"""Recurring health report preferences and latest-report generation."""

from __future__ import annotations

import json
import sqlite3
import smtplib
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from . import alerts, email_alerts, goals, telemetry_emulator, telemetry_store

# Local SQLite file, used until this module is ported to the cloud (S2-04 task 4).
DATABASE_PATH = Path(__file__).resolve().parent / "healthtrack.db"

FREQUENCIES = ("daily", "weekly")
_scheduler_started = False


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS report_preferences (
            user_id TEXT PRIMARY KEY,
            frequency TEXT NOT NULL,
            email TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS health_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            content TEXT NOT NULL,
            delivery_status TEXT NOT NULL DEFAULT 'not_sent',
            delivery_error TEXT NOT NULL DEFAULT ''
        )
        """
    )
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _validate_frequency(frequency: str) -> str:
    if frequency not in FREQUENCIES:
        raise ValueError("Choose a daily or weekly reporting frequency.")
    return frequency


def get_preferences(user_id: str) -> dict[str, str] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT frequency, email, updated_at FROM report_preferences WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def save_preferences(user_id: str, frequency: str, email: str) -> dict[str, str]:
    frequency = _validate_frequency(frequency)
    if not email_alerts.is_valid_address(email):
        raise ValueError("Enter a valid email address.")
    updated = _now().isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO report_preferences (user_id, frequency, email, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                frequency = excluded.frequency,
                email = excluded.email,
                updated_at = excluded.updated_at
            """,
            (user_id, frequency, email.strip(), updated),
        )
    return {"frequency": frequency, "email": email.strip(), "updated_at": updated}


def _metric_summary(telemetry: dict[str, Any] | None) -> dict[str, Any]:
    if not telemetry:
        return {
            "available": False,
            "message": "Telemetry data is unavailable or incomplete; no health readings were interpreted.",
        }
    steps = telemetry.get("steps", {}).get("dataPoints", [])
    heart_rate = telemetry.get("heart-rate", {}).get("dataPoints", [])
    summaries = telemetry_emulator.summarize_fitbit_data(telemetry)
    return {
        "available": bool(steps or heart_rate),
        "steps_points": len(steps),
        "heart_rate_points": len(heart_rate),
        "summaries": summaries,
        "message": "Telemetry is available for this reporting period.",
    }


def generate_report(
    user_id: str,
    telemetry: dict[str, Any] | None = None,
    now: datetime | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    telemetry = (
        telemetry
        if telemetry is not None
        else telemetry_store.get_latest(user_id)
    )
    end = now or _now()
    preferences = get_preferences(user_id)
    days = 1 if not preferences or preferences["frequency"] == "daily" else 7
    start = end - timedelta(days=days)
    user_goals = goals.list_goals(user_id)
    user_alerts = alerts.list_alerts(user_id)
    content = {
        "metrics": _metric_summary(telemetry),
        "goals": [
            {
                "target": item["target"],
                "steps": item["steps"],
                "status": item["status"],
                "percent": min(100, int(item["steps"] * 100 / item["target"])),
            }
            for item in user_goals
        ],
        "alerts": [
            {"title": item["title"], "severity": item["severity"], "message": item["message"]}
            for item in user_alerts
            if item["started_at"] >= start.isoformat()
        ],
    }
    if not persist:
        return {
            "id": 0,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "generated_at": end.isoformat(),
            "content": content,
            "delivery_status": "not_sent",
            "delivery_error": "",
        }
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO health_reports
                (user_id, period_start, period_end, generated_at, content)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, start.isoformat(), end.isoformat(), end.isoformat(), json.dumps(content)),
        )
        report_id = cursor.lastrowid
    return get_report(user_id, report_id)


def get_report(user_id: str, report_id: int | None = None) -> dict[str, Any] | None:
    with _connect() as conn:
        query = (
            "SELECT * FROM health_reports WHERE user_id = ? ORDER BY generated_at DESC, id DESC LIMIT 1"
            if report_id is None
            else "SELECT * FROM health_reports WHERE user_id = ? AND id = ?"
        )
        params: tuple[Any, ...] = (user_id,) if report_id is None else (user_id, report_id)
        row = conn.execute(query, params).fetchone()
    if not row:
        return None
    result = dict(row)
    result["content"] = json.loads(result["content"])
    return result


def deliver_report(user_id: str, report: dict[str, Any]) -> dict[str, Any]:
    preferences = get_preferences(user_id)
    if not preferences:
        return report
    message = {
        "title": "Healthify health report",
        "message": (
            f"Report for {report['period_start']} through {report['period_end']}. "
            "Open Analytics and Reports in Healthify to review the details."
        ),
        "severity": alerts.SEVERITY_INFO,
    }
    status, error = "sent", ""
    try:
        email_alerts.send(email_alerts.build_message(message, preferences["email"]))
    except (
        email_alerts.EmailNotConfigured,
        smtplib.SMTPException,
        OSError,
        ValueError,
    ) as exc:
        status, error = "failed", str(exc)
    with _connect() as conn:
        conn.execute(
            "UPDATE health_reports SET delivery_status = ?, delivery_error = ? WHERE id = ? AND user_id = ?",
            (status, error, report["id"], user_id),
        )
    report["delivery_status"] = status
    report["delivery_error"] = error
    return report


def _is_due(preferences: dict[str, str], report: dict[str, Any] | None) -> bool:
    if report is None:
        return True
    generated = datetime.fromisoformat(report["generated_at"])
    local_generated = generated.astimezone()
    next_midnight = datetime.combine(
        local_generated.date() + timedelta(days=1),
        datetime.min.time(),
        local_generated.tzinfo,
    )
    if preferences["frequency"] == "weekly":
        next_midnight += timedelta(days=6)
    return _now() >= next_midnight.astimezone(timezone.utc)


def start_scheduler(user_id: str, interval_seconds: int = 60) -> None:
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True

    def run() -> None:
        while True:
            preferences = get_preferences(user_id)
            if preferences and _is_due(preferences, get_report(user_id)):
                deliver_report(user_id, generate_report(user_id))
            time.sleep(interval_seconds)

    threading.Thread(target=run, name="healthify-report-scheduler", daemon=True).start()
