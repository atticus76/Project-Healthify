"""Recurring health report preferences and latest-report generation.

Stored in the cloud report_preferences and health_reports tables (S2-04).
Every user_id must be an existing account.
"""

from __future__ import annotations

import json
import logging
import smtplib
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.db import connect

from . import alerts, email_alerts, goals, telemetry_emulator

log = logging.getLogger(__name__)

FREQUENCIES = ("daily", "weekly")
_scheduler_started = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _validate_frequency(frequency: str) -> str:
    if frequency not in FREQUENCIES:
        raise ValueError("Choose a daily or weekly reporting frequency.")
    return frequency


def get_preferences(user_id: str) -> dict[str, str] | None:
    with connect("load report preferences") as conn:
        return conn.execute(
            "SELECT frequency, email, updated_at FROM report_preferences WHERE user_id = %s",
            (user_id,),
        ).fetchone()


def save_preferences(user_id: str, frequency: str, email: str) -> dict[str, str]:
    frequency = _validate_frequency(frequency)
    if not email_alerts.is_valid_address(email):
        raise ValueError("Enter a valid email address.")
    updated = _now().isoformat()
    with connect("save report preferences") as conn:
        conn.execute(
            """
            INSERT INTO report_preferences (user_id, frequency, email, updated_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
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
        else telemetry_emulator.get_latest_telemetry(user_id)
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
    with connect("save report") as conn:
        row = conn.execute(
            """
            INSERT INTO health_reports
                (user_id, period_start, period_end, generated_at, content)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (user_id, start.isoformat(), end.isoformat(), end.isoformat(), json.dumps(content)),
        ).fetchone()
    return _report_dict(row)


def _report_dict(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    result["content"] = json.loads(result["content"])
    return result


def get_report(user_id: str, report_id: int | None = None) -> dict[str, Any] | None:
    query = (
        "SELECT * FROM health_reports WHERE user_id = %s ORDER BY generated_at DESC, id DESC LIMIT 1"
        if report_id is None
        else "SELECT * FROM health_reports WHERE user_id = %s AND id = %s"
    )
    params: tuple[Any, ...] = (user_id,) if report_id is None else (user_id, report_id)
    with connect("load report") as conn:
        row = conn.execute(query, params).fetchone()
    return _report_dict(row) if row else None


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
    with connect("save report delivery status") as conn:
        conn.execute(
            "UPDATE health_reports SET delivery_status = %s, delivery_error = %s WHERE id = %s AND user_id = %s",
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


def send_due_reports() -> list[str]:
    """Generate and email every report that's due. Returns the user_ids served."""
    with connect("find due reports") as conn:
        rows = conn.execute(
            """
            SELECT p.user_id, p.frequency, p.email, latest.generated_at
            FROM report_preferences p
            LEFT JOIN LATERAL (
                SELECT generated_at FROM health_reports r
                WHERE r.user_id = p.user_id
                ORDER BY r.generated_at DESC, r.id DESC
                LIMIT 1
            ) latest ON true
            ORDER BY p.user_id
            """
        ).fetchall()
    served = []
    for row in rows:
        last = {"generated_at": row["generated_at"]} if row["generated_at"] else None
        if _is_due(row, last):
            deliver_report(row["user_id"], generate_report(row["user_id"]))
            served.append(row["user_id"])
    return served


def start_scheduler(interval_seconds: int = 60) -> None:
    """Every minute, send every user's report that's due."""
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True

    def run() -> None:
        while True:
            try:
                send_due_reports()
            except Exception:  # keep the scheduler alive (e.g. Supabase paused)
                log.exception("Report check failed; trying again later.")
            time.sleep(interval_seconds)

    threading.Thread(target=run, name="healthify-report-scheduler", daemon=True).start()
