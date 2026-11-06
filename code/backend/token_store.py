"""Cloud storage for Google connections and in-flight OAuth requests (S2-04).

AI-GENERATED (Claude) for the device-connection demo; ported from SQLite to
PostgreSQL (Supabase) for S2-04.

Two tables, created by code/backend/db/schema.sql:

- oauth_pending: state -> PKCE verifier, kept between "user clicks Connect"
  and "Google redirects back". Stored server-side (not in Reflex state) so a
  dev-server reload in the middle of the flow doesn't lose it.
- google_connections: one row per user with their tokens and sync status.

Every user_id must be an existing account (users.username).

TODO (NFR-03, S3-02): tokens are stored in plaintext. Encrypt at rest.
"""

from __future__ import annotations

import time
from typing import Any

from backend.db import connect

# Pending requests older than this are treated as abandoned.
PENDING_TTL_S = 10 * 60

STATUS_CONNECTED = "connected"
STATUS_SYNC_FAILED = "sync_failed"  # last sync failed; retrying on a backoff schedule
STATUS_RECONNECT = "reconnect_required"  # access expired or revoked; never retried automatically


# --- pending OAuth requests ---------------------------------------------------

def save_pending(state: str, code_verifier: str, user_id: str) -> None:
    now = int(time.time())
    with connect("start Google connection") as conn:
        conn.execute("DELETE FROM oauth_pending WHERE created_at < %s", (now - PENDING_TTL_S,))
        conn.execute(
            "INSERT INTO oauth_pending (state, code_verifier, user_id, created_at) VALUES (%s, %s, %s, %s)",
            (state, code_verifier, user_id, now),
        )


def pop_pending(state: str) -> dict[str, Any] | None:
    """Return and delete the pending request for this state (single use), or None."""
    with connect("finish Google connection") as conn:
        # One statement, so two callbacks with the same state can't both get it.
        row = conn.execute(
            "DELETE FROM oauth_pending WHERE state = %s RETURNING *", (state,)
        ).fetchone()
    if row is None or row["created_at"] < time.time() - PENDING_TTL_S:
        return None
    return row


# --- connections ----------------------------------------------------------------

def save_connection(user_id: str, tokens: dict[str, Any]) -> None:
    with connect("save Google connection") as conn:
        conn.execute(
            """
            INSERT INTO google_connections (
                user_id, email, access_token, refresh_token, expires_at,
                scope, status, connected_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                email = excluded.email,
                access_token = excluded.access_token,
                refresh_token = excluded.refresh_token,
                expires_at = excluded.expires_at,
                scope = excluded.scope,
                status = excluded.status,
                connected_at = excluded.connected_at,
                next_sync_at = NULL,
                sync_failures = 0,
                last_sync_error = ''
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
    with connect("load Google connection") as conn:
        return conn.execute(
            "SELECT * FROM google_connections WHERE user_id = %s", (user_id,)
        ).fetchone()


def update_access_token(user_id: str, access_token: str, expires_at: int) -> None:
    with connect("save refreshed Google token") as conn:
        conn.execute(
            "UPDATE google_connections SET access_token = %s, expires_at = %s, status = %s WHERE user_id = %s",
            (access_token, expires_at, STATUS_CONNECTED, user_id),
        )


def mark_reconnect_required(user_id: str) -> None:
    with connect("mark Google reconnect required") as conn:
        conn.execute(
            "UPDATE google_connections SET status = %s WHERE user_id = %s",
            (STATUS_RECONNECT, user_id),
        )


def record_sync(user_id: str, device_name: str, next_sync_at: int | None = None) -> None:
    """A sync succeeded: clear any failure state and schedule the next one."""
    with connect("record Google sync") as conn:
        conn.execute(
            "UPDATE google_connections SET last_sync_at = %s, "
            "device_name = COALESCE(NULLIF(%s, ''), device_name), "
            "status = %s, sync_failures = 0, last_sync_error = '', next_sync_at = %s "
            "WHERE user_id = %s",
            (int(time.time()), device_name, STATUS_CONNECTED, next_sync_at, user_id),
        )


def record_sync_failure(user_id: str, error: str) -> int:
    """A sync failed: mark it (unless reconnect is already required) and return
    how many times in a row it has failed."""
    with connect("record failed Google sync") as conn:
        row = conn.execute(
            "UPDATE google_connections SET sync_failures = sync_failures + 1, "
            "last_sync_error = %s, "
            "status = CASE WHEN status = %s THEN status ELSE %s END "
            "WHERE user_id = %s RETURNING sync_failures",
            (error, STATUS_RECONNECT, STATUS_SYNC_FAILED, user_id),
        ).fetchone()
    return row["sync_failures"] if row else 0


def schedule_next_sync(user_id: str, next_sync_at: int) -> None:
    with connect("schedule Google sync") as conn:
        conn.execute(
            "UPDATE google_connections SET next_sync_at = %s WHERE user_id = %s",
            (next_sync_at, user_id),
        )


def due_for_sync(now: int) -> list[str]:
    """Users whose next sync is due. Reconnect-required connections are skipped."""
    with connect("find due Google syncs") as conn:
        rows = conn.execute(
            "SELECT user_id FROM google_connections "
            "WHERE status <> %s AND (next_sync_at IS NULL OR next_sync_at <= %s) "
            "ORDER BY user_id",
            (STATUS_RECONNECT, now),
        ).fetchall()
    return [row["user_id"] for row in rows]


def delete_connection(user_id: str) -> None:
    with connect("delete Google connection") as conn:
        conn.execute("DELETE FROM google_connections WHERE user_id = %s", (user_id,))
