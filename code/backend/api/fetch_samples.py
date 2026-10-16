"""
Full transparency, generated with Claude. Going to read up on OAuth 2.0 so I can fully understand how tokens
and authorization works tonight, but just wanted to get a script that works for everyone out tonight and some JSON files.

To run this script (from the scripts folder)...
1. Activate your virtual environment for Python (differs across OS' I believe?)
2. pip install -r requirements.txt
3. python3 fetch_samples.py
4. deactivate

- Atticus
"""

import os
from dotenv import load_dotenv

import json
from pathlib import Path

from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
OUT_DIR = REPO_ROOT / "data" / "samples"

load_dotenv(REPO_ROOT / ".env")

# Resolve relative to the repo root so the script works from any directory.
TOKEN_FILE = REPO_ROOT / os.environ.get("GOOGLE_TOKEN_PATH", ".token.json")

CLIENT_CONFIG = {
    "installed": {
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

BASE_URL = "https://health.googleapis.com/v4/users/me"

SCOPES = [
    "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
    "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly",
    "https://www.googleapis.com/auth/googlehealth.sleep.readonly",
    "https://www.googleapis.com/auth/googlehealth.nutrition.readonly",
    "https://www.googleapis.com/auth/googlehealth.logged_symptoms.readonly",
    "https://www.googleapis.com/auth/googlehealth.mindfulness.readonly",
    "https://www.googleapis.com/auth/googlehealth.ecg.readonly",
    "https://www.googleapis.com/auth/googlehealth.irn.readonly"
]

# Data types we expect Healthify to use. Results come back newest first,
# so a small pageSize gives us the most recent data without a date filter.
DATA_TYPES = {
    "steps": 50,
    "heart-rate": 50,
    "daily-resting-heart-rate": 14,
    "heart-rate-variability": 50,
    "daily-heart-rate-variability": 14,
    "sleep": 5,            # max pageSize for sleep is 25
    "exercise": 10,        # max pageSize for exercise is 25
    "active-zone-minutes": 50,
    "total-calories": 50,
    "distance": 50,
    "daily-oxygen-saturation": 14,
}


def get_credentials() -> Credentials:
    """Load cached token, refresh it, or run the browser consent flow."""
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())  # trade refresh token for a new access token
        except Exception as e:
            print(f"Refresh failed ({e}); re-running consent flow.")
            creds = None

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_config(CLIENT_CONFIG, SCOPES)
        # Starts a tiny local server on :8080 to catch the redirect with ?code=...
        # then exchanges the code (+ client secret) for access & refresh tokens.
        creds = flow.run_local_server(port=8080, access_type="offline", prompt="consent")

    TOKEN_FILE.write_text(creds.to_json())
    return creds


def main() -> None:
    session = AuthorizedSession(get_credentials())  # adds "Authorization: Bearer ..." for us
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for data_type, page_size in DATA_TYPES.items():
        url = f"{BASE_URL}/dataTypes/{data_type}/dataPoints"
        resp = session.get(url, params={"pageSize": page_size})
        if resp.status_code != 200:
            print(f"[{resp.status_code}] {data_type}: {resp.text[:200]}")
            continue
        body = resp.json()
        out = OUT_DIR / f"{data_type}.json"
        out.write_text(json.dumps(body, indent=2))
        print(f"[200] {data_type}: {len(body.get('dataPoints', []))} points -> {out.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
