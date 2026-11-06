"""Shared PostgreSQL access for Healthify (S2-04).

Every module that reads or writes data uses `connect()`:

    from backend.db import connect

    with connect("save goal") as conn:
        row = conn.execute(
            "INSERT INTO health_goals (...) VALUES (%s, ...) RETURNING id", (...)
        ).fetchone()

Rows come back as dicts (`row["id"]`). The block is one transaction: it
commits when the block finishes and rolls back if it raises. Connections come
from a small pool and are reused, because opening a new one to Supabase takes
~200 ms (NFR-01: pages under 1 s).

The database is Supabase, used only as a plain PostgreSQL server. The
connection string is DATABASE_URL in the repo-root .env (see .env.example).
"""

from __future__ import annotations

import atexit
import logging
import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolTimeout

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

# Pool settings. Supabase's free-plan pooler allows only a limited number of
# connections per project, and up to four teammates may run the app against
# the same project, so each app keeps at most a few.
POOL_MIN_SIZE = 1
POOL_MAX_SIZE = 4
POOL_WAIT_SECONDS = 10  # how long a request waits for a connection before failing
POOL_MAX_IDLE_SECONDS = 300  # close extra connections idle this long

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


_pools: dict[str, ConnectionPool] = {}
_pools_lock = threading.Lock()


def _pool(url: str) -> ConnectionPool:
    """One pool per DATABASE_URL (tests switch between databases)."""
    with _pools_lock:
        pool = _pools.get(url)
        if pool is None:
            pool = ConnectionPool(
                url,
                min_size=POOL_MIN_SIZE,
                max_size=POOL_MAX_SIZE,
                max_idle=POOL_MAX_IDLE_SECONDS,
                kwargs={
                    "row_factory": dict_row,
                    "connect_timeout": CONNECT_TIMEOUT_SECONDS,
                    # Automatic prepared statements can collide behind
                    # Supabase's own pooler once connections are reused.
                    "prepare_threshold": None,
                },
                # Test each connection before handing it out, so one that
                # Supabase dropped (e.g. after a pause) is replaced instead of
                # failing the request.
                check=ConnectionPool.check_connection,
                name="healthify",
                open=True,
            )
            _pools[url] = pool
        return pool


def close_pools() -> None:
    """Close every pooled connection (runs automatically at exit)."""
    with _pools_lock:
        pools = list(_pools.values())
        _pools.clear()
    for pool in pools:
        pool.close()


atexit.register(close_pools)


@contextmanager
def connect(operation: str = "database query") -> Iterator[psycopg.Connection]:
    """Borrow a pooled connection for one unit of work (one transaction).

    `operation` is a short description such as "load goals", logged if
    anything fails. Any database failure is raised as `DatabaseError`; there is
    deliberately no fallback to local files.
    """
    pool = _pool(database_url())
    try:
        # Commits on success, rolls back on error, then returns the
        # connection to the pool (or discards it if it's broken).
        with pool.connection(timeout=POOL_WAIT_SECONDS) as conn:
            yield conn
    except PoolTimeout as exc:
        log.error("Database unreachable during %r: %s", operation, exc)
        raise DatabaseError(operation) from exc
    except psycopg.Error as exc:
        log.error("Database error during %r: %s", operation, exc)
        raise DatabaseError(operation) from exc


def create_schema() -> None:
    """Create any missing tables. Safe to run more than once."""
    with connect("create schema") as conn:
        conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
