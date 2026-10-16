"""Google OAuth 2.0 (authorization code flow + PKCE) for the Google Health API.

AI-GENERATED (Claude) for the device-connection demo. Atticus is rewriting this
by hand on the `device-connection` branch; treat this as a reference version.

Written with plain `requests` on purpose, so every HTTP call in the OAuth
dance is visible instead of hidden inside a library:

    1. build_authorization_url()  -> browser goes to Google's consent screen
    2. Google redirects back to GOOGLE_REDIRECT_URI with ?code=...&state=...
    3. exchange_code()             -> POST to the token endpoint: code -> tokens
    4. refresh_access_token()      -> POST to the token endpoint: refresh token -> new access token
    5. revoke_token()              -> POST to the revoke endpoint on disconnect
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"

# Must match an "Authorized redirect URI" on the OAuth client EXACTLY
# (scheme, host, port, path). Reflex serves pages on :3000 in dev.
DEFAULT_REDIRECT_URI = "http://localhost:3000/devices/callback"

# Least privilege: only the three scopes registered on our consent screen,
# plus openid/email so we can show which Google account is connected.
SCOPES = [
    "openid",
    "email",
    "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
    "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly",
    "https://www.googleapis.com/auth/googlehealth.sleep.readonly",
]

REQUEST_TIMEOUT_S = 15


class OAuthError(Exception):
    """Google rejected an OAuth request (bad code, revoked token, etc.)."""

    def __init__(self, message: str, error_code: str = ""):
        super().__init__(message)
        self.error_code = error_code  # e.g. "invalid_grant"


def _client_id() -> str:
    return os.environ["GOOGLE_CLIENT_ID"]


def _client_secret() -> str:
    return os.environ["GOOGLE_CLIENT_SECRET"]


def redirect_uri() -> str:
    return os.environ.get("GOOGLE_REDIRECT_URI", DEFAULT_REDIRECT_URI)


def is_configured() -> bool:
    return bool(os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET"))


# --- PKCE --------------------------------------------------------------------
# The verifier is a random secret we keep server-side. Google only sees its
# SHA-256 hash (the challenge) in step 1, and the verifier itself in step 3,
# so a stolen authorization code is useless without it.

def make_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def make_state() -> str:
    """Random, unguessable value that ties the callback to the request we started (CSRF protection)."""
    return secrets.token_urlsafe(32)


# --- Step 1: send the user to Google --------------------------------------------

def build_authorization_url(state: str, code_challenge: str) -> str:
    params = {
        "client_id": _client_id(),
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",   # ask for a refresh token
        "prompt": "consent",        # always show consent so Google always returns a refresh token
        "include_granted_scopes": "true",
    }
    return f"{AUTH_ENDPOINT}?{urlencode(params)}"


# --- Steps 3 & 4: talk to the token endpoint ------------------------------------

def _post_token_endpoint(data: dict) -> dict:
    resp = requests.post(TOKEN_ENDPOINT, data=data, timeout=REQUEST_TIMEOUT_S)
    body = resp.json() if resp.content else {}
    if resp.status_code != 200:
        raise OAuthError(
            body.get("error_description") or body.get("error") or f"HTTP {resp.status_code}",
            body.get("error", ""),
        )
    return body


def exchange_code(code: str, code_verifier: str) -> dict:
    """Trade the one-time authorization code for tokens.

    Returns a dict with access_token, refresh_token, expires_at (unix seconds),
    scope, and email (from the ID token).
    """
    body = _post_token_endpoint({
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": code_verifier,
        "client_id": _client_id(),
        "client_secret": _client_secret(),
        "redirect_uri": redirect_uri(),  # must match step 1
    })
    return {
        "access_token": body["access_token"],
        "refresh_token": body.get("refresh_token", ""),
        "expires_at": int(time.time()) + int(body.get("expires_in", 3600)),
        "scope": body.get("scope", ""),
        "email": _email_from_id_token(body.get("id_token", "")),
    }


def refresh_access_token(refresh_token: str) -> dict:
    """Use the long-lived refresh token to get a new ~1 hour access token."""
    body = _post_token_endpoint({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": _client_id(),
        "client_secret": _client_secret(),
    })
    return {
        "access_token": body["access_token"],
        "expires_at": int(time.time()) + int(body.get("expires_in", 3600)),
    }


def revoke_token(token: str) -> None:
    """Tell Google to invalidate the grant. Best effort: we delete our copy either way."""
    try:
        requests.post(REVOKE_ENDPOINT, data={"token": token}, timeout=REQUEST_TIMEOUT_S)
    except requests.RequestException:
        pass


def _email_from_id_token(id_token: str) -> str:
    """Read the email claim from the ID token (a JWT: header.payload.signature).

    We skip signature verification because this token came straight from
    Google's token endpoint over HTTPS, not from the browser.
    """
    try:
        payload = id_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload)).get("email", "")
    except (IndexError, ValueError):
        return ""
