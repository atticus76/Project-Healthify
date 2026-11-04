"""Goal instances, progress tracking, reminders, and daily rollover (FR-09)."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from .alerts import DATABASE_PATH

GOAL_DAILY_STEPS = "daily_steps"
MILESTONES = (25, 50, 75, 100)
REMINDER_HOURS = (2, 8, 16)
MOTIVATIONAL_PROMPT = (
    "Every step counts. Tomorrow is a fresh start—try a short walk and build from there."
)
_scheduler_started = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def next_local_midnight(now: datetime | None = None) -> datetime:
    local = (now or _now()).astimezone()
    tomorrow = (local + timedelta(days=1)).date()
    midnight = datetime.combine(tomorrow, datetime.min.time(), local.tzinfo)
    return midnight.astimezone(timezone.utc)


def _validate_target(target: int) -> int:
    if not isinstance(target, int) or not 1 <= target <= 1_000_000:
        raise ValueError("Step target must be a whole number between 1 and 1,000,000.")
    return target


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS health_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            goal_type TEXT NOT NULL,
            target INTEGER NOT NULL,
            is_daily INTEGER NOT NULL DEFAULT 1,
            reminders_enabled INTEGER NOT NULL DEFAULT 0,
            reminder_25_enabled INTEGER NOT NULL DEFAULT 1,
            reminder_50_enabled INTEGER NOT NULL DEFAULT 1,
            reminder_75_enabled INTEGER NOT NULL DEFAULT 1,
            deadline_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(health_goals)")}
    if "is_daily" not in columns:
        conn.execute("ALTER TABLE health_goals ADD COLUMN is_daily INTEGER NOT NULL DEFAULT 1")
    if "deadline_at" not in columns:
        conn.execute("ALTER TABLE health_goals ADD COLUMN deadline_at TEXT")
        conn.execute(
            "UPDATE health_goals SET deadline_at = datetime(created_at, '+24 hours') "
            "WHERE deadline_at IS NULL"
        )
    for column in ("reminder_25_enabled", "reminder_50_enabled", "reminder_75_enabled"):
        if column not in columns:
            conn.execute(
                f"ALTER TABLE health_goals ADD COLUMN {column} INTEGER NOT NULL DEFAULT 1"
            )
    existing_progress = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'goal_progress'"
    ).fetchone()
    if existing_progress and "progress_date" in (existing_progress["sql"] or ""):
        conn.execute("ALTER TABLE goal_progress RENAME TO goal_progress_legacy")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS goal_progress (
            goal_id INTEGER PRIMARY KEY,
            steps INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'in_progress',
            prompt TEXT NOT NULL DEFAULT '',
            milestones_sent TEXT NOT NULL DEFAULT '',
            reminders_sent TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (goal_id) REFERENCES health_goals(id)
        )
        """
    )
    if existing_progress and "progress_date" in (existing_progress["sql"] or ""):
        conn.execute(
            """
            INSERT OR IGNORE INTO goal_progress (goal_id, steps, status, prompt, milestones_sent)
            SELECT goal_id, MAX(steps), 'in_progress', '', milestones_sent
            FROM goal_progress_legacy GROUP BY goal_id
            """
        )
        conn.execute("DROP TABLE goal_progress_legacy")
    progress_columns = {row["name"] for row in conn.execute("PRAGMA table_info(goal_progress)")}
    if "reminders_sent" not in progress_columns:
        conn.execute("ALTER TABLE goal_progress ADD COLUMN reminders_sent TEXT NOT NULL DEFAULT ''")
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _ensure_progress(conn: sqlite3.Connection, goal_id: int) -> sqlite3.Row:
    conn.execute("INSERT OR IGNORE INTO goal_progress (goal_id) VALUES (?)", (goal_id,))
    return conn.execute("SELECT * FROM goal_progress WHERE goal_id = ?", (goal_id,)).fetchone()


def _milestones(value: str) -> list[int]:
    return [int(item) for item in value.split(",") if item]


def _hours(value: str) -> list[int]:
    return [int(item) for item in value.split(",") if item]


def _goal_row(conn: sqlite3.Connection, goal_id: int, user_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM health_goals WHERE id = ? AND user_id = ?", (goal_id, user_id)
    ).fetchone()
    if not row:
        raise ValueError("Goal was not found.")
    return row


