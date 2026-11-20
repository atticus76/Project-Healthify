"""Tests for the NFR-01 response-time check (S3-01).

Spec: code/specs/features/S3-01-response-time-check.md

Tests that time the real interactions need TEST_DATABASE_URL and skip
without it. The rest use fake interactions and need no database.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend import alerts, auth_controller, reports
from backend.db import connect
from scripts import nfr01_response_times as check

SMALL = check.SeedSizes(alerts=60, goals=4, reports=3)
FRONTEND_APP = Path(__file__).resolve().parents[2] / "frontend" / "healthify"


def _fake(name: str, call, setup=None) -> check.Interaction:
    return check.Interaction(page="/fake", kind="action", name=name, call=call, setup=setup)


@pytest.fixture
def live_url_elsewhere(test_db, monkeypatch: pytest.MonkeyPatch) -> None:
    """test_db points DATABASE_URL at the test database; the check expects the
    live URL there and points it at the test database itself."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://live.invalid/never-used")


def _users_in_test_database(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    with connect("list users") as conn:
        return [row["username"] for row in conn.execute("SELECT username FROM users").fetchall()]


# Scenario: Every interaction meets the budget with a large account
# Scenario: Cold loads are reported separately
# Scenario: The seed is checked before timing
def test_every_interaction_meets_the_budget_with_a_large_account(live_url_elsewhere):
    report = check.run(runs=3, budget_ms=1000, sizes=SMALL)

    assert report.seeded == {
        "alerts": 60, "goals": 4, "progress": 4, "reports": 3,
        "profiles": 1, "preferences": 1, "snapshots": 1,
    }
    pages = {result.page for result in report.results}
    assert {"/login", "/", "/profile", "/goals", "/alerts", "/reports", "/devices", "/emulator"} <= pages
    for result in report.results:
        assert result.error is None, f"{result.name}: {result.error}"
        assert result.cold_ms is not None
        assert len(result.samples_ms) == 3  # the cold run isn't one of them
        assert result.status == "PASS", f"{result.name} p95 {result.p95_ms:.0f} ms"
    assert check.exit_code(report.results) == 0


# Scenario: An interaction is over budget
def test_an_interaction_over_budget_fails():
    results = check.measure_all(
        [_fake("quick", lambda: None), _fake("slow", lambda: time.sleep(0.03))],
        runs=3,
        budget_ms=20,
    )

    assert [r.status for r in results] == ["PASS", "FAIL"]
    assert check.exit_code(results) == 1
    assert "slow" in check.format_slowest(results)


def test_p95_is_the_nearest_rank_of_the_timed_runs():
    result = check.Result(page="/", kind="load", name="x", budget_ms=1000, cold_ms=5000.0,
                          samples_ms=[float(n) for n in range(20, 0, -1)])

    assert result.p95_ms == 19.0  # 19th of 20 when sorted
    assert result.median_ms == 10.5
    assert result.max_ms == 20.0  # the 5 s cold run isn't counted
    assert result.status == "PASS"


# Scenario: Cold loads are reported separately
def test_the_cold_run_is_timed_but_not_counted():
    durations = iter([0.05, 0.0, 0.0])

    result = check.measure(_fake("warms up", lambda: time.sleep(next(durations))),
                           runs=2, budget_ms=40)

    assert result.cold_ms >= 50
    assert len(result.samples_ms) == 2
    assert result.status == "PASS"


# Scenario: An interaction raises an error
def test_an_interaction_that_raises_is_an_error_and_the_rest_still_run():
    def broken():
        raise RuntimeError("boom")

    results = check.measure_all([_fake("broken", broken), _fake("fine", lambda: None)],
                                runs=2, budget_ms=1000)

    assert results[0].status == "ERROR"
    assert "boom" in results[0].error
    assert results[1].status == "PASS"
    assert check.exit_code(results) == 1


# Scenario: Unsafe or missing test database
@pytest.mark.parametrize("test_url, live_url", [("", "postgresql://live"), ("postgresql://same", "postgresql://same")])
def test_unsafe_or_missing_test_database_is_refused(monkeypatch, test_url, live_url):
    monkeypatch.setenv("TEST_DATABASE_URL", test_url)
    monkeypatch.setenv("DATABASE_URL", live_url)
    seeded = []
    monkeypatch.setattr(check, "seed_large_user", lambda *args: seeded.append(args))

    with pytest.raises(check.CheckRefused):
        check.run(runs=1, budget_ms=1000, sizes=SMALL)

    assert seeded == []
    assert check.main(["--runs", "1"]) == 2


# Scenario: The perf user is always removed
def test_the_perf_user_is_removed_even_when_an_interaction_raises(live_url_elsewhere, monkeypatch):
    def interactions(context):
        def broken():
            raise RuntimeError("boom")
        return [_fake("broken", broken)]

    report = check.run(runs=1, budget_ms=1000, sizes=SMALL, build=interactions)

    assert report.results[0].status == "ERROR"
    assert report.username.startswith("perf_nfr01_")
    assert report.username not in _users_in_test_database(monkeypatch)


def test_the_check_aborts_if_the_database_changes_mid_run(live_url_elsewhere, monkeypatch):
    def interactions(context):
        def switch_database():
            monkeypatch.setenv("DATABASE_URL", "postgresql://live.invalid/never-used")
        return [_fake("switches database", switch_database)]

    with pytest.raises(check.UnsafeDatabase):
        check.run(runs=1, budget_ms=1000, sizes=SMALL, build=interactions)


# Scenario: The check isn't reachable from the web app
def test_the_check_isnt_reachable_from_the_web_app():
    importers = [
        path for path in FRONTEND_APP.rglob("*.py")
        if "nfr01_response_times" in path.read_text(encoding="utf-8")
    ]
    assert importers == []


# Scenario: Report refresh reads only the alerts in the report period
@pytest.fixture
def user_with_old_and_new_alerts(test_db) -> tuple[str, datetime]:
    auth_controller.register("periodic", "", "Testpass1!")
    reports.save_preferences("periodic", "weekly", "periodic@example.com")  # 7-day report
    now =datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)
    rows = [
        ("periodic", alerts.KIND_HIGH_HEART_RATE, alerts.SEVERITY_URGENT, f"Alert {days}d",
         "m", (now - timedelta(days=days)).isoformat(), (now - timedelta(days=days)).isoformat())
        for days in (1, 6, 8, 30)
    ]
    with connect("seed alerts") as conn:
        conn.cursor().executemany(
            "INSERT INTO health_alerts (user_id, kind, severity, title, message, started_at, ended_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            rows,
        )
    return "periodic", now


def test_list_alerts_since_returns_only_alerts_in_the_period(user_with_old_and_new_alerts):
    user, now = user_with_old_and_new_alerts

    recent = alerts.list_alerts_since(user, (now - timedelta(days=7)).isoformat())

    assert [row["title"] for row in recent] == ["Alert 1d", "Alert 6d"]


def test_report_refresh_reads_only_the_alerts_in_the_report_period(user_with_old_and_new_alerts, monkeypatch):
    user, now = user_with_old_and_new_alerts
    monkeypatch.setattr(alerts, "list_alerts", lambda user_id: pytest.fail("loaded every alert"))

    report = reports.generate_report(user, telemetry={}, now=now, persist=False)

    assert [item["title"] for item in report["content"]["alerts"]] == ["Alert 1d", "Alert 6d"]
