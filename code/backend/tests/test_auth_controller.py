"""Unit tests for login-page accounts: usernames are case-sensitive, emails are not."""

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import auth_controller  # noqa: E402

PASSWORD = "Testpass1!"


@pytest.fixture(autouse=True)
def isolated_users_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect account storage to a temporary file during tests."""
    monkeypatch.setattr(auth_controller, "USERS_FILE", tmp_path / "users.txt")
    yield


def test_username_keeps_its_case():
    ok, _, username = auth_controller.register("Alice", "", PASSWORD)
    assert ok
    assert username == "Alice"
    assert auth_controller.get_user("Alice") is not None
    assert auth_controller.get_user("alice") is None


def test_usernames_differing_only_in_case_are_separate_accounts():
    assert auth_controller.register("Alice", "", PASSWORD)[0]
    assert auth_controller.register("alice", "", PASSWORD)[0]


def test_same_username_twice_is_rejected():
    assert auth_controller.register("Alice", "", PASSWORD)[0]
    ok, message, _ = auth_controller.register("Alice", "", PASSWORD)
    assert not ok
    assert message == "That username is already in use."


def test_sign_in_needs_exact_username_case():
    auth_controller.register("Alice", "", PASSWORD)
    assert auth_controller.authenticate("Alice", PASSWORD) == (True, "Signed in.", "Alice")
    assert not auth_controller.authenticate("alice", PASSWORD)[0]
    assert not auth_controller.authenticate("ALICE", PASSWORD)[0]


def test_password_is_case_sensitive():
    auth_controller.register("Alice", "", PASSWORD)
    assert not auth_controller.authenticate("Alice", PASSWORD.lower())[0]
    assert not auth_controller.authenticate("Alice", PASSWORD.upper())[0]


def test_email_sign_in_ignores_case():
    auth_controller.register("Alice", "Alice@Example.com", PASSWORD)
    assert auth_controller.authenticate("alice@example.com", PASSWORD) == (
        True,
        "Signed in.",
        "Alice",
    )
    assert auth_controller.authenticate("ALICE@EXAMPLE.COM", PASSWORD)[0]


def test_email_in_use_check_ignores_case():
    auth_controller.register("Alice", "alice@example.com", PASSWORD)
    ok, message, _ = auth_controller.register("Bob", "ALICE@example.com", PASSWORD)
    assert not ok
    assert message == "That email is already in use."
