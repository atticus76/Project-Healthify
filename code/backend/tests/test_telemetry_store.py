"""Latest telemetry per user, kept in memory and saved to telemetry_snapshots (S2-04).

The emulator refreshes ~176 KB every second, so snapshots are saved to the
cloud at most once a minute per user (immediately for Google syncs and when
the emulator is turned off). Runs against healthify-test.
"""

from contextlib import contextmanager

import pytest

from backend import auth_controller, db, telemetry_emulator, telemetry_store

pytestmark = pytest.mark.usefixtures("test_db")

DATA_1 = {"steps": {"dataPoints": [{"value": 1}]}}
DATA_2 = {"steps": {"dataPoints": [{"value": 2}]}}


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch):
    class Clock:
        now = 1000.0

    monkeypatch.setattr(telemetry_store, "_clock", lambda: Clock.now)
    return Clock


@pytest.fixture
def user() -> str:
    auth_controller.register("user", "", "Testpass1!")
    return "user"


@pytest.fixture
def db_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    real_connect = telemetry_store.connect

    @contextmanager
    def counting_connect(operation: str = "database query"):
        calls.append(operation)
        with real_connect(operation) as conn:
            yield conn

    monkeypatch.setattr(telemetry_store, "connect", counting_connect)
    return calls


def _saved(user_id: str) -> list[dict]:
    with db.connect() as conn:
        return conn.execute(
            "SELECT source, data FROM telemetry_snapshots WHERE user_id = %s ORDER BY source",
            (user_id,),
        ).fetchall()


def test_nothing_saved_yet(user):
    assert telemetry_store.get_latest(user) is None


def test_first_snapshot_is_saved_right_away(user, clock):
    telemetry_store.save(user, DATA_1)
    assert _saved(user) == [{"source": "emulator", "data": DATA_1}]


def test_refreshes_within_a_minute_stay_in_memory(user, clock):
    telemetry_store.save(user, DATA_1)
    clock.now += 30
    telemetry_store.save(user, DATA_2)

    assert telemetry_store.get_latest(user) == DATA_2  # live view is current
    assert _saved(user)[0]["data"] == DATA_1  # cloud copy waits for the minute

    clock.now += 31
    telemetry_store.save(user, DATA_2)
    assert _saved(user)[0]["data"] == DATA_2


def test_forced_saves_skip_the_wait(user, clock):
    telemetry_store.save(user, DATA_1)
    telemetry_store.save(user, DATA_2, force=True)
    assert _saved(user)[0]["data"] == DATA_2


def test_after_a_restart_the_saved_snapshot_is_used(user, clock):
    telemetry_store.save(user, DATA_1)
    telemetry_store._reset_cache()  # what a server restart does
    assert telemetry_store.get_latest(user) == DATA_1


def test_newest_source_wins(user, clock):
    telemetry_store.save(user, DATA_1, source="emulator")
    telemetry_store.save(user, DATA_2, source="google", force=True)
    telemetry_store._reset_cache()
    assert telemetry_store.get_latest(user) == DATA_2


def test_turning_the_emulator_off_keeps_google_data(user, clock):
    telemetry_store.save(user, DATA_2, source="google", force=True)
    telemetry_store.save(user, DATA_1, source="emulator", force=True)
    telemetry_store.clear(user, "emulator")
    assert [row["source"] for row in _saved(user)] == ["google"]
    assert telemetry_store.get_latest(user) == DATA_2


def test_reading_with_nothing_saved_asks_the_database_once(user, clock, db_calls):
    # The Reports page reads telemetry every second.
    for _ in range(5):
        assert telemetry_store.get_latest(user) is None
    assert len(db_calls) == 1


def test_reading_saved_data_uses_memory(user, clock, db_calls):
    telemetry_store.save(user, DATA_1)
    db_calls.clear()
    for _ in range(5):
        telemetry_store.get_latest(user)
    assert db_calls == []


def test_users_have_separate_snapshots(user, clock):
    auth_controller.register("other", "", "Testpass1!")
    telemetry_store.save("other", DATA_2)
    assert telemetry_store.get_latest(user) is None


def test_a_failed_save_keeps_the_live_data_and_retries(user, clock, monkeypatch):
    @contextmanager
    def unreachable(operation: str = "database query"):
        raise db.DatabaseError(operation)
        yield

    real_connect = telemetry_store.connect
    monkeypatch.setattr(telemetry_store, "connect", unreachable)
    telemetry_store.save(user, DATA_1)  # doesn't raise
    assert telemetry_store.get_latest(user) == DATA_1

    monkeypatch.setattr(telemetry_store, "connect", real_connect)
    clock.now += 1  # well within a minute, but the last save failed
    telemetry_store.save(user, DATA_1)
    assert _saved(user)[0]["data"] == DATA_1


def test_emulator_no_longer_keeps_its_own_copy():
    assert not hasattr(telemetry_emulator, "_latest_telemetry")
