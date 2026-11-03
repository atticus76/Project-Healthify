"""SQLite persistence for Google connections and in-flight OAuth requests.

AI-GENERATED (Claude) for the device-connection demo.

Two tables in the same healthtrack.db the profile feature uses (gitignored):

- oauth_pending: state -> PKCE verifier, kept between "user clicks Connect"
  and "Google redirects back". Stored server-side (not in Reflex state) so a
  dev-server reload in the middle of the flow doesn't lose it.
- google_connections: one row per user with their tokens and sync status.

TODO (NFR-03): refresh tokens are stored in plaintext. Encrypt at rest before
this goes anywhere real.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

DATABASE_PATH = Path(__file__).resolve().parent / "healthtrack.db"

# Pending requests older than this are treated as abandoned.
PENDING_TTL_S = 10 * 60

STATUS_CONNECTED = "connected"
STATUS_RECONNECT = "reconnect_required"


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    """Commit on success, roll back on error, and always close the file.

    A bare `with sqlite3.connect()` only commits; the open handle keeps the
    file locked on Windows.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS oauth_pending (
            state TEXT PRIMARY KEY,
            code_verifier TEXT NOT NULL,
            user_id TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS google_connections (
            user_id TEXT PRIMARY KEY,
            email TEXT,
            access_token TEXT NOT NULL,
            refresh_token TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            scope TEXT,
            status TEXT NOT NULL,
            device_name TEXT,
            connected_at INTEGER NOT NULL,
            last_sync_at INTEGER
        )
        """
    )
    try:
        with conn:
            yield conn
    finally:
        conn.close()


# --- pending OAuth requests ---------------------------------------------------

def save_pending(state: str, code_verifier: str, user_id: str) -> None:
    now = int(time.time())
    with _connect() as conn:
        conn.execute("DELETE FROM oauth_pending WHERE created_at < ?", (now - PENDING_TTL_S,))
        conn.execute(
            "INSERT INTO oauth_pending (state, code_verifier, user_id, created_at) VALUES (?, ?, ?, ?)",
            (state, code_verifier, user_id, now),
        )


def pop_pending(state: str) -> dict[str, Any] | None:
    """Return and delete the pending request for this state (single use), or None."""
    with _connect() as conn:
        row = conn.execute("SELECT * FROM oauth_pending WHERE state = ?", (state,)).fetchone()
        if row is None:
            return None
        conn.execute("DELETE FROM oauth_pending WHERE state = ?", (state,))
    if row["created_at"] < time.time() - PENDING_TTL_S:
        return None
    return dict(row)


# --- connections ----------------------------------------------------------------

def save_connection(user_id: str, tokens: dict[str, Any]) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO google_connections (
                user_id, email, access_token, refresh_token, expires_at,
                scope, status, connected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                email = excluded.email,
                access_token = excluded.access_token,
                refresh_token = excluded.refresh_token,
                expires_at = excluded.expires_at,
                scope = excluded.scope,
                status = excluded.status,
                connected_at = excluded.connected_at
            """,
            (
                user_id,
                tokens.get("email", ""),
                tokens["access_token"],
                tokens["refresh_token"],
                tokens["expires_at"],
                tokens.get("scope", ""),
                STATUS_CONNECTED,
                int(time.time()),
            ),
        )


def get_connection(user_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM google_connections WHERE user_id = ?", (user_id,)
        ).fetchone()
    return dict(row) if row else None


def update_access_token(user_id: str, access_token: str, expires_at: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE google_connections SET access_token = ?, expires_at = ?, status = ? WHERE user_id = ?",
            (access_token, expires_at, STATUS_CONNECTED, user_id),
        )


def mark_reconnect_required(user_id: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE google_connections SET status = ? WHERE user_id = ?",
            (STATUS_RECONNECT, user_id),
        )


def record_sync(user_id: str, device_name: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE google_connections SET last_sync_at = ?, device_name = COALESCE(NULLIF(?, ''), device_name) WHERE user_id = ?",
            (int(time.time()), device_name, user_id),
        )


def delete_connection(user_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM google_connections WHERE user_id = ?", (user_id,))
