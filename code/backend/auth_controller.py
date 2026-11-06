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


_INVALID_LOGIN = "Invalid username/email or password."

# Saves the chosen theme and returns what the app needs after signing in,
# including whether the user has a profile, in one round trip.
_START_SESSION = """
    UPDATE users
    SET app_state = jsonb_set(app_state, '{theme}', to_jsonb(%s::text))
    WHERE username = %s
    RETURNING username, COALESCE(email, '') AS email, app_state,
        EXISTS (SELECT 1 FROM health_profiles WHERE user_id = users.username) AS has_profile
"""


def _clean_theme(theme: str) -> str:
    return theme if theme in {"light", "dark"} else "light"


def _registration_error(username_key: str, email_key: str, password: str) -> str | None:
    """Check sign-up input without touching the database."""
    if len(username_key) < 3:
        return "Username must be at least 3 characters long."
    if "@" in username_key or not re.fullmatch(r"[A-Za-z0-9_.-]+", username_key):
        return "Username may contain letters, numbers, '.', '_' or '-'."
    if email_key and ("@" not in email_key or "." not in email_key.rsplit("@", 1)[-1]):
        return "Please enter a valid email address or leave it blank."
    return _valid_password(password)


def _insert_user(conn, username_key: str, email_key: str, password: str, theme: str) -> str | None:
    """Insert the account. Returns an error message, or None on success."""
    if email_key and conn.execute(
        "SELECT 1 FROM users WHERE email = %s", (email_key,)
    ).fetchone():
        return "That email is already in use."
    created = conn.execute(
        """
        INSERT INTO users (username, email, password_hash, app_state)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (username) DO NOTHING
        RETURNING username
        """,
        (
            username_key,
            email_key or None,
            _hash_password(password),
            Jsonb({"theme": _clean_theme(theme), "device_name": ""}),
        ),
    ).fetchone()
    return None if created else "That username is already in use."


def _check_login(conn, identifier: str, password: str) -> str | None:
    """Return the username if the password matches, else None."""
    # Usernames can't contain "@", so an identifier with "@" is an email.
    if "@" in identifier:
        query, key = "SELECT username, password_hash FROM users WHERE email = %s", _email_key(identifier)
    else:
        query, key = "SELECT username, password_hash FROM users WHERE username = %s", _username_key(identifier)
    row = conn.execute(query, (key,)).fetchone()
    if row is None or row["password_hash"] != _hash_password(password):
        return None
    return row["username"]


def register(
    username: str, email: str, password: str, theme: str = "light"
) -> tuple[bool, str, str]:
    username_key, email_key = _username_key(username), _email_key(email)
    error = _registration_error(username_key, email_key, password)
    if error:
        return False, error, ""
    with connect("register account") as conn:
        error = _insert_user(conn, username_key, email_key, password, theme)
    if error:
        return False, error, ""
    return True, "Account created.", username_key


def authenticate(identifier: str, password: str) -> tuple[bool, str, str]:
    with connect("sign in") as conn:
        username = _check_login(conn, identifier, password)
    if username is None:
        return False, _INVALID_LOGIN, ""
    return True, "Signed in.", username


def sign_up(
    username: str, email: str, password: str, theme: str = "light"
) -> tuple[bool, str, dict[str, Any] | None]:
    """Create the account and return it (with `has_profile`) in one connection."""
    username_key, email_key = _username_key(username), _email_key(email)
    error = _registration_error(username_key, email_key, password)
    if error:
        return False, error, None
    with connect("sign up") as conn:
        error = _insert_user(conn, username_key, email_key, password, theme)
        if error:
            return False, error, None
        account = conn.execute(_START_SESSION, (_clean_theme(theme), username_key)).fetchone()
    return True, "Account created.", account


def sign_in(
    identifier: str, password: str, theme: str = "light"
) -> tuple[bool, str, dict[str, Any] | None]:
    """Check the password, save the chosen theme, and return the account with
    `has_profile`, all in one connection."""
    with connect("sign in") as conn:
        username = _check_login(conn, identifier, password)
        if username is None:
            return False, _INVALID_LOGIN, None
        account = conn.execute(_START_SESSION, (_clean_theme(theme), username)).fetchone()
    return True, "Signed in.", account


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
