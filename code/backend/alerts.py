"""Health abnormality alerts (US-04 / FR-02).

Spec: code/specs/features/S2-03-health-abnormality-alerts.md

Checks synced telemetry (Google Health API or the emulator, which share the
same JSON shape) for a sustained high heart rate and for gaps in the data.
Alerts are stored in the same healthtrack.db the profile feature uses so the
Alerts page can show a history. Delivery (toast + browser notification) is the
frontend's job; this module only decides what is abnormal and records it.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DATABASE_PATH = Path(__file__).resolve().parent / "healthtrack.db"

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

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    """Commit on success, roll back on error, and always close the file."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS health_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            severity TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT NOT NULL,
            peak_bpm INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            acknowledged INTEGER NOT NULL DEFAULT 0,
            UNIQUE (user_id, kind, started_at)
        )
        """
    )
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def check_telemetry(data: dict[str, Any], user_id: str) -> list[dict[str, Any]]:
    """Evaluate a sync's telemetry and return only the alerts that are new.

    Re-syncing overlapping data finds the same events again; the UNIQUE
    constraint drops those so the user isn't alerted twice for one event.
    """
    findings = evaluate_heart_rate(
        extract_heart_rate(data), extract_exercise_intervals(data)
    )
    new_ids = []
    with _connect() as conn:
        for finding in findings:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO health_alerts (
                    user_id, kind, severity, title, message,
                    started_at, ended_at, peak_bpm
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
            )
            if cursor.rowcount:
                new_ids.append(cursor.lastrowid)
        if not new_ids:
            return []
        rows = conn.execute(
            f"SELECT * FROM health_alerts WHERE id IN ({','.join('?' * len(new_ids))}) ORDER BY id",
            new_ids,
        ).fetchall()
    return [dict(row) for row in rows]


def list_alerts(user_id: str) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM health_alerts WHERE user_id = ? ORDER BY started_at DESC, id DESC",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def unacknowledged_count(user_id: str) -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM health_alerts WHERE user_id = ? AND acknowledged = 0",
            (user_id,),
        ).fetchone()
    return row[0]


def acknowledge(user_id: str, alert_id: int | None = None) -> None:
    """Mark one alert (or all of the user's alerts) as seen."""
    with _connect() as conn:
        if alert_id is None:
            conn.execute("UPDATE health_alerts SET acknowledged = 1 WHERE user_id = ?", (user_id,))
        else:
            conn.execute(
                "UPDATE health_alerts SET acknowledged = 1 WHERE user_id = ? AND id = ?",
                (user_id, alert_id),
            )
