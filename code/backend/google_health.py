"""Device connection service: ties OAuth + token storage + Google Health API calls together.

AI-GENERATED (Claude) for the device-connection demo.

The Reflex state only calls the functions in the "public API" section below;
it never touches tokens directly.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import requests

from . import google_oauth, token_store

API_BASE = "https://health.googleapis.com/v4/users/me"

# Until accounts exist (FR-05) everyone is the same user, matching the profile page.
DEMO_USER_ID = "new-user"

# Refresh a little before the access token actually expires.
EXPIRY_SKEW_S = 60

# data type -> pageSize (results come back newest first)
SYNC_DATA_TYPES = {
    "heart-rate": 1,
    "daily-resting-heart-rate": 1,
    "daily-heart-rate-variability": 1,
    "steps": 50,
    "sleep": 1,
    "exercise": 1,
}


class ReconnectRequired(Exception):
    """The stored grant no longer works (revoked, or the 7-day Testing-mode expiry)."""


class ConnectionFailed(Exception):
    """The OAuth callback could not be completed."""


# --- public API ------------------------------------------------------------------

def start_connection(user_id: str = DEMO_USER_ID) -> str:
    """Create a pending request and return the Google URL to send the browser to."""
    state = google_oauth.make_state()
    verifier, challenge = google_oauth.make_pkce_pair()
    token_store.save_pending(state, verifier, user_id)
    return google_oauth.build_authorization_url(state, challenge)


def complete_connection(params: dict[str, str]) -> str:
    """Handle the query string Google redirected back with. Returns the user_id."""
    if "error" in params:
        # e.g. error=access_denied when the user clicks Cancel
        raise ConnectionFailed(f"Google returned: {params['error']}")

    state, code = params.get("state", ""), params.get("code", "")
    if not state or not code:
        raise ConnectionFailed("Missing code or state in the callback URL.")

    pending = token_store.pop_pending(state)
    if pending is None:
        # Unknown, reused, or expired state: possible CSRF, or the user
        # refreshed the callback page. Either way, don't trust it.
        raise ConnectionFailed("This sign-in link expired or was already used. Try connecting again.")

    try:
        tokens = google_oauth.exchange_code(code, pending["code_verifier"])
    except google_oauth.OAuthError as exc:
        raise ConnectionFailed(f"Token exchange failed: {exc}") from exc

    if not tokens["refresh_token"]:
        raise ConnectionFailed("Google did not return a refresh token. Try connecting again.")

    missing = [s for s in google_oauth.SCOPES if s.startswith("https://") and s not in tokens["scope"]]
    if missing:
        # Google's consent screen lets users untick individual scopes.
        raise ConnectionFailed("Healthify needs all of the requested health permissions. Please allow them all.")

    token_store.save_connection(pending["user_id"], tokens)
    return pending["user_id"]


def get_status(user_id: str = DEMO_USER_ID) -> dict[str, Any] | None:
    """Connection info safe to show in the UI (no tokens)."""
    conn = token_store.get_connection(user_id)
    if conn is None:
        return None
    return {
        "status": conn["status"],
        "email": conn["email"] or "",
        "device_name": conn["device_name"] or "",
        "connected_at": conn["connected_at"],
        "last_sync_at": conn["last_sync_at"],
    }


def disconnect(user_id: str = DEMO_USER_ID) -> None:
    conn = token_store.get_connection(user_id)
    if conn is not None:
        # Revoking the refresh token revokes the whole grant.
        google_oauth.revoke_token(conn["refresh_token"])
    token_store.delete_connection(user_id)


def sync(user_id: str = DEMO_USER_ID) -> dict[str, dict]:
    """Fetch the latest data for each SYNC_DATA_TYPES entry. Returns {data_type: response_json}."""
    results: dict[str, dict] = {}
    for data_type, page_size in SYNC_DATA_TYPES.items():
        results[data_type] = _api_get(user_id, f"/dataTypes/{data_type}/dataPoints", {"pageSize": page_size})
    token_store.record_sync(user_id, _device_name(results))
    return results


# --- tokens & HTTP -----------------------------------------------------------------

def _access_token(user_id: str, force_refresh: bool = False) -> str:
    conn = token_store.get_connection(user_id)
    if conn is None:
        raise ReconnectRequired("No Google account connected.")
    if conn["status"] == token_store.STATUS_RECONNECT:
        raise ReconnectRequired("Google access expired. Please reconnect.")

    if not force_refresh and conn["expires_at"] - EXPIRY_SKEW_S > time.time():
        return conn["access_token"]

    try:
        fresh = google_oauth.refresh_access_token(conn["refresh_token"])
    except google_oauth.OAuthError as exc:
        if exc.error_code == "invalid_grant":
            token_store.mark_reconnect_required(user_id)
            raise ReconnectRequired("Google access expired or was revoked. Please reconnect.") from exc
        raise
    token_store.update_access_token(user_id, fresh["access_token"], fresh["expires_at"])
    return fresh["access_token"]


def _api_get(user_id: str, path: str, params: dict) -> dict:
    """GET with a Bearer token; on 401, refresh once and retry."""
    for attempt in range(2):
        token = _access_token(user_id, force_refresh=attempt > 0)
        resp = requests.get(
            API_BASE + path,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=google_oauth.REQUEST_TIMEOUT_S,
        )
        if resp.status_code == 401 and attempt == 0:
            continue
        resp.raise_for_status()
        return resp.json()
    raise ReconnectRequired("Google rejected our access token. Please reconnect.")


# --- turning API responses into display lines -----------------------------------------

def _points(results: dict, data_type: str) -> list[dict]:
    return results.get(data_type, {}).get("dataPoints", []) or []


def _device_name(results: dict) -> str:
    for body in results.values():
        for point in body.get("dataPoints", []) or []:
            name = point.get("dataSource", {}).get("device", {}).get("displayName")
            if name:
                return name
    return ""


def _civil(civil: dict) -> str:
    d, t = civil.get("date", {}), civil.get("time", {})
    try:
        dt = datetime(d["year"], d["month"], d["day"], t.get("hours", 0), t.get("minutes", 0))
    except (KeyError, TypeError):
        return ""
    return dt.strftime("%b %d, %I:%M %p")


def _date(d: dict) -> str:
    try:
        return datetime(d["year"], d["month"], d["day"]).strftime("%b %d")
    except (KeyError, TypeError):
        return ""


def _iso(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def _hours_minutes(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 3600}h {seconds % 3600 // 60}m"


def summarize(results: dict) -> list[str]:
    lines: list[str] = []

    if hr := _points(results, "heart-rate"):
        p = hr[0]["heartRate"]
        lines.append(f"Latest heart rate: {p['beatsPerMinute']} bpm ({_civil(p['sampleTime'].get('civilTime', {}))})")

    if rhr := _points(results, "daily-resting-heart-rate"):
        p = rhr[0]["dailyRestingHeartRate"]
        lines.append(f"Resting heart rate: {p['beatsPerMinute']} bpm ({_date(p['date'])})")

    if hrv := _points(results, "daily-heart-rate-variability"):
        p = hrv[0]["dailyHeartRateVariability"]
        lines.append(f"Heart rate variability: {p['averageHeartRateVariabilityMilliseconds']} ms ({_date(p['date'])})")

    if steps := _points(results, "steps"):
        total = sum(int(p["steps"]["count"]) for p in steps)
        lines.append(f"Steps in the latest {len(steps)} recorded minutes: {total:,}")

    if sleep := _points(results, "sleep"):
        interval = sleep[0]["sleep"]["interval"]
        start, end = _iso(interval.get("startTime", "")), _iso(interval.get("endTime", ""))
        if start and end:
            lines.append(f"Last sleep: {_hours_minutes((end - start).total_seconds())} (ended {end.astimezone():%b %d, %I:%M %p})")

    if ex := _points(results, "exercise"):
        e = ex[0]["exercise"]
        kcal = e.get("metricsSummary", {}).get("caloriesKcal")
        duration = _hours_minutes(float(e.get("activeDuration", "0s").rstrip("s") or 0))
        lines.append(f"Last exercise: {e.get('displayName', 'Workout')}, {duration}" + (f", {kcal} kcal" if kcal else ""))

    return lines or ["Connected, but Google Health returned no recent data yet. Sync your Charge 6 in the Google Health app."]
