"""Shared fixtures for backend tests."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from backend import db


@pytest.fixture(scope="session")
def _test_database_url() -> str:
    url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("TEST_DATABASE_URL isn't set in .env; skipping database tests.")
    if url == os.getenv("DATABASE_URL", "").strip():
        pytest.fail(
            "TEST_DATABASE_URL is the same as DATABASE_URL. Tests wipe their "
            "database, so point TEST_DATABASE_URL at the healthify-test project."
        )
    return url


@pytest.fixture(scope="session")
def _test_schema(_test_database_url: str) -> str:
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DATABASE_URL", _test_database_url)
        db.create_schema()
    return _test_database_url


@pytest.fixture
def test_db(_test_schema: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Point the app at healthify-test with every table empty.

    Code under test that calls `backend.db.connect()` uses the test database.
    """
    monkeypatch.setenv("DATABASE_URL", _test_schema)
    with db.connect("reset test database") as conn:
        conn.execute(f"TRUNCATE {', '.join(db.TABLES)} RESTART IDENTITY CASCADE")
    # The latest-telemetry cache would otherwise carry over between tests.
    from backend import telemetry_store

    telemetry_store._reset_cache()
    yield
