"""Goal instances, progress tracking, reminders, and daily rollover (FR-09).

Stored in the cloud health_goals and goal_progress tables (S2-04). Every goal
gets its goal_progress row when it is created. Every user_id must be an
existing account.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.db import connect
from backend import calories

log = logging.getLogger(__name__)

GOAL_DAILY_STEPS = "daily_steps"
BURN = "calories_burned"
LIMIT = "consumed_below"
LABELS = {GOAL_DAILY_STEPS: "Step Count", BURN: "Calories burned", LIMIT: "Calories consumed below limit"}
MILESTONES = (25, 50, 75, 100)
REMINDER_HOURS = (2, 8, 16)
MOTIVATIONAL_PROMPT = (
    "Every step counts. Tomorrow is a fresh start—try a short walk and build from there."
)
_scheduler_started = False


class EmulatorDisabled(ValueError):
    """An emulator tick arrived after the account disabled the emulator."""


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
        raise ValueError("Target must be a whole number between 1 and 1,000,000.")
    return target


# Each goal with its progress, in one query. Goals always get a progress row
# when created; the COALESCEs only guard against a missing one.
_SELECT_GOALS = """
    SELECT g.*,
        COALESCE(p.steps, 0) AS steps,
        COALESCE(p.status, 'in_progress') AS status,
        COALESCE(p.prompt, '') AS prompt,
        COALESCE(p.milestones_sent, '') AS milestones_sent,
        COALESCE(p.reminders_sent, '') AS reminders_sent
    FROM health_goals g
    JOIN goal_progress p ON p.goal_id = g.id
