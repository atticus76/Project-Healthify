"""Google OAuth storage in the cloud tables oauth_pending and google_connections (S2-04).

Runs against healthify-test and is skipped if TEST_DATABASE_URL isn't set.
"""

import time

import pytest

from backend import auth_controller, db, token_store

pytestmark = pytest.mark.usefixtures("test_db")

TOKENS = {
    "email": "alice@gmail.com",
    "access_token": "access-1",
    "refresh_token": "refresh-1",
    "expires_at": int(time.time()) + 3600,
    "scope": "openid email",
}


@pytest.fixture
def alice() -> str:
    auth_controller.register("alice", "", "Testpass1!")
    return "alice"


# --- Pending OAuth requests -------------------------------------------------


def test_pending_request_is_returned_once(alice):
    token_store.save_pending("state-1", "verifier-1", alice)
    pending = token_store.pop_pending("state-1")
    assert pending["code_verifier"] == "verifier-1"
    assert pending["user_id"] == alice
    assert token_store.pop_pending("state-1") is None


def test_unknown_state_returns_none(alice):
    assert token_store.pop_pending("never-saved") is None


def test_expired_pending_request_is_rejected(alice, monkeypatch):
    token_store.save_pending("state-1", "verifier-1", alice)
    monkeypatch.setattr(token_store.time, "time", lambda: 10**10)  # far in the future
    assert token_store.pop_pending("state-1") is None


def test_saving_a_request_clears_abandoned_ones(alice, monkeypatch):
    token_store.save_pending("old", "v", alice)
    real_time = time.time()
    monkeypatch.setattr(
        token_store.time, "time", lambda: real_time + token_store.PENDING_TTL_S + 60
    )
    token_store.save_pending("new", "v", alice)
    with db.connect() as conn:
        states = [r["state"] for r in conn.execute("SELECT state FROM oauth_pending").fetchall()]
    assert states == ["new"]


def test_pending_request_needs_an_existing_account():
    with pytest.raises(db.DatabaseError):
        token_store.save_pending("state-1", "verifier-1", "ghost")


# --- Connections ------------------------------------------------------------


def test_saved_connection_comes_back(alice):
    token_store.save_connection(alice, TOKENS)
    conn = token_store.get_connection(alice)
    assert conn["status"] == token_store.STATUS_CONNECTED
    assert conn["email"] == "alice@gmail.com"
    assert conn["access_token"] == "access-1"
    assert conn["refresh_token"] == "refresh-1"
    assert conn["expires_at"] == TOKENS["expires_at"]
    assert conn["last_sync_at"] is None


def test_users_only_see_their_own_connection(alice):
    auth_controller.register("bob", "", "Testpass1!")
    token_store.save_connection(alice, TOKENS)
    assert token_store.get_connection("bob") is None


def test_reconnecting_replaces_the_tokens(alice):
    token_store.save_connection(alice, TOKENS)
    token_store.mark_reconnect_required(alice)
    token_store.save_connection(alice, {**TOKENS, "access_token": "access-2"})
    conn = token_store.get_connection(alice)
    assert conn["access_token"] == "access-2"
    assert conn["status"] == token_store.STATUS_CONNECTED


def test_refreshed_access_token_is_saved(alice):
    token_store.save_connection(alice, TOKENS)
    token_store.mark_reconnect_required(alice)
    token_store.update_access_token(alice, "access-2", 123)
    conn = token_store.get_connection(alice)
    assert (conn["access_token"], conn["expires_at"]) == ("access-2", 123)
    assert conn["status"] == token_store.STATUS_CONNECTED


def test_record_sync_keeps_the_device_name_when_none_is_reported(alice):
    token_store.save_connection(alice, TOKENS)
    token_store.record_sync(alice, "Charge 6")
    token_store.record_sync(alice, "")
    conn = token_store.get_connection(alice)
    assert conn["device_name"] == "Charge 6"
    assert conn["last_sync_at"] >= int(time.time()) - 60


def test_disconnecting_deletes_the_connection(alice):
    token_store.save_connection(alice, TOKENS)
    token_store.delete_connection(alice)
    assert token_store.get_connection(alice) is None


def test_deleting_an_account_deletes_its_tokens(alice):
    token_store.save_connection(alice, TOKENS)
    with db.connect() as conn:
        conn.execute("DELETE FROM users WHERE username = %s", (alice,))
    assert token_store.get_connection(alice) is None


def test_tokens_no_longer_use_sqlite():
    assert not hasattr(token_store, "DATABASE_PATH")