def _goal_dict(conn: sqlite3.Connection, goal: sqlite3.Row) -> dict[str, Any]:
    progress = _ensure_progress(conn, goal["id"])
    return {
        **dict(goal),
        "steps": progress["steps"],
        "status": progress["status"],
        "prompt": progress["prompt"],
        "milestones": _milestones(progress["milestones_sent"]),
        "reminders_sent": _hours(progress["reminders_sent"]),
        "reminder_25_enabled": bool(goal["reminder_25_enabled"]),
        "reminder_50_enabled": bool(goal["reminder_50_enabled"]),
        "reminder_75_enabled": bool(goal["reminder_75_enabled"]),
    }


def add_goal(
    user_id: str,
    goal_type: str,
    target: int,
    reminders_enabled: bool,
    is_daily: bool = True,
    deadline_at: str | None = None,
    reminder_25_enabled: bool = True,
    reminder_50_enabled: bool = True,
    reminder_75_enabled: bool = True,
) -> dict[str, Any]:
    if goal_type != GOAL_DAILY_STEPS:
        raise ValueError("Unsupported goal type.")
    target = _validate_target(target)
    created = _now()
    deadline = next_local_midnight(created) if is_daily else _parse_time(deadline_at or "")
    if deadline <= created:
        raise ValueError("The goal deadline must be in the future.")
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO health_goals
                (user_id, goal_type, target, is_daily, reminders_enabled,
                 reminder_25_enabled, reminder_50_enabled, reminder_75_enabled,
                 deadline_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                goal_type,
                target,
                int(is_daily),
                int(reminders_enabled),
                int(reminder_25_enabled),
                int(reminder_50_enabled),
                int(reminder_75_enabled),
                deadline.isoformat(),
                created.isoformat(),
            ),
        )
        return _goal_dict(conn, conn.execute(
            "SELECT * FROM health_goals WHERE id = ?", (cursor.lastrowid,)
        ).fetchone())


def save_goal(user_id: str, goal_type: str, target: int, reminders_enabled: bool) -> dict[str, Any]:
    return add_goal(user_id, goal_type, target, reminders_enabled)


def list_goals(user_id: str) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM health_goals WHERE user_id = ? ORDER BY created_at DESC, id DESC",
            (user_id,),
        ).fetchall()
        return [_goal_dict(conn, row) for row in rows]


def get_goal(user_id: str) -> dict[str, Any] | None:
    rows = list_goals(user_id)
    return rows[0] if rows else None


def get_progress(user_id: str, progress_date: Any = None) -> dict[str, Any]:
    goal = get_goal(user_id)
    return goal or {"steps": 0, "status": "not_set", "prompt": "", "milestones": []}


def list_progress(user_id: str, progress_date: Any = None) -> list[dict[str, Any]]:
    return list_goals(user_id)


def _rollover_daily(conn: sqlite3.Connection, goal: sqlite3.Row) -> dict[str, Any] | None:
    if not goal["is_daily"]:
        return None
    created = _now()
    deadline = next_local_midnight(created)
    cursor = conn.execute(
        """
        INSERT INTO health_goals
            (user_id, goal_type, target, is_daily, reminders_enabled, deadline_at, created_at)
        VALUES (?, ?, ?, 1, ?, ?, ?)
        """,
        (
            goal["user_id"], goal["goal_type"], goal["target"],
            goal["reminders_enabled"], deadline.isoformat(), created.isoformat(),
        ),
    )
    return {"id": cursor.lastrowid, "created_at": created.isoformat()}


