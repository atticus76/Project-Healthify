"""Goals in the cloud health_goals / goal_progress tables (FR-09, S2-04).

Runs against healthify-test and is skipped if TEST_DATABASE_URL isn't set.
Time is controlled by patching goals._now.
"""

from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone

import pytest

from backend import auth_controller, db, goals

pytestmark = pytest.mark.usefixtures("test_db")

START = datetime(2026, 11, 4, 15, 0, tzinfo=timezone.utc)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch):
    """Set the current time with clock.now = ...; starts at START."""

    class Clock:
        now = START

    monkeypatch.setattr(goals, "_now", lambda: Clock.now)
    return Clock


@pytest.fixture
def user() -> str:
    auth_controller.register("user", "", "Testpass1!")
    return "user"


@pytest.fixture
def count_queries(monkeypatch: pytest.MonkeyPatch):
    """Count connections opened and statements run by goals."""
    counts = {"connections": 0, "queries": 0}
    real_connect = goals.connect

    class CountingConnection:
        def __init__(self, conn):
            self._conn = conn

        def execute(self, *args, **kwargs):
            counts["queries"] += 1
            return self._conn.execute(*args, **kwargs)

    @contextmanager
    def counting_connect(operation: str = "database query"):
        counts["connections"] += 1
        with real_connect(operation) as conn:
            yield CountingConnection(conn)

    monkeypatch.setattr(goals, "connect", counting_connect)
    return counts


def _custom_deadline(hours: int) -> str:
    return (START + timedelta(hours=hours)).isoformat()


# --- Existing behavior ------------------------------------------------------


def test_low_incomplete_day_gets_motivational_prompt(user, clock):
    goals.save_goal(user, goals.GOAL_DAILY_STEPS, 10_000, True)
    goals.record_steps(user, 4_999, date(2026, 11, 4))

    result = goals.complete_day(user, date(2026, 11, 4))

    assert result["status"] == "incomplete"
    assert result["prompt"]


# --- Creating and listing goals ---------------------------------------------


def test_daily_goal_ends_at_the_next_local_midnight(user, clock):
    goal = goals.add_goal(user, goals.GOAL_DAILY_STEPS, 8_000, False)
    assert goal["deadline_at"] == goals.next_local_midnight(START).isoformat()
    assert goal["is_daily"] == 1


def test_listing_goals_is_one_query_however_many_goals_exist(user, clock, count_queries):
    # Daily goals add a row every day, and the Goals page reloads every second,
    # so this must not grow with the number of goals.
    for _ in range(5):
        goals.add_goal(user, goals.GOAL_DAILY_STEPS, 1_000, False)
    count_queries.update(connections=0, queries=0)

    assert len(goals.list_goals(user)) == 5
    assert count_queries == {"connections": 1, "queries": 1}


def test_users_only_see_their_own_goals(user, clock):
    auth_controller.register("other", "", "Testpass1!")
    goals.add_goal("other", goals.GOAL_DAILY_STEPS, 1_000, False)
    assert goals.list_goals(user) == []
    assert goals.get_goal(user) is None


# --- Recording steps --------------------------------------------------------


def test_milestones_are_only_announced_once(user, clock):
    goals.add_goal(user, goals.GOAL_DAILY_STEPS, 1_000, True)
    assert goals.record_steps(user, 300)["milestones"] == [25]
    assert goals.record_steps(user, 300)["milestones"] == [50]
    result = goals.record_steps(user, 500)
    assert result["milestones"] == [75, 100]
    assert result["status"] == "complete"


def test_steps_go_to_the_chosen_goal(user, clock):
    older = goals.add_goal(user, goals.GOAL_DAILY_STEPS, 1_000, False)
    clock.now = START + timedelta(minutes=5)
    goals.add_goal(user, goals.GOAL_DAILY_STEPS, 1_000, False)
    goals.record_steps(user, 100, goal_id=older["id"])
    by_id = {g["id"]: g["steps"] for g in goals.list_goals(user)}
    assert by_id[older["id"]] == 100
    assert sorted(by_id.values()) == [0, 100]


