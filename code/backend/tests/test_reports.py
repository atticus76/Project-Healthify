"""Health reports in the cloud report_preferences / health_reports tables (S2-04).

Runs against healthify-test and is skipped if TEST_DATABASE_URL isn't set.
Time is controlled by patching reports._now (and goals._now for goals).
"""

import smtplib
from datetime import datetime, timedelta, timezone

import pytest

from backend import alerts, auth_controller, db, email_alerts, goals, reports
from backend.telemetry_emulator import generate_fitbit_data

pytestmark = pytest.mark.usefixtures("test_db")

NOW = datetime(2026, 11, 4, 18, 0, tzinfo=timezone.utc)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch):
    class Clock:
        now = NOW

    monkeypatch.setattr(reports, "_now", lambda: Clock.now)
    monkeypatch.setattr(goals, "_now", lambda: Clock.now)
    return Clock


@pytest.fixture
def user() -> str:
    auth_controller.register("user", "", "Testpass1!")
    return "user"


@pytest.fixture
def sent_emails(monkeypatch: pytest.MonkeyPatch) -> list:
    sent = []
    monkeypatch.setattr(email_alerts, "send", lambda message: sent.append(message))
    return sent


# --- Preferences ------------------------------------------------------------


def test_no_preferences_until_saved(user):
    assert reports.get_preferences(user) is None


def test_preferences_are_saved_and_replaced(user, clock):
    reports.save_preferences(user, "daily", " me@example.com ")
    reports.save_preferences(user, "weekly", "me@example.com")
    prefs = reports.get_preferences(user)
    assert (prefs["frequency"], prefs["email"]) == ("weekly", "me@example.com")
    assert prefs["updated_at"] == NOW.isoformat()


def test_invalid_preferences_are_rejected(user):
    with pytest.raises(ValueError, match="daily or weekly"):
        reports.save_preferences(user, "hourly", "me@example.com")
    with pytest.raises(ValueError, match="email"):
        reports.save_preferences(user, "daily", "not-an-email")
    assert reports.get_preferences(user) is None


def test_preferences_need_an_existing_account():
    with pytest.raises(db.DatabaseError):
        reports.save_preferences("ghost", "daily", "me@example.com")


# --- Generating reports -----------------------------------------------------


def test_report_includes_goals_and_recent_alerts(user, clock):
    goals.add_goal(user, goals.GOAL_DAILY_STEPS, 1_000, False)
    goals.record_steps(user, 250)
    spike = generate_fitbit_data("Medium", NOW - timedelta(hours=2), scenario="heart-rate-spike")
    alerts.check_telemetry(spike, user)
    old_spike = generate_fitbit_data("Medium", NOW - timedelta(days=3), scenario="heart-rate-spike")
    alerts.check_telemetry(old_spike, user)

    report = reports.generate_report(user, telemetry={})

    assert report["id"] > 0
    assert report["period_end"] == NOW.isoformat()
    assert report["period_start"] == (NOW - timedelta(days=1)).isoformat()  # daily by default
    content = report["content"]
    assert content["goals"] == [{"target": 1_000, "steps": 250, "status": "in_progress", "percent": 25}]
    assert len(content["alerts"]) == 1  # the 3-day-old alert is outside the period
    assert content["metrics"]["available"] is False


def test_weekly_reports_cover_seven_days(user, clock):
    reports.save_preferences(user, "weekly", "me@example.com")
    report = reports.generate_report(user, telemetry={})
    assert report["period_start"] == (NOW - timedelta(days=7)).isoformat()


def test_telemetry_is_summarized_when_present(user, clock):
    data = generate_fitbit_data("Medium", NOW)
    metrics = reports.generate_report(user, telemetry=data)["content"]["metrics"]
    assert metrics["available"] is True
    assert metrics["steps_points"] > 0


def test_preview_reports_are_not_saved(user, clock):
    preview = reports.generate_report(user, telemetry={}, persist=False)
    assert preview["id"] == 0
    assert reports.get_report(user) is None


def test_latest_report_is_returned(user, clock):
    first = reports.generate_report(user, telemetry={})
    clock.now = NOW + timedelta(hours=1)
    second = reports.generate_report(user, telemetry={})
    assert reports.get_report(user)["id"] == second["id"]
    assert reports.get_report(user, first["id"])["content"] == first["content"]


def test_users_cant_read_each_others_reports(user, clock):
    auth_controller.register("other", "", "Testpass1!")
    theirs = reports.generate_report("other", telemetry={})
    assert reports.get_report(user) is None
    assert reports.get_report(user, theirs["id"]) is None


# --- Delivering reports -----------------------------------------------------


def test_delivery_without_preferences_does_nothing(user, clock, sent_emails):
    report = reports.generate_report(user, telemetry={})
    assert reports.deliver_report(user, report)["delivery_status"] == "not_sent"
    assert sent_emails == []


def test_delivered_report_is_marked_sent(user, clock, sent_emails):
    reports.save_preferences(user, "daily", "me@example.com")
    report = reports.deliver_report(user, reports.generate_report(user, telemetry={}))
    assert report["delivery_status"] == "sent"
    assert sent_emails[0]["To"] == "me@example.com"
    assert reports.get_report(user)["delivery_status"] == "sent"


def test_failed_delivery_is_recorded(user, clock, monkeypatch):
    def fail(message):
        raise smtplib.SMTPConnectError(421, "down")

    monkeypatch.setattr(email_alerts, "send", fail)
    reports.save_preferences(user, "daily", "me@example.com")
    reports.deliver_report(user, reports.generate_report(user, telemetry={}))
    saved = reports.get_report(user)
    assert saved["delivery_status"] == "failed"
    assert "down" in saved["delivery_error"]


# --- Scheduling -------------------------------------------------------------


def test_scheduler_sends_due_reports_for_every_user(user, clock, sent_emails):
    for name in ("second", "third"):
        auth_controller.register(name, "", "Testpass1!")
    reports.save_preferences(user, "daily", "user@example.com")
    reports.save_preferences("second", "weekly", "second@example.com")
    # "third" has no preferences, so never gets reports.

    assert sorted(reports.send_due_reports()) == ["second", "user"]
    assert reports.send_due_reports() == []  # not due again until the next period

    clock.now = NOW + timedelta(days=2)
    assert reports.send_due_reports() == ["user"]  # weekly isn't due yet
    clock.now = NOW + timedelta(days=8)
    assert sorted(reports.send_due_reports()) == ["second", "user"]
    assert len(sent_emails) == 5


def test_reports_no_longer_use_sqlite_or_a_demo_user():
    from backend import google_health

    assert not hasattr(reports, "DATABASE_PATH")
    assert not hasattr(google_health, "DEMO_USER_ID")
