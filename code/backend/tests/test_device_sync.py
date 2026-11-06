"""Scheduled Google Health sync with backoff (US-01 scenario 2).

Spec: code/specs/features/S1-03-scheduled-device-sync.md. Google's endpoints
are mocked; runs against healthify-test.
"""

import json
import time
from pathlib import Path
from unittest import mock

import pytest
import requests

from backend import auth_controller, db, email_alerts, google_health, telemetry_store, token_store

pytestmark = pytest.mark.usefixtures("test_db")

SAMPLES = Path(__file__).resolve().parents[3] / "data" / "samples"
NOW = 2_000_000_000.0  # seconds since the epoch, May 2033
MINUTE = 60


class FakeResponse:
    def __init__(self, status: int, body: dict | None = None, headers: dict | None = None):
        self.status_code = status
        self._body = body or {}
        self.headers = headers or {}
        self.content = json.dumps(self._body).encode()

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)


def _samples(url, params, headers, timeout):
    data_type = url.split("/dataTypes/")[1].split("/")[0]
    return FakeResponse(200, json.loads((SAMPLES / f"{data_type}.json").read_text()))


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch):
    class Clock:
        now = NOW

    monkeypatch.setattr(google_health, "_now", lambda: Clock.now)
    return Clock


def _connect(user: str) -> str:
    auth_controller.register(user, "", "Testpass1!")
    token_store.save_connection(user, {
        "email": f"{user}@gmail.com", "access_token": "access", "refresh_token": "refresh",
        "expires_at": int(time.time()) + 3600, "scope": "",
    })
    return user


@pytest.fixture
def alice() -> str:
    return _connect("alice")


def _connection(user: str) -> dict:
    return token_store.get_connection(user)


def test_due_connections_sync_and_schedule_the_next_one(alice, clock):
    with mock.patch("backend.google_health.requests.get", side_effect=_samples):
        assert google_health.sync_due() == [alice]

    conn = _connection(alice)
    assert conn["status"] == token_store.STATUS_CONNECTED
    assert conn["next_sync_at"] == NOW + google_health.SYNC_EVERY_S
    assert telemetry_store.get_latest(alice) is not None

    # Not due again until the interval passes: no calls to Google.
    with mock.patch("backend.google_health.requests.get") as get:
        assert google_health.sync_due() == []
    get.assert_not_called()


def test_failures_back_off_and_a_success_resets(alice, clock):
    outage = FakeResponse(503)
    delays = []
    for _ in range(4):
        with mock.patch("backend.google_health.requests.get", return_value=outage):
            google_health.sync_due()
        conn = _connection(alice)
        delays.append(conn["next_sync_at"] - clock.now)
        clock.now = conn["next_sync_at"]

    assert delays == [5 * MINUTE, 10 * MINUTE, 20 * MINUTE, 40 * MINUTE]
    conn = _connection(alice)
    assert conn["status"] == token_store.STATUS_SYNC_FAILED
    assert conn["sync_failures"] == 4
    assert "503" in conn["last_sync_error"]

    with mock.patch("backend.google_health.requests.get", side_effect=_samples):
        google_health.sync_due()
    conn = _connection(alice)
    assert (conn["status"], conn["sync_failures"], conn["last_sync_error"]) == ("connected", 0, "")


def test_backoff_is_capped_and_respects_retry_after(alice, clock):
    with db.connect() as conn:
        conn.execute("UPDATE google_connections SET sync_failures = 20 WHERE user_id = %s", (alice,))
    with mock.patch("backend.google_health.requests.get", return_value=FakeResponse(503)):
        google_health.sync_due()
    assert _connection(alice)["next_sync_at"] - NOW == google_health.RETRY_MAX_S

    clock.now = _connection(alice)["next_sync_at"]
    rate_limited = FakeResponse(429, headers={"Retry-After": "86400"})  # longer than the cap
    with mock.patch("backend.google_health.requests.get", return_value=rate_limited):
        google_health.sync_due()
    conn = _connection(alice)
    assert conn["next_sync_at"] - clock.now == 86400
    assert "rate limit" in conn["last_sync_error"].lower()


def test_revoked_access_is_not_retried_until_reconnected(alice, clock):
    with db.connect() as conn:
        conn.execute("UPDATE google_connections SET expires_at = 0 WHERE user_id = %s", (alice,))
    revoked = FakeResponse(400, {"error": "invalid_grant"})
    with mock.patch("backend.google_oauth.requests.post", return_value=revoked):
        assert google_health.sync_due() == []
    assert _connection(alice)["status"] == token_store.STATUS_RECONNECT

    clock.now += 7 * 24 * 3600
    with mock.patch("backend.google_health.requests.get") as get, \
            mock.patch("backend.google_oauth.requests.post") as post:
        assert google_health.sync_due() == []
    get.assert_not_called()
    post.assert_not_called()


def test_one_users_failure_does_not_stop_the_others(alice, clock):
    bob = _connect("bob")

    calls = {"n": 0}

    def alice_fails_bob_works(url, params, headers, timeout):
        calls["n"] += 1
        if calls["n"] == 1:  # the first user's first request
            raise requests.ConnectionError("network down")
        return _samples(url, params, headers, timeout)

    with mock.patch("backend.google_health.requests.get", side_effect=alice_fails_bob_works):
        synced = google_health.sync_due()

    assert len(synced) == 1
    statuses = sorted(_connection(u)["status"] for u in (alice, bob))
    assert statuses == ["connected", "sync_failed"]


def test_background_sync_saves_and_emails_new_alerts(alice, clock, monkeypatch):
    spike_hr = {"dataPoints": [
        {"heartRate": {"beatsPerMinute": 150, "sampleTime": {"physicalTime": f"2026-11-05T10:{m:02d}:00Z"}}}
        for m in range(0, 10)
    ]}

    def with_spike(url, params, headers, timeout):
        if "/dataTypes/heart-rate/" in url:
            return FakeResponse(200, spike_hr)
        return FakeResponse(200, {"dataPoints": []})

    with mock.patch("backend.google_health.requests.get", side_effect=with_spike), \
            mock.patch.object(email_alerts, "dispatch") as dispatch:
        google_health.sync_due()

    from backend import alerts

    assert alerts.unacknowledged_count(alice) == 1
    dispatch.assert_called_once()
    assert dispatch.call_args.args[0] == alice