def test_recording_steps_uses_one_connection(user, clock, count_queries):
    goals.add_goal(user, goals.GOAL_DAILY_STEPS, 1_000, False)
    count_queries.update(connections=0, queries=0)
    goals.record_steps(user, 100)
    assert count_queries["connections"] == 1


def test_ended_goal_can_no_longer_be_updated(user, clock):
    goals.add_goal(user, goals.GOAL_DAILY_STEPS, 1_000, False)
    clock.now = START + timedelta(days=2)
    with pytest.raises(ValueError, match="ended"):
        goals.record_steps(user, 100)


def test_someone_elses_goal_cant_be_updated(user, clock):
    auth_controller.register("other", "", "Testpass1!")
    theirs = goals.add_goal("other", goals.GOAL_DAILY_STEPS, 1_000, False)
    with pytest.raises(ValueError, match="not found"):
        goals.record_steps(user, 100, goal_id=theirs["id"])


# --- Ending goals -----------------------------------------------------------


def test_ending_a_daily_goal_starts_tomorrows(user, clock):
    goal = goals.add_goal(user, goals.GOAL_DAILY_STEPS, 7_000, True)
    result = goals.end_goal(user, goal_id=goal["id"])

    assert result["rollover"] is not None
    newest = goals.list_goals(user)[0]
    assert newest["id"] == result["rollover"]["id"] != goal["id"]
    assert (newest["target"], newest["steps"], newest["status"]) == (7_000, 0, "in_progress")
    assert newest["reminders_enabled"] == 1


def test_deleting_a_goal_only_deletes_your_own(user, clock):
    auth_controller.register("other", "", "Testpass1!")
    mine = goals.add_goal(user, goals.GOAL_DAILY_STEPS, 1_000, False)
    theirs = goals.add_goal("other", goals.GOAL_DAILY_STEPS, 1_000, False)
    goals.delete_goal(user, theirs["id"])
    goals.delete_goal(user, mine["id"])
    assert goals.list_goals(user) == []
    assert len(goals.list_goals("other")) == 1
    with db.connect() as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM goal_progress WHERE goal_id = %s", (mine["id"],)
        ).fetchone()["n"] == 0


# --- Reminders and deadlines ------------------------------------------------


def test_reminders_after_2_8_and_16_hours_without_steps(user, clock):
    goals.add_goal(
        user, goals.GOAL_DAILY_STEPS, 1_000, True, is_daily=False, deadline_at=_custom_deadline(48)
    )
    clock.now = START + timedelta(hours=1)
    assert goals.refresh_reminders(user) == []
    clock.now = START + timedelta(hours=9)
    assert len(goals.refresh_reminders(user)) == 2  # the 2- and 8-hour reminders
    assert goals.refresh_reminders(user) == []  # not repeated
    clock.now = START + timedelta(hours=17)
    assert len(goals.refresh_reminders(user)) == 1


def test_passed_deadline_ends_the_goal_and_rolls_daily_goals_over(user, clock):
    goal = goals.add_goal(user, goals.GOAL_DAILY_STEPS, 1_000, False)
    goals.record_steps(user, 400)
    clock.now = START + timedelta(days=1, hours=1)

    [notice] = goals.refresh_reminders(user)

    assert notice["title"] == "Goal deadline reached"
    assert "400 of 1,000" in notice["message"]
    by_id = {g["id"]: g for g in goals.list_goals(user)}
    assert by_id[goal["id"]]["status"] == "incomplete"
    assert by_id[goal["id"]]["prompt"] == goals.MOTIVATIONAL_PROMPT
    assert len(by_id) == 2


def test_scheduler_checks_every_user_not_a_demo_user(user, clock):
    auth_controller.register("second", "", "Testpass1!")
    for name in (user, "second"):
        goals.add_goal(
            name, goals.GOAL_DAILY_STEPS, 1_000, True, is_daily=False, deadline_at=_custom_deadline(48)
        )
    clock.now = START + timedelta(hours=3)

    due = goals.refresh_all_reminders()

    assert sorted(user_id for user_id, _ in due) == sorted([user, "second"])
    assert all(n["title"] == "Goal progress reminder" for _, n in due)
