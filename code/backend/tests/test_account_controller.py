"""Unit tests for US-02 account registration."""

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import account_controller as account_ctrl  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_accounts_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect account storage to a temporary file during tests."""
    temp_file = tmp_path / "test_accounts.json"
    monkeypatch.setattr(account_ctrl, "ACCOUNTS_FILE", temp_file)
    yield


def test_us02_scenario_1_positive_registration():
    success, msg = account_ctrl.register_account("student@wsu.edu", "SecurePass1!")
    assert success is True
    assert msg == "Account created successfully."


def test_us02_scenario_2_duplicate_email_rejected():
    account_ctrl.register_account("student@wsu.edu", "SecurePass1!")
    success, msg = account_ctrl.register_account("student@wsu.edu", "DifferentPass2@")
    assert success is False
    assert "different login credentials" in msg


@pytest.mark.parametrize(
    "bad_password",
    [
        "short1!",          # Too short
        "nocapital123!",    # Missing capital letter
        "NoNumbersHere!",   # Missing number
        "NoSpecialChar123", # Missing special character
    ],
)
def test_us02_password_complexity_enforcement(bad_password: str):
    success, _ = account_ctrl.register_account("newuser@wsu.edu", bad_password)
    assert success is False
