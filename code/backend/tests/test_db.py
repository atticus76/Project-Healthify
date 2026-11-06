"""Tests for the shared database layer (S2-04).

The first two tests need no database. The rest run against healthify-test
(TEST_DATABASE_URL) and are skipped if it isn't set.
"""

from __future__ import annotations

import logging

import psycopg
import pytest
from psycopg.types.json import Jsonb

from backend import db


# --- No database needed ---------------------------------------------------


def test_missing_database_url_says_what_to_do(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(db.MissingDatabaseURL) as error:
        with db.connect():
            pass
    assert "DATABASE_URL is required" in str(error.value)
    assert ".env.example" in str(error.value)


def test_app_startup_stops_without_database_url(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(SystemExit) as stop:
        db.require_database_url()
    assert "DATABASE_URL is required" in str(stop.value)
    assert ".env.example" in str(stop.value)


def test_unreachable_database_shows_message_and_logs_operation(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    # Port 1 on localhost refuses connections immediately. Don't wait the full
    # default time for the pool to give up.
    monkeypatch.setenv("DATABASE_URL", "postgresql://nobody:nothing@127.0.0.1:1/none")
    monkeypatch.setattr(db, "POOL_WAIT_SECONDS", 2)
    with caplog.at_level(logging.ERROR, logger="backend.db"):
        with pytest.raises(db.DatabaseError) as error:
            with db.connect("load goals"):
                pass
    assert str(error.value) == "Couldn't reach the database. Try again in a moment."
    assert error.value.operation == "load goals"
    assert "load goals" in caplog.text


# --- Against healthify-test -----------------------------------------------


def _add_user(conn: psycopg.Connection, username: str, email: str | None = None) -> None:
    conn.execute(
        "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, 'x')",
        (username, email),
    )


def test_schema_can_be_applied_again(test_db):
    db.create_schema()
    db.create_schema()


def test_every_table_exists_with_row_level_security(test_db):
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT relname, relrowsecurity FROM pg_class "
            "WHERE relkind = 'r' AND relnamespace = 'public'::regnamespace"
        ).fetchall()
    found = {row["relname"]: row["relrowsecurity"] for row in rows}
    for table in db.TABLES:
        assert table in found, f"{table} is missing"
        assert found[table], f"{table} doesn't have row level security on"


def test_block_commits_when_it_finishes(test_db):
    with db.connect() as conn:
        _add_user(conn, "alice")
    with db.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 1


def test_block_rolls_back_when_it_raises(test_db):
    with pytest.raises(RuntimeError):
        with db.connect() as conn:
            _add_user(conn, "alice")
            raise RuntimeError("something went wrong after the insert")
    with db.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 0


def test_query_error_becomes_database_error(test_db):
    with pytest.raises(db.DatabaseError) as error:
        with db.connect("save goal") as conn:
            conn.execute("SELECT * FROM no_such_table")
    assert error.value.operation == "save goal"


def test_deleting_a_user_deletes_their_data(test_db):
    with db.connect() as conn:
        _add_user(conn, "alice")
        goal_id = conn.execute(
            "INSERT INTO health_goals (user_id, goal_type, target, deadline_at, created_at) "
            "VALUES ('alice', 'steps', 8000, '2026-12-01', '2026-11-05') RETURNING id"
        ).fetchone()["id"]
        conn.execute("INSERT INTO goal_progress (goal_id) VALUES (%s)", (goal_id,))
        conn.execute(
            "INSERT INTO telemetry_snapshots (user_id, source, data, synced_at) "
            "VALUES ('alice', 'emulator', %s, '2026-11-05')",
            (Jsonb({"steps": 1200}),),
        )
        conn.execute("DELETE FROM users WHERE username = 'alice'")
        for table in ("health_goals", "goal_progress", "telemetry_snapshots"):
            assert conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"] == 0


# --- Connection pool (NFR-01: a new Supabase connection costs ~200 ms) -------


def test_connections_are_reused(test_db):
    # pg_backend_pid() can't tell: Supabase's pooler reuses server processes
    # even for brand-new client connections. Count the app's own connections.
    with db.connect() as conn:  # warm up
        conn.execute("SELECT 1")
    pool = db._pool(db.database_url())
    opened_before = pool.get_stats().get("connections_num", 0)
    for _ in range(6):
        with db.connect() as conn:
            conn.execute("SELECT 1")
    assert pool.get_stats().get("connections_num", 0) == opened_before


def test_dropped_connection_does_not_break_the_next_request(test_db):
    with pytest.raises(db.DatabaseError):
        with db.connect("simulate a dropped connection") as conn:
            conn.execute("SELECT pg_terminate_backend(pg_backend_pid())")
    with db.connect() as conn:
        assert conn.execute("SELECT 1 AS one").fetchone() == {"one": 1}
