"""Login-page accounts, stored in the cloud users table (S2-04).

Usernames are case-sensitive, emails are not. Runs against healthify-test and
is skipped if TEST_DATABASE_URL isn't set.
"""

import pytest

from backend import auth_controller, db

PASSWORD = "Testpass1!"

pytestmark = pytest.mark.usefixtures("test_db")


def _users_table() -> list[dict]:
    with db.connect() as conn:
        return conn.execute("SELECT * FROM users ORDER BY username").fetchall()


# --- Registering ------------------------------------------------------------


def test_registering_stores_a_row_in_the_users_table():
    ok, message, username = auth_controller.register("alice", "alice@example.com", PASSWORD)
    assert (ok, message, username) == (True, "Account created.", "alice")
    [row] = _users_table()
    assert row["username"] == "alice"
    assert row["email"] == "alice@example.com"
    assert row["password_hash"] and row["password_hash"] != PASSWORD


def test_blank_email_is_stored_as_null_so_many_users_can_skip_it():
    assert auth_controller.register("alice", "", PASSWORD)[0]
    assert auth_controller.register("bob", "  ", PASSWORD)[0]
    assert [row["email"] for row in _users_table()] == [None, None]


def test_username_keeps_its_case():
    ok, _, username = auth_controller.register("Alice", "", PASSWORD)
    assert ok and username == "Alice"
    assert auth_controller.get_user("Alice") is not None
    assert auth_controller.get_user("alice") is None


def test_same_username_twice_is_rejected():
    assert auth_controller.register("alice", "", PASSWORD)[0]
    ok, message, _ = auth_controller.register("alice", "", PASSWORD)
    assert not ok
    assert message == "That username is already in use."


def test_email_in_use_check_ignores_case():
    auth_controller.register("alice", "alice@example.com", PASSWORD)
    ok, message, _ = auth_controller.register("bob", "ALICE@example.com", PASSWORD)
    assert not ok
    assert message == "That email is already in use."


# --- Signing in -------------------------------------------------------------


def test_sign_in_with_username_or_email():
    auth_controller.register("alice", "alice@example.com", PASSWORD)
    assert auth_controller.authenticate("alice", PASSWORD) == (True, "Signed in.", "alice")
    assert auth_controller.authenticate("alice@example.com", PASSWORD) == (
        True,
        "Signed in.",
        "alice",
    )


def test_sign_in_needs_exact_username_case():
    auth_controller.register("Alice", "", PASSWORD)
    assert auth_controller.authenticate("Alice", PASSWORD)[0]
    assert not auth_controller.authenticate("alice", PASSWORD)[0]


def test_password_is_case_sensitive():
    auth_controller.register("alice", "", PASSWORD)
    assert not auth_controller.authenticate("alice", PASSWORD.lower())[0]
    assert not auth_controller.authenticate("alice", PASSWORD.upper())[0]


# --- Reading and updating ---------------------------------------------------


def test_get_user_returns_account_without_the_password_hash():
    auth_controller.register("alice", "", PASSWORD, theme="dark")
    user = auth_controller.get_user("alice")
    assert user["username"] == "alice"
    assert user["email"] == ""  # blank, not None, so the UI can show it
    assert user["app_state"]["theme"] == "dark"
    assert "password_hash" not in user


# --- One connection per sign-in / sign-up (NFR-01: pages under 1 s) ----------
# Opening a Supabase connection takes ~200 ms, so these must not open several.


@pytest.fixture
def count_connections(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    opened: list[str] = []
    real_connect = auth_controller.connect

    def counting_connect(operation: str = "database query"):
        opened.append(operation)
        return real_connect(operation)

    monkeypatch.setattr(auth_controller, "connect", counting_connect)
    return opened


def test_sign_in_returns_account_and_profile_status_in_one_connection(count_connections):
    auth_controller.register("alice", "alice@example.com", PASSWORD)
    count_connections.clear()

    ok, message, account = auth_controller.sign_in("ALICE@example.com", PASSWORD, "dark")

    assert (ok, message) == (True, "Signed in.")
    assert account["username"] == "alice"
    assert account["email"] == "alice@example.com"
    assert account["app_state"]["theme"] == "dark"
    assert account["has_profile"] is False
    assert len(count_connections) == 1
    assert auth_controller.get_user("alice")["app_state"]["theme"] == "dark"


def test_failed_sign_in_changes_nothing():
    auth_controller.register("alice", "", PASSWORD, theme="light")
    assert auth_controller.sign_in("alice", "Wrongpass1!", "dark") == (
        False,
        "Invalid username/email or password.",
        None,
    )
    assert auth_controller.get_user("alice")["app_state"]["theme"] == "light"


def test_sign_up_returns_the_new_account_in_one_connection(count_connections):
    ok, message, account = auth_controller.sign_up("Alice", "", PASSWORD, "dark")
    assert (ok, message) == (True, "Account created.")
    assert account["username"] == "Alice"
    assert account["email"] == ""
    assert account["app_state"]["theme"] == "dark"
    assert account["has_profile"] is False
    assert len(count_connections) == 1
