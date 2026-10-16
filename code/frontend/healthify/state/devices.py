"""State for the Connect Device page and the OAuth callback page.

AI-GENERATED (Claude) for the device-connection demo.
"""

from datetime import datetime

import reflex as rx
import requests

from backend import google_health, google_oauth


def _fmt(ts: int | None) -> str:
    return datetime.fromtimestamp(ts).strftime("%b %d, %I:%M %p") if ts else "never"


class DeviceState(rx.State):
    status: str = "disconnected"  # disconnected | connected | reconnect_required
    email: str = ""
    device_name: str = ""
    last_sync: str = "never"
    summaries: list[str] = []
    message: str = ""
    error: str = ""
    busy: bool = False
    configured: bool = True

    def _load_status(self):
        self.configured = google_oauth.is_configured()
        info = google_health.get_status()
        if info is None:
            self.status, self.email, self.device_name, self.last_sync = "disconnected", "", "", "never"
            return
        self.status = info["status"]
        self.email = info["email"]
        self.device_name = info["device_name"]
        self.last_sync = _fmt(info["last_sync_at"])

    def load(self):
        """on_load for /devices."""
        self._load_status()

    def start_connect(self):
        self.error = ""
        self.message = ""
        if not google_oauth.is_configured():
            self.error = "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET are missing from .env."
            return
        # Same-tab navigation to Google's consent screen.
        return rx.redirect(google_health.start_connection())

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

        self.message = "Google account connected."
        self._sync()
        # replace=True keeps the one-time ?code= URL out of browser history.
        return rx.redirect("/devices", replace=True)

    def sync_now(self):
        self.busy = True
        self.error = ""
        self.message = ""
        yield  # push the spinner to the browser before the slow HTTP calls
        self._sync()
        self.busy = False

    def _sync(self):
        try:
            results = google_health.sync()
            self.summaries = google_health.summarize(results)
        except google_health.ReconnectRequired as exc:
            self.error = str(exc)
        except requests.HTTPError as exc:
            self.error = f"Google Health API error ({exc.response.status_code}). Sync failed."
        except requests.RequestException:
            self.error = "Couldn't reach Google Health. Sync failed."
        self._load_status()

    def disconnect_account(self):
        google_health.disconnect()
        self.summaries = []
        self.error = ""
        self.message = "Disconnected and revoked Healthify's access to your Google account."
        self._load_status()
