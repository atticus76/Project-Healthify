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


def test_expired_pending_request_is_rejected(alice, monkeypatch):
    token_store.save_pending("state-1", "verifier-1", alice)
    monkeypatch.setattr(token_store.time, "time", lambda: 10**10)  # far in the future
    assert token_store.pop_pending("state-1") is None


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


def test_deleting_an_account_deletes_its_tokens(alice):
    token_store.save_connection(alice, TOKENS)
    with db.connect() as conn:
        conn.execute("DELETE FROM users WHERE username = %s", (alice,))
    assert token_store.get_connection(alice) is None