"""
_NEWEST_FIRST = " ORDER BY g.created_at DESC, g.id DESC"

# Insert a goal and its empty progress row in one round trip, returning both.
_INSERT_GOAL = """
    WITH new_goal AS (
        INSERT INTO health_goals
            (user_id, goal_type, target, is_daily, reminders_enabled,
             reminder_25_enabled, reminder_50_enabled, reminder_75_enabled,
             deadline_at, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    ), new_progress AS (
        INSERT INTO goal_progress (goal_id) SELECT id FROM new_goal
        RETURNING *
    )
    SELECT new_goal.*, p.steps, p.status, p.prompt, p.milestones_sent, p.reminders_sent
    FROM new_goal JOIN new_progress p ON p.goal_id = new_goal.id
"""


def _milestones(value: str) -> list[int]:
    return [int(item) for item in value.split(",") if item]


def _hours(value: str) -> list[int]:
    return [int(item) for item in value.split(",") if item]


def _goal_dict(row: dict[str, Any]) -> dict[str, Any]:
    goal = dict(row)
    goal["milestones"] = _milestones(goal.pop("milestones_sent"))
    goal["reminders_sent"] = _hours(goal["reminders_sent"])
    for flag in ("reminder_25_enabled", "reminder_50_enabled", "reminder_75_enabled"):
        goal[flag] = bool(goal[flag])
    return goal


def _goal_row(conn, user_id: str, goal_id: int | None) -> dict[str, Any]:
    """The user's goal with this id, or their newest goal if goal_id is None."""
    if goal_id is None:
        row = conn.execute(
            _SELECT_GOALS + " WHERE g.user_id = %s AND g.goal_type = %s" + _NEWEST_FIRST + " LIMIT 1", (user_id, GOAL_DAILY_STEPS)
        ).fetchone()
        if not row:
            raise ValueError("Set a step goal first.")
        return row
    row = conn.execute(
        _SELECT_GOALS + " WHERE g.id = %s AND g.user_id = %s FOR UPDATE OF g,p", (goal_id, user_id)
    ).fetchone()
    if not row:
        raise ValueError("Goal was not found.")
    return row


def _insert_goal(conn, user_id, goal_type, target, is_daily, reminders_enabled,
                 r25, r50, r75, deadline: datetime, created: datetime) -> dict[str, Any]:
    return conn.execute(
        _INSERT_GOAL,
        (
            user_id, goal_type, target, int(is_daily), int(reminders_enabled),
            int(r25), int(r50), int(r75), deadline.isoformat(), created.isoformat(),
        ),
    ).fetchone()


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
    if goal_type not in LABELS:
        raise ValueError("Unsupported goal type.")
    target = _validate_target(target)
    created = _now()
    deadline = next_local_midnight(created) if is_daily else _parse_time(deadline_at or "")
    if deadline <= created:
        raise ValueError("The goal deadline must be in the future.")
    with connect("add goal") as conn:
        row = _insert_goal(
            conn, user_id, goal_type, target, is_daily, reminders_enabled,
            reminder_25_enabled, reminder_50_enabled, reminder_75_enabled, deadline, created,
        )
    return _goal_dict(row)


def save_goal(user_id: str, goal_type: str, target: int, reminders_enabled: bool) -> dict[str, Any]:
    return add_goal(user_id, goal_type, target, reminders_enabled)


def list_goals(user_id: str) -> list[dict[str, Any]]:
    with connect("load goals") as conn:
        rows = conn.execute(_SELECT_GOALS + " WHERE g.user_id = %s" + _NEWEST_FIRST, (user_id,)).fetchall()
    return [_goal_dict(row) for row in rows]


def get_goal(user_id: str) -> dict[str, Any] | None:
    rows = list_goals(user_id)
    return rows[0] if rows else None


def _rollover_daily(conn, goal: dict[str, Any]) -> dict[str, Any] | None:
    """Start tomorrow's copy of a daily goal (same target and reminder setting)."""
    if not goal["is_daily"]:
        return None
    created = _now()
    row = _insert_goal(
        conn, goal["user_id"], goal["goal_type"], goal["target"], True,
        goal["reminders_enabled"], goal["reminder_25_enabled"], goal["reminder_50_enabled"], goal["reminder_75_enabled"], next_local_midnight(created), created,
    )
    return {"id": row["id"], "created_at": row["created_at"]}


def _finish(conn, goal: dict[str, Any]) -> tuple[str, str, dict[str, Any] | None]:
    """Mark a goal complete/incomplete and roll daily goals over."""
    reached = goal["steps"] >= goal["target"]
    successful = not reached if goal["goal_type"] == LIMIT else reached
    status = "complete" if successful else "incomplete"
    prompt = MOTIVATIONAL_PROMPT if status == "incomplete" and goal["goal_type"] == GOAL_DAILY_STEPS else ""
    conn.execute(
        "UPDATE goal_progress SET status = %s, prompt = %s WHERE goal_id = %s",
        (status, prompt, goal["id"]),
    )
    return status, prompt, _rollover_daily(conn, goal)


def record_steps(
    user_id: str,
    steps: int,
    progress_date: Any = None,
    goal_id: int | None = None,
    *,
    from_emulator: bool = False,
) -> dict[str, Any]:
    if not isinstance(steps, int) or steps < 0:
        raise ValueError("Enter a whole number of steps to add.")
    with connect("record steps") as conn:
        if from_emulator:
            account = conn.execute(
                "SELECT app_state->'telemetry_enabled' AS enabled FROM users WHERE username=%s FOR UPDATE",
                (user_id,),
            ).fetchone()
            if not account or account["enabled"] is not True:
                raise EmulatorDisabled("The telemetry emulator is disabled.")
        goal = _goal_row(conn, user_id, goal_id)
        if goal["goal_type"] != GOAL_DAILY_STEPS:
            raise ValueError("Calories are tracked automatically.")
        if goal["status"] != "in_progress" or _parse_time(goal["deadline_at"]) <= _now():
            raise ValueError("This goal has ended and can no longer be updated.")
        new_steps = goal["steps"] + steps
        percentage = new_steps * 100 / goal["target"]
        sent = _milestones(goal["milestones_sent"])
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
            UPDATE goal_progress SET steps = %s, status = %s, milestones_sent = %s
            WHERE goal_id = %s
            """,
            (new_steps, status, ",".join(map(str, sorted(sent))), goal["id"]),
        )
    return {"steps": new_steps, "target": goal["target"], "milestones": reached, "status": status, "prompt": ""}


def _sync_calorie_goal(conn, goal, now):
    end = min(now, _parse_time(goal["deadline_at"]))
    values = calories.period_summary(conn, goal["user_id"], _parse_time(goal["created_at"]), end)
    field = "burned" if goal["goal_type"] == BURN else "consumed"
    amount = int(values[field])
    sent = _milestones(goal["milestones_sent"])
    reached = [n for n in MILESTONES if amount * 100 >= goal["target"] * n and n not in sent]
    if amount != goal["steps"] or reached:
        conn.execute("UPDATE goal_progress SET steps=%s, milestones_sent=%s WHERE goal_id=%s",
                     (amount, ",".join(map(str, sorted(sent + reached))), goal["id"]))
    if goal["goal_type"] == BURN and not goal["is_daily"] and amount >= goal["target"]:
        conn.execute("UPDATE goal_progress SET status='complete' WHERE goal_id=%s", (goal["id"],))
    goal["steps"] = amount
    notices = []
    for n in reached:
        enabled = goal["reminders_enabled"] if n == 100 else goal[f"reminder_{n}_enabled"]
        if enabled:
            notices.append((goal["user_id"], {"title": LABELS[goal["goal_type"]],
                            "message": f"You have {field} {amount:,} kcal ({n}% milestone of {goal['target']:,} kcal)."}))
    return notices


def end_goal(user_id: str, progress_date: Any = None, goal_id: int | None = None) -> dict[str, Any]:
    with connect("end goal") as conn:
        goal = _goal_row(conn, user_id, goal_id)
        if goal["goal_type"] != GOAL_DAILY_STEPS and goal["status"] == "in_progress":
            _sync_calorie_goal(conn, goal, _now())
        status, prompt, rollover = _finish(conn, goal)
    return {"steps": goal["steps"], "target": goal["target"], "status": status, "prompt": prompt, "rollover": rollover}


def complete_day(user_id: str, progress_date: Any = None, goal_id: int | None = None) -> dict[str, Any]:
    return end_goal(user_id, progress_date, goal_id)


def delete_goal(user_id: str, goal_id: int) -> None:
    """Delete one of the user's goals (its progress row goes with it)."""
    with connect("delete goal") as conn:
        conn.execute("DELETE FROM health_goals WHERE id = %s AND user_id = %s", (goal_id, user_id))


def _refresh(conn, goals_in_progress: list[dict[str, Any]]) -> list[tuple[str, dict[str, str]]]:
    """End goals past their deadline and collect due reminders, as (user_id, notification)."""
    now = _now()
    due = []
    for goal in goals_in_progress:
        unit = "steps" if goal["goal_type"] == GOAL_DAILY_STEPS else "kcal"
        if unit == "kcal":
            due.extend(_sync_calorie_goal(conn, goal, now))
        if now >= _parse_time(goal["deadline_at"]):
            _finish(conn, goal)
            due.append((goal["user_id"], {
                "title": "Goal deadline reached",
                "message": f"Your goal ended with {goal['steps']:,} of {goal['target']:,} {unit}.",
            }))
            continue
        if not goal["reminders_enabled"] or goal["steps"] != 0:
            continue
        elapsed = (now - _parse_time(goal["created_at"])).total_seconds() / 3600
        sent = _hours(goal["reminders_sent"])
        new_hours = [hour for hour in REMINDER_HOURS if elapsed >= hour and hour not in sent]
        if not new_hours:
            continue
        for hour in new_hours:
            due.append((goal["user_id"], {
                "title": "Goal progress reminder",
                "message": f"No progress has been recorded after {hour} hours.",
            }))
        conn.execute(
            "UPDATE goal_progress SET reminders_sent = %s WHERE goal_id = %s",
            (",".join(map(str, sorted(sent + new_hours))), goal["id"]),
        )
    return due


def refresh_reminders(user_id: str) -> list[dict[str, Any]]:
    with connect("check goal reminders") as conn:
        rows = conn.execute(
            _SELECT_GOALS + " WHERE g.user_id = %s AND p.status = 'in_progress' FOR UPDATE OF g,p", (user_id,)
        ).fetchall()
        return [notification for _, notification in _refresh(conn, rows)]


def refresh_all_reminders() -> list[tuple[str, dict[str, Any]]]:
    """Check every user's goals in progress. Returns (user_id, notification) pairs."""
    with connect("check all goal reminders") as conn:
        rows = conn.execute(_SELECT_GOALS + " WHERE p.status = 'in_progress' FOR UPDATE OF g,p").fetchall()
        return _refresh(conn, rows)


def start_scheduler(interval_seconds: int = 60) -> None:
    """Every few minutes, end overdue goals and email due reminders, for every user."""
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True
    import threading
    import time
    from . import alerts, email_alerts

    def run() -> None:
        while True:
            try:
                for user_id, notification in alerts.missing_meal_alerts():
                    email_alerts.dispatch(user_id, [notification])
                for user_id, notification in refresh_all_reminders():
                    email_alerts.dispatch(user_id, [{
                        "title": notification["title"],
                        "message": notification["message"],
                        "severity": "info",
                    }])
            except Exception:  # keep the scheduler alive (e.g. Supabase paused)
                log.exception("Goal reminder check failed; trying again later.")
            time.sleep(interval_seconds)

    thread = threading.Thread(target=run, name="healthify-goal-scheduler", daemon=True)
    thread.start()
