"""Health abnormality alerts (US-04 / FR-02).

Spec: code/specs/features/S2-03-health-abnormality-alerts.md

Checks synced telemetry (Google Health API or the emulator, which share the
same JSON shape) for a sustained high heart rate and for gaps in the data.
Alerts are stored in the cloud health_alerts table (S2-04) so the Alerts page
can show a history. Delivery (toast + browser notification) is the
frontend's job and email is email_alerts.py's; this module only decides what is
abnormal and records it, plus the user's alert email address.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.db import connect

HIGH_HEART_RATE_BPM = 130
SUSTAINED_FOR = timedelta(minutes=5)
# Samples further apart than this mean the wearable stopped sending data.
MAX_SAMPLE_GAP = timedelta(minutes=2)

KIND_HIGH_HEART_RATE = "high_heart_rate"
KIND_DATA_GAP = "data_gap"
SEVERITY_URGENT = "urgent"
SEVERITY_INFO = "info"

DISCLAIMER = (
    "Healthify is not a medical device and does not give medical advice. "
    "If you feel unwell, contact a doctor or emergency services."
)


@dataclass(frozen=True)
class HeartRateSample:
    time: datetime
    bpm: int


@dataclass(frozen=True)
class Finding:
    kind: str
    severity: str
    title: str
    message: str
    started_at: datetime
    ended_at: datetime
    peak_bpm: int | None = None


# --- reading telemetry ------------------------------------------------------------

def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def extract_heart_rate(data: dict[str, Any]) -> list[HeartRateSample]:
    """Heart-rate samples from a Fitbit-shaped payload, oldest first."""
    samples = []
    for point in data.get("heart-rate", {}).get("dataPoints", []) or []:
        heart_rate = point.get("heartRate", {})
        try:
            samples.append(
                HeartRateSample(
                    _parse_time(heart_rate["sampleTime"]["physicalTime"]),
                    int(heart_rate["beatsPerMinute"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(samples, key=lambda sample: sample.time)


def extract_exercise_intervals(data: dict[str, Any]) -> list[tuple[datetime, datetime]]:
    """Exercise sessions, during which a high heart rate is expected."""
    intervals = []
    for point in data.get("exercise", {}).get("dataPoints", []) or []:
        interval = point.get("exercise", {}).get("interval", {})
        try:
            intervals.append(
                (_parse_time(interval["startTime"]), _parse_time(interval["endTime"]))
            )
        except (KeyError, TypeError, ValueError):
            continue
    return intervals


# --- deciding what is abnormal --------------------------------------------------------

def _exercising(moment: datetime, exercise: list[tuple[datetime, datetime]]) -> bool:
    return any(start <= moment <= end for start, end in exercise)


def evaluate_heart_rate(
    samples: list[HeartRateSample],
    exercise: list[tuple[datetime, datetime]] | None = None,
) -> list[Finding]:
    """Find sustained high heart rate at rest and gaps in the data.

    A high heart rate only counts as sustained if the readings are continuous.
    If the wearable drops out in the middle, we can't tell what happened while
    it was gone, so we report a data gap instead of raising a false alarm.
    """
    exercise = exercise or []
    samples = sorted(samples, key=lambda sample: sample.time)
    findings: list[Finding] = []
    run: list[HeartRateSample] = []

    def close_run() -> None:
        if run and run[-1].time - run[0].time >= SUSTAINED_FOR:
            peak = max(sample.bpm for sample in run)
            minutes = int((run[-1].time - run[0].time).total_seconds() // 60)
            findings.append(
                Finding(
                    kind=KIND_HIGH_HEART_RATE,
                    severity=SEVERITY_URGENT,
                    title="Abnormal heart rate spike",
                    message=(
                        f"Your heart rate stayed above {HIGH_HEART_RATE_BPM} BPM "
                        f"for {minutes} minutes while you weren't exercising "
                        f"(peak {peak} BPM)."
                    ),
                    started_at=run[0].time,
                    ended_at=run[-1].time,
                    peak_bpm=peak,
                )
            )
        run.clear()

    for previous, sample in zip([None, *samples], samples):
        if previous is not None and sample.time - previous.time > MAX_SAMPLE_GAP:
            close_run()
            findings.append(
                Finding(
                    kind=KIND_DATA_GAP,
                    severity=SEVERITY_INFO,
                    title="Wearable data gap",
                    message=(
                        "Your wearable stopped sending heart-rate data from "
                        f"{previous.time:%H:%M} to {sample.time:%H:%M} UTC. "
                        "Check that it's worn snugly and charged."
                    ),
                    started_at=previous.time,
                    ended_at=sample.time,
                )
            )
        if sample.bpm > HIGH_HEART_RATE_BPM and not _exercising(sample.time, exercise):
            run.append(sample)
        else:
            close_run()
    close_run()
    return findings


# --- storing alerts --------------------------------------------------------------------
# Tables: health_alerts and alert_settings in code/backend/db/schema.sql. Every
# user_id must be an existing account.


def check_telemetry(data: dict[str, Any], user_id: str) -> list[dict[str, Any]]:
    """Evaluate a sync's telemetry and return only the alerts that are new.

    Re-syncing overlapping data finds the same events again; the UNIQUE
    (user_id, kind, started_at) constraint drops those so the user isn't
    alerted twice for one event.
    """
    findings = evaluate_heart_rate(
        extract_heart_rate(data), extract_exercise_intervals(data)
    )
    if not findings:
        return []
    new_alerts = []
    with connect("save alerts") as conn:
        for finding in findings:
            row = conn.execute(
                """
                INSERT INTO health_alerts (
                    user_id, kind, severity, title, message,
                    started_at, ended_at, peak_bpm
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, kind, started_at) DO NOTHING
                RETURNING *
                """,
                (
                    user_id,
                    finding.kind,
                    finding.severity,
                    finding.title,
                    finding.message,
                    finding.started_at.isoformat(),
                    finding.ended_at.isoformat(),
                    finding.peak_bpm,
                ),
            ).fetchone()
            if row is not None:  # None means this event was already saved
                new_alerts.append(row)
    return new_alerts


def list_alerts(user_id: str) -> list[dict[str, Any]]:
    with connect("load alerts") as conn:
        return conn.execute(
            "SELECT * FROM health_alerts WHERE user_id = %s ORDER BY started_at DESC, id DESC",
            (user_id,),
        ).fetchall()


def unacknowledged_count(user_id: str) -> int:
    with connect("count unread alerts") as conn:
        row = conn.execute(
            "SELECT count(*) AS n FROM health_alerts WHERE user_id = %s AND acknowledged = 0",
            (user_id,),
        ).fetchone()
    return row["n"]


def acknowledge(user_id: str, alert_id: int | None = None) -> None:
    """Mark one alert (or all of the user's alerts) as seen."""
    with connect("acknowledge alerts") as conn:
        if alert_id is None:
            conn.execute(
                "UPDATE health_alerts SET acknowledged = 1 WHERE user_id = %s", (user_id,)
            )
        else:
            conn.execute(
                "UPDATE health_alerts SET acknowledged = 1 WHERE user_id = %s AND id = %s",
                (user_id, alert_id),
            )


def get_alert_email(user_id: str) -> str | None:
    """The address saved on the Alerts page: None if never set, "" if turned off."""
    with connect("load alert email") as conn:
        row = conn.execute(
            "SELECT email FROM alert_settings WHERE user_id = %s", (user_id,)
        ).fetchone()
    return row["email"] if row else None


def set_alert_email(user_id: str, email: str) -> None:
    """Save the alert email address; "" turns email alerts off."""
    with connect("save alert email") as conn:
        conn.execute(
            """
            INSERT INTO alert_settings (user_id, email) VALUES (%s, %s)
            ON CONFLICT (user_id) DO UPDATE SET email = excluded.email
            """,
            (user_id, email.strip()),
        )
