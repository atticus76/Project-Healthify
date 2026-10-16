"""Backend controller for US-02 user registration and credential validation."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

# Store registered accounts in data/accounts.json so they persist across runs
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
ACCOUNTS_FILE = DATA_DIR / "accounts.json"

SPECIAL_CHAR_PATTERN = re.compile(r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\;/~`]")


def _load_accounts() -> dict[str, dict[str, Any]]:
    if not ACCOUNTS_FILE.exists():
        return {}
    try:
        return json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_accounts(accounts: dict[str, dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ACCOUNTS_FILE.write_text(json.dumps(accounts, indent=2), encoding="utf-8")


def validate_credentials(email: str, password: str) -> str | None:
    """
    Validate email format and US-02 password rules:
    - At least one capital letter
    - At least one number
    - At least one special character
    """
    clean_email = email.strip().lower()
    if not clean_email or "@" not in clean_email or "." not in clean_email.split("@")[-1]:
        return "Please enter a valid email address."

    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one capital letter."
    if not re.search(r"\d", password):
        return "Password must contain at least one number."
    if not SPECIAL_CHAR_PATTERN.search(password):
        return "Password must contain at least one special character."

    return None


def hash_password(password: str) -> str:
    """Return a SHA-256 hex digest of the password."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def register_account(email: str, password: str) -> tuple[bool, str]:
    """
    Register a new user account.
    Returns (success: bool, message: str).
    """
    clean_email = email.strip().lower()
    accounts = _load_accounts()

    # US-02 Scenario 2: Reject duplicate email already in database
    if clean_email in accounts:
        return (
            False,
            "An account with those credentials already exists. Please create an account using different login credentials.",
        )

    # US-02 Scenario 1: Verify password meets security requirements
    validation_error = validate_credentials(clean_email, password)
    if validation_error:
        return False, validation_error

    accounts[clean_email] = {
        "email": clean_email,
        "password_hash": hash_password(password),
    }
    _save_accounts(accounts)
    return True, "Account created successfully."