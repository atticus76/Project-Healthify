"""Latest telemetry per user: kept in memory, saved to the cloud now and then (S2-04).

The emulator produces ~176 KB of telemetry and the Emulator and Reports pages
refresh every second. Saving every refresh to Supabase would be ~600 MB an hour
per open tab, so (decided 2026-11-05):

- The live, per-second data lives in memory in this process.
- It's saved to the cloud `telemetry_snapshots` table at most once every
  SAVE_EVERY_SECONDS per user and source, and right away when `force=True`
  (Google syncs, turning the emulator off).
- Reads use memory first and fall back to the cloud after a restart or on
  another computer. "Nothing saved" is remembered too, so a page polling every
  second doesn't query the database every second.

A process won't see a snapshot another computer saves after it first looked;
a user is normally on one computer at a time. History is S3-04.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

from psycopg.types.json import Jsonb

from backend.db import DatabaseError, connect

log = logging.getLogger(__name__)

SAVE_EVERY_SECONDS = 60
SOURCES = ("emulator", "google")

_lock = threading.Lock()
# user_id -> latest telemetry (None = checked the cloud, nothing there)
_latest: dict[str, dict[str, Any] | None] = {}
# (user_id, source) -> when it was last saved to the cloud (time.monotonic())
_last_saved: dict[tuple[str, str], float] = {}


def _clock() -> float:
    return time.monotonic()


def _reset_cache() -> None:
    """Forget everything in memory (what a server restart does). For tests."""
    with _lock:
        _latest.clear()
        _last_saved.clear()


def save(user_id: str, data: dict[str, Any], source: str = "emulator", force: bool = False) -> None:
    """Make `data` the user's latest telemetry, saving it to the cloud if due.

    Never raises for a database failure: the live data stays in memory and the
    save is retried on the next call.
    """
    if source not in SOURCES:
        raise ValueError(f"Unknown telemetry source: {source}")
    key = (user_id, source)
    with _lock:
        _latest[user_id] = data
        last = _last_saved.get(key)
        due = force or last is None or _clock() - last >= SAVE_EVERY_SECONDS
    if not due:
        return
    try:
        with connect("save telemetry snapshot") as conn:
            conn.execute(
                """
                INSERT INTO telemetry_snapshots (user_id, source, data, synced_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, source) DO UPDATE SET
                    data = excluded.data,
                    synced_at = excluded.synced_at
                """,
                (user_id, source, Jsonb(data), datetime.now(timezone.utc).isoformat()),
            )
    except DatabaseError:
        log.warning("Couldn't save the telemetry snapshot for %r; will retry.", user_id)
        return
    with _lock:
        _last_saved[key] = _clock()


def get_latest(user_id: str) -> dict[str, Any] | None:
    """The user's latest telemetry from any source, or None."""
    with _lock:
        if user_id in _latest:
            return _latest[user_id]
    with connect("load telemetry snapshot") as conn:
        row = conn.execute(
            "SELECT data FROM telemetry_snapshots WHERE user_id = %s "
            "ORDER BY synced_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    data = row["data"] if row else None
    with _lock:
        _latest.setdefault(user_id, data)
        return _latest[user_id]


def clear(user_id: str, source: str = "emulator") -> None:
    """Delete one source's snapshot (e.g. when the emulator is turned off)."""
    with connect("delete telemetry snapshot") as conn:
        conn.execute(
            "DELETE FROM telemetry_snapshots WHERE user_id = %s AND source = %s",
            (user_id, source),
        )
    with _lock:
        _latest.pop(user_id, None)  # next read falls back to whatever's left
        _last_saved.pop((user_id, source), None)