def record_steps(
    user_id: str,
    steps: int,
    progress_date: Any = None,
    goal_id: int | None = None,
) -> dict[str, Any]:
    if not isinstance(steps, int) or steps < 0:
        raise ValueError("Enter a whole number of steps to add.")
    with _connect() as conn:
        goal = _goal_row(conn, goal_id or list_goals(user_id)[0]["id"], user_id)
        progress = _ensure_progress(conn, goal["id"])
        if progress["status"] != "in_progress" or _parse_time(goal["deadline_at"]) <= _now():
            raise ValueError("This goal has ended and can no longer be updated.")
        new_steps = progress["steps"] + steps
        percentage = new_steps * 100 / goal["target"]
        sent = _milestones(progress["milestones_sent"])
        enabled = {
            25: goal["reminder_25_enabled"],
            50: goal["reminder_50_enabled"],
            75: goal["reminder_75_enabled"],
            100: goal["reminders_enabled"],
        }
        reached = [
            item for item in MILESTONES
            if percentage >= item and item not in sent and enabled[item]
        ]
        sent.extend(
            item for item in MILESTONES
            if percentage >= item and item not in sent
        )
        status = "complete" if new_steps >= goal["target"] else "in_progress"
        conn.execute(
            """
            UPDATE goal_progress SET steps = ?, status = ?, milestones_sent = ?
            WHERE goal_id = ?
            """,
            (new_steps, status, ",".join(map(str, sorted(sent))), goal["id"]),
        )
    return {"steps": new_steps, "target": goal["target"], "milestones": reached, "status": status, "prompt": ""}


def end_goal(user_id: str, progress_date: Any = None, goal_id: int | None = None) -> dict[str, Any]:
    with _connect() as conn:
        goal = _goal_row(conn, goal_id or list_goals(user_id)[0]["id"], user_id)
        progress = _ensure_progress(conn, goal["id"])
        status = "complete" if progress["steps"] >= goal["target"] else "incomplete"
        prompt = MOTIVATIONAL_PROMPT if status == "incomplete" else ""
        conn.execute(
            "UPDATE goal_progress SET status = ?, prompt = ? WHERE goal_id = ?",
            (status, prompt, goal["id"]),
        )
        rollover = _rollover_daily(conn, goal)
    return {"steps": progress["steps"], "target": goal["target"], "status": status, "prompt": prompt, "rollover": rollover}


def complete_day(user_id: str, progress_date: Any = None, goal_id: int | None = None) -> dict[str, Any]:
    return end_goal(user_id, progress_date, goal_id)


def delete_goal(user_id: str, goal_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "DELETE FROM goal_progress WHERE goal_id = ? AND EXISTS "
            "(SELECT 1 FROM health_goals WHERE id = ? AND user_id = ?)",
            (goal_id, goal_id, user_id),
        )
        conn.execute("DELETE FROM health_goals WHERE id = ? AND user_id = ?", (goal_id, user_id))


def refresh_reminders(user_id: str) -> list[dict[str, Any]]:
    now = _now()
    notifications = []
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM health_goals WHERE user_id = ? AND id IN "
            "(SELECT goal_id FROM goal_progress WHERE status = 'in_progress')",
            (user_id,),
        ).fetchall()
        for goal in rows:
            progress = _ensure_progress(conn, goal["id"])
            elapsed = (now - _parse_time(goal["created_at"])).total_seconds() / 3600
            if now >= _parse_time(goal["deadline_at"]):
                status = "complete" if progress["steps"] >= goal["target"] else "incomplete"
                prompt = "" if status == "complete" else MOTIVATIONAL_PROMPT
                conn.execute(
                    "UPDATE goal_progress SET status = ?, prompt = ? WHERE goal_id = ?",
                    (status, prompt, goal["id"]),
                )
                rollover = _rollover_daily(conn, goal)
                notifications.append({
                    "title": "Goal deadline reached",
                    "message": f"Your goal ended with {progress['steps']:,} of {goal['target']:,} steps.",
                })
                continue
            sent = _hours(progress["reminders_sent"])
            if goal["reminders_enabled"] and progress["steps"] == 0:
                for hour in REMINDER_HOURS:
                    if elapsed >= hour and hour not in sent:
                        sent.append(hour)
                        notifications.append({
                            "title": "Goal progress reminder",
                            "message": f"No progress has been recorded after {hour} hours. Every step counts.",
                        })
            conn.execute(
                "UPDATE goal_progress SET reminders_sent = ? WHERE goal_id = ?",
                (",".join(map(str, sorted(sent))), goal["id"]),
            )
    return notifications


def start_scheduler(user_id: str, interval_seconds: int = 300) -> None:
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True
    import threading
    import time
    from . import email_alerts

    def run() -> None:
        while True:
            for notification in refresh_reminders(user_id):
                email_alerts.dispatch(user_id, [{
                    "title": notification["title"],
                    "message": notification["message"],
                    "severity": "info",
                }])
            time.sleep(interval_seconds)

    thread = threading.Thread(target=run, name="healthify-goal-scheduler", daemon=True)
    thread.start()
