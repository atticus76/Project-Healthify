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
from backend.db import init as db_init


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


def test_app_startup_continues_with_database_url(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://example")
    db.require_database_url()


def test_init_script_reports_missing_database_url(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert db_init.main() == 1
    assert "DATABASE_URL is required" in capsys.readouterr().err


def test_unreachable_database_shows_message_and_logs_operation(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    # Port 1 on localhost refuses connections immediately.
    monkeypatch.setenv("DATABASE_URL", "postgresql://nobody:nothing@127.0.0.1:1/none")
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


def test_rows_come_back_as_dicts(test_db):
    with db.connect() as conn:
        assert conn.execute("SELECT 1 AS one").fetchone() == {"one": 1}


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


def test_usernames_are_case_sensitive(test_db):
    with db.connect() as conn:
        _add_user(conn, "alice")
        _add_user(conn, "Alice")
        assert conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 2


def test_duplicate_username_is_rejected(test_db):
    with db.connect() as conn:
        _add_user(conn, "alice")
    with pytest.raises(db.DatabaseError):
        with db.connect() as conn:
            _add_user(conn, "alice")


def test_many_users_can_have_no_email_but_emails_are_unique(test_db):
    with db.connect() as conn:
        _add_user(conn, "alice")
        _add_user(conn, "bob")
        _add_user(conn, "carol", "carol@example.com")
    with pytest.raises(db.DatabaseError):
        with db.connect() as conn:
            _add_user(conn, "dave", "carol@example.com")


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


def test_data_needs_an_existing_user(test_db):
    with pytest.raises(db.DatabaseError):
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO alert_settings (user_id, email) VALUES ('ghost', 'g@example.com')"
            )


def test_default_timestamps_match_the_sqlite_format(test_db):
    with db.connect() as conn:
        _add_user(conn, "alice")
        created = conn.execute("SELECT created_at FROM users").fetchone()["created_at"]
    # SQLite's CURRENT_TIMESTAMP gives 'YYYY-MM-DD HH:MM:SS'.
    assert len(created) == 19 and created[4] == "-" and created[10] == " "


def test_json_columns_round_trip(test_db):
    state = {"theme": "dark", "telemetry_enabled": True, "device_name": "Pixel Watch"}
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, app_state) VALUES ('alice', 'x', %s)",
            (Jsonb(state),),
        )
        assert conn.execute("SELECT app_state FROM users").fetchone()["app_state"] == state
