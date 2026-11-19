from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from backend import auth_controller, calories, db, google_health, profile_controller


def test_myplate_profile_and_plan_level(monkeypatch):
    request = MagicMock()
    request.return_value.json.return_value = {"calorie_level": 2200}
    monkeypatch.setattr(profile_controller.requests, "get", request)
    assert profile_controller.myplate_target("Female", 30, 165, 140, "Moderately active") == 2200
    assert request.call_args.kwargs["params"] == {
        "age": 30, "sex": "female", "height_cm": 165, "weight_kg": 63.503,
        "activity": "moderately-active",
    }
    assert profile_controller.myplate_target("Non-binary", 30, 165, 140, "Active") is None
    request.assert_called_once()


def test_device_rollup_contract(monkeypatch):
    monkeypatch.setattr(google_health.token_store, "get_connection",
                        lambda _: {"connected_at": 125, "last_sync_at": None})
    monkeypatch.setattr(google_health, "_now", lambda: 250)
    monkeypatch.setattr(google_health, "_access_token", lambda *args, **kwargs: "token")
    request = MagicMock()
    request.return_value.json.return_value = {"rollupDataPoints": []}
    monkeypatch.setattr(google_health.requests, "post", request)
    google_health._sync_calories("alice")
    assert request.call_args.args[0].endswith("/total-calories/dataPoints:rollUp")
    body = request.call_args.kwargs["json"]
    assert body["windowSize"] == "60s"
    assert datetime.fromisoformat(body["range"]["startTime"]).timestamp() == 120
    assert datetime.fromisoformat(body["range"]["endTime"]).timestamp() == 240


@pytest.mark.usefixtures("test_db")
def test_reset_overlap_and_repeated_fitbit_sync():
    user = "alice"
    auth_controller.register(user, "", "Testpass1!")
    point = {"startTime": "2026-01-01T00:00:00Z", "endTime": "2026-01-01T00:01:00Z",
             "totalCalories": {"kcalSum": 10}}
    with db.connect() as conn:
        conn.execute("""INSERT INTO calorie_emulator_sessions VALUES
                     (%s,'2026-01-01T00:00:30Z','2026-01-01T00:01:00Z',2)""", (user,))
        calories.record_device_samples(conn, user, [point, point], 0)
    calories.add_food(user, 120)
    before = calories.summary(user)
    assert before["burned"] == 6 and before["consumed"] == 120
    calories.reset(user)
    with db.connect() as conn:
        calories.record_device_samples(conn, user, [point], 0)
    after = calories.summary(user)
    assert after["burned"] == after["consumed"] == 0


@pytest.mark.parametrize("amount,status", [(499, "complete"), (500, "incomplete"), (501, "incomplete")])
def test_consumption_goal_strict_limit(amount, status):
    from backend import goals
    result, _, _ = goals._finish(MagicMock(), {"id": 1, "steps": amount, "target": 500,
                                               "goal_type": goals.LIMIT, "is_daily": False})
    assert result == status


def test_meal_cutoffs_in_account_timezone(monkeypatch):
    from backend import alerts
    connection = MagicMock()
    connection.execute.return_value.fetchall.side_effect = [[{"zone":"America/Los_Angeles"}], [], []]
    context = MagicMock()
    context.__enter__.return_value = connection
    monkeypatch.setattr(alerts, "connect", lambda _: context)
    alerts.missing_meal_alerts(datetime(2026,11,19,22,30,tzinfo=UTC))
    args = [call.args[1] for call in connection.execute.call_args_list[1:]]
    assert [a[0] for a in args] == ["missing_breakfast","missing_lunch"]
    assert [a[3] for a in args] == ["2026-11-19T18:00:00+00:00","2026-11-19T22:30:00+00:00"]
