"""Shared PostgreSQL access for Healthify (S2-04).

Every module that reads or writes data uses `connect()`:

    from backend.db import connect

    with connect("save goal") as conn:
        row = conn.execute(
            "INSERT INTO health_goals (...) VALUES (%s, ...) RETURNING id", (...)
        ).fetchone()

Rows come back as dicts (`row["id"]`). The connection commits when the block
finishes, rolls back if it raises, and is always closed.

The database is Supabase, used only as a plain PostgreSQL server. The
connection string is DATABASE_URL in the repo-root .env (see .env.example).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = Path(__file__).with_name("schema.sql")

load_dotenv(REPO_ROOT / ".env")

log = logging.getLogger(__name__)

UNREACHABLE_MESSAGE = "Couldn't reach the database. Try again in a moment."
MISSING_URL_MESSAGE = (
    "DATABASE_URL is required. Add it to .env in the repo root "
    "(see .env.example for the format)."
)
CONNECT_TIMEOUT_SECONDS = 10

# Every table in schema.sql.
TABLES = (
    "users",
    "health_profiles",
    "health_goals",
    "goal_progress",
    "health_alerts",
    "alert_settings",
    "report_preferences",
    "health_reports",
    "oauth_pending",
    "google_connections",
    "telemetry_snapshots",
)


class DatabaseError(Exception):
    """The database couldn't be reached or a query failed.

    `str(error)` is the message to show the user. `operation` says what the
    app was trying to do, for the log.
    """

    def __init__(self, operation: str) -> None:
        super().__init__(UNREACHABLE_MESSAGE)
        self.operation = operation


class MissingDatabaseURL(RuntimeError):
    """DATABASE_URL isn't set, so the app can't run."""

    def __init__(self) -> None:
        super().__init__(MISSING_URL_MESSAGE)


def database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise MissingDatabaseURL()
    return url


def require_database_url() -> None:
    """Stop the app at startup with a clear message if DATABASE_URL is missing."""
    try:
        database_url()
    except MissingDatabaseURL as exc:
        raise SystemExit(str(exc)) from None


@contextmanager
def connect(operation: str = "database query") -> Iterator[psycopg.Connection]:
    """Open a connection for one unit of work.

    `operation` is a short description such as "load goals", logged if
    anything fails. Any database failure is raised as `DatabaseError`; there is
    deliberately no fallback to local files.
    """
    url = database_url()
    try:
        conn = psycopg.connect(
            url, row_factory=dict_row, connect_timeout=CONNECT_TIMEOUT_SECONDS
        )
    except psycopg.Error as exc:
        log.error("Database unreachable during %r: %s", operation, exc)
        raise DatabaseError(operation) from exc
    try:
        with conn:  # commits on success, rolls back on error, then closes
            yield conn
    except psycopg.Error as exc:
        log.error("Database error during %r: %s", operation, exc)
        raise DatabaseError(operation) from exc


def create_schema() -> None:
    """Create any missing tables. Safe to run more than once."""
    with connect("create schema") as conn:
        conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
