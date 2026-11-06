"""Login-page accounts, stored in the cloud `users` table (S2-04).

Usernames are case-sensitive ("Alice" and "alice" are different accounts).
Emails are case-insensitive: they're lowercased before saving or looking up,
and stored as NULL when left blank.

Database failures raise `backend.db.DatabaseError`; callers show its message.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from psycopg.types.json import Jsonb

from backend.db import connect

# The signed-in user is still one global shared by every browser. It moves
# into AuthState in S2-04 task 5 (cleanup C2).
_active_user = ""

_UPDATABLE_FIELDS = {"email", "app_state"}


def set_active_user(username: str) -> None:
    global _active_user
    _active_user = _username_key(username)


def get_active_user() -> str:
    return _active_user


def clear_active_user() -> None:
    global _active_user
    _active_user = ""


def _username_key(value: str) -> str:
    """Usernames are case-sensitive: "Alice" and "alice" are different accounts."""
    return value.strip()


def _email_key(value: str) -> str:
    """Emails are case-insensitive, since mail servers treat them that way."""
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
    username_key = _username_key(username)
    email_key = _email_key(email)
    if len(username_key) < 3:
        return False, "Username must be at least 3 characters long.", ""
    if "@" in username_key or not re.fullmatch(r"[A-Za-z0-9_.-]+", username_key):
        return False, "Username may contain letters, numbers, '.', '_' or '-'.", ""
    if email_key and ("@" not in email_key or "." not in email_key.rsplit("@", 1)[-1]):
        return False, "Please enter a valid email address or leave it blank.", ""
    password_error = _valid_password(password)
    if password_error:
        return False, password_error, ""

    app_state = {"theme": theme if theme in {"light", "dark"} else "light", "device_name": ""}
    with connect("register account") as conn:
        if email_key and conn.execute(
            "SELECT 1 FROM users WHERE email = %s", (email_key,)
        ).fetchone():
            return False, "That email is already in use.", ""
        created = conn.execute(
            """
            INSERT INTO users (username, email, password_hash, app_state)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (username) DO NOTHING
            RETURNING username
            """,
            (username_key, email_key or None, _hash_password(password), Jsonb(app_state)),
        ).fetchone()
    if created is None:
        return False, "That username is already in use.", ""
    return True, "Account created.", username_key


def authenticate(identifier: str, password: str) -> tuple[bool, str, str]:
    # Usernames can't contain "@", so an identifier with "@" is an email.
    if "@" in identifier:
        query, key = "SELECT username, password_hash FROM users WHERE email = %s", _email_key(identifier)
    else:
        query, key = "SELECT username, password_hash FROM users WHERE username = %s", _username_key(identifier)
    with connect("sign in") as conn:
        row = conn.execute(query, (key,)).fetchone()
    if row is None or row["password_hash"] != _hash_password(password):
        return False, "Invalid username/email or password.", ""
    return True, "Signed in.", row["username"]


def get_user(username: str) -> dict[str, Any] | None:
    """Return the account (never the password hash), or None if it doesn't exist."""
    with connect("load account") as conn:
        row = conn.execute(
            "SELECT username, email, app_state, created_at FROM users WHERE username = %s",
            (_username_key(username),),
        ).fetchone()
    if row is None:
        return None
    return {**row, "email": row["email"] or ""}


def update_user(username: str, **changes: Any) -> None:
    """Update `email` and/or `app_state` for an existing account."""
    unknown = set(changes) - _UPDATABLE_FIELDS
    if unknown:
        raise ValueError(f"Can't update these account fields: {', '.join(sorted(unknown))}")
    values: dict[str, Any] = {}
    if "email" in changes:
        values["email"] = _email_key(changes["email"]) or None
    if "app_state" in changes:
        values["app_state"] = Jsonb(dict(changes["app_state"]))
    with connect("update account") as conn:
        if values:
            # Column names come from _UPDATABLE_FIELDS, never from user input.
            assignments = ", ".join(f"{column} = %({column})s" for column in values)
            row = conn.execute(
                f"UPDATE users SET {assignments} WHERE username = %(username)s RETURNING username",
                {**values, "username": _username_key(username)},
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT username FROM users WHERE username = %s", (_username_key(username),)
            ).fetchone()
    if row is None:
        raise ValueError("User account was not found.")


def set_theme(username: str, theme: str) -> None:
    if theme not in {"light", "dark"}:
        raise ValueError("Theme must be light or dark.")
    user = get_user(username)
    if user is None:
        raise ValueError("User account was not found.")
    app_state = dict(user.get("app_state") or {})
    app_state["theme"] = theme
    update_user(username, app_state=app_state)
