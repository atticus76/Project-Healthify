"""Small file-backed authentication service for the Healthify demo."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


USERS_FILE = Path(__file__).resolve().parent / "users.txt"
DEFAULT_PROFILE = {
    "gender": "Prefer not to say",
    "age": 30,
    "weight_lb": 170.0,
    "complete": False,
}
_active_user = ""


def set_active_user(username: str) -> None:
    global _active_user
    _active_user = _key(username)


def get_active_user() -> str:
    return _active_user


def clear_active_user() -> None:
    global _active_user
    _active_user = ""


def _load_users() -> dict[str, dict[str, Any]]:
    if not USERS_FILE.exists():
        return {}
    try:
        value = json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _save_users(users: dict[str, dict[str, Any]]) -> None:
    USERS_FILE.write_text(json.dumps(users, indent=2), encoding="utf-8")


def _key(value: str) -> str:
    return value.strip().lower()


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _valid_password(password: str) -> str | None:
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one capital letter."
    if not re.search(r"\d", password):
        return "Password must contain at least one number."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\;/~`]", password):
        return "Password must contain at least one special character."
    return None


def register(
    username: str, email: str, password: str, theme: str = "light"
) -> tuple[bool, str, str]:
    username_key = _key(username)
    email_key = _key(email)
    if len(username_key) < 3:
        return False, "Username must be at least 3 characters long.", ""
    if "@" in username_key or not re.fullmatch(r"[a-z0-9_.-]+", username_key):
        return False, "Username may contain letters, numbers, '.', '_' or '-'.", ""
    if email_key and ("@" not in email_key or "." not in email_key.rsplit("@", 1)[-1]):
        return False, "Please enter a valid email address or leave it blank.", ""
    password_error = _valid_password(password)
    if password_error:
        return False, password_error, ""

    users = _load_users()
    if username_key in users:
        return False, "That username is already in use.", ""
    if any(user.get("email", "") == email_key and email_key for user in users.values()):
        return False, "That email is already in use.", ""

    users[username_key] = {
        "username": username_key,
        "email": email_key,
        "password_hash": _hash_password(password),
        "profile": dict(DEFAULT_PROFILE),
        "app_state": {"theme": theme if theme in {"light", "dark"} else "light", "device_name": ""},
    }
    _save_users(users)
    return True, "Account created.", username_key


def authenticate(identifier: str, password: str) -> tuple[bool, str, str]:
    users = _load_users()
    key = _key(identifier)
    username = key if key in users else next(
        (name for name, user in users.items() if user.get("email") == key), ""
    )
    if not username or users[username].get("password_hash") != _hash_password(password):
        return False, "Invalid username/email or password.", ""
    return True, "Signed in.", username


def get_user(username: str) -> dict[str, Any] | None:
    return _load_users().get(_key(username))


def update_user(username: str, **changes: Any) -> None:
    users = _load_users()
    key = _key(username)
    if key not in users:
        raise ValueError("User account was not found.")
    users[key].update(changes)
    _save_users(users)


def set_theme(username: str, theme: str) -> None:
    if theme not in {"light", "dark"}:
        raise ValueError("Theme must be light or dark.")
    user = get_user(username)
    if user is None:
        raise ValueError("User account was not found.")
    app_state = dict(user.get("app_state", {}))
    app_state["theme"] = theme
    update_user(username, app_state=app_state)


def save_profile(username: str, gender: str, age: int, weight_lb: float) -> None:
    user = get_user(username)
    if user is None:
        raise ValueError("User account was not found.")
    profile = {
        "gender": gender,
        "age": age,
        "weight_lb": weight_lb,
        "complete": True,
    }
    update_user(username, profile=profile)
