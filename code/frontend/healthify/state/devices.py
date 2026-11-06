"""State for the Connect Device page and the OAuth callback page.

AI-GENERATED (Claude) for the device-connection demo.
"""

from datetime import datetime

import reflex as rx
import requests

from backend import alerts, google_health, google_oauth
from backend.db import DatabaseError

from .alerts import notify
from .session import SessionState


def _fmt(ts: int | None) -> str:
    return datetime.fromtimestamp(ts).strftime("%b %d, %I:%M %p") if ts else "never"


class DeviceState(SessionState):
    status: str = "disconnected"  # disconnected | connected | sync_failed | reconnect_required
    sync_error: str = ""  # why the last sync failed (sync_failed only)
    next_sync: str = ""  # when the scheduler will try again
    email: str = ""
    device_name: str = ""
    last_sync: str = "never"
    summaries: list[str] = []
    message: str = ""
    error: str = ""
    busy: bool = False
    configured: bool = True

    def _user(self) -> str:
        return self.username

    def _load_status(self):
        self.configured = google_oauth.is_configured()
        try:
            info = google_health.get_status(self._user())
        except DatabaseError as exc:
            self.error = str(exc)
            return
        if info is None:
            self.status, self.email, self.device_name, self.last_sync = "disconnected", "", "", "never"
            return
        self.status = info["status"]
        self.email = info["email"]
        self.device_name = info["device_name"]
        self.last_sync = _fmt(info["last_sync_at"])
        self.sync_error = info["last_sync_error"]
        self.next_sync = _fmt(info["next_sync_at"]) if info["next_sync_at"] else "soon"

    def load(self):
        """on_load for /devices."""
        self._load_status()

    def start_connect(self):
        self.error = ""
        self.message = ""
        if not google_oauth.is_configured():
            self.error = "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET are missing from .env."
            return
        try:
            url = google_health.start_connection(self._user())
        except DatabaseError as exc:
            self.error = str(exc)
            return
        # Same-tab navigation to Google's consent screen.
        return rx.redirect(url)

    def handle_callback(self):
        """on_load for /devices/callback: Google redirects here with ?code=&state=."""
        self.error = ""
        self.message = ""
        params = dict(self.router.url.query_parameters)
        try:
            google_health.complete_connection(params)
        except google_health.ConnectionFailed as exc:
            self.error = str(exc)
            return rx.redirect("/devices", replace=True)
        except requests.RequestException:
            self.error = "Couldn't reach Google to finish connecting. Check your internet and try again."
            return rx.redirect("/devices", replace=True)
        except DatabaseError as exc:
            self.error = str(exc)
            return rx.redirect("/devices", replace=True)

        self.message = "Google account connected."
        events = self._sync()
        # replace=True keeps the one-time ?code= URL out of browser history.
        return [rx.redirect("/devices", replace=True), *events]

    def sync_now(self):
        self.busy = True
        self.error = ""
        self.message = ""
        yield  # push the spinner to the browser before the slow HTTP calls
        events = self._sync()
        self.busy = False
        yield events

    def _sync(self) -> list:
        """Sync, then return the events that deliver any new alerts (US-04)."""
        events = []
        try:
            results = google_health.sync(self._user())
            self.summaries = google_health.summarize(results)
            events = notify(alerts.check_telemetry(results, self._user()), self._user())
        except google_health.ReconnectRequired as exc:
            self.error = str(exc)
        except requests.RequestException as exc:
            # Recorded like a scheduled failure so the page shows "Sync failed"
            # and the scheduler backs off.
            try:
                self.error = google_health.record_sync_failure(self._user(), exc) + " Sync failed."
            except DatabaseError as db_exc:
                self.error = str(db_exc)
        except DatabaseError as exc:
            self.error = str(exc)
        self._load_status()
        return events

    def disconnect_account(self):
        try:
            google_health.disconnect(self._user())
        except DatabaseError as exc:
            self.error = str(exc)
            return
        self.summaries = []
        self.error = ""
        self.message = "Disconnected and revoked Healthify's access to your Google account."
        self._load_status()
