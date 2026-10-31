"""State for health abnormality alerts (US-04 / FR-02).

Spec: code/specs/features/S2-03-health-abnormality-alerts.md

Alerts reach the user two ways: an in-app toast plus the Alerts page (always),
and a browser notification (only if the user granted permission), so an
urgent alert still pops up when the Healthify tab is in the background.
"""

import json
from datetime import datetime

import reflex as rx

from backend import alerts
from backend.google_health import DEMO_USER_ID


def _fmt(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone().strftime("%b %d, %I:%M %p")


def _browser_notification(alert: dict) -> str:
    # tag stops the OS stacking duplicates; urgent alerts stay until dismissed.
    options = {
        "body": f"{alert['message']}\n{alerts.DISCLAIMER}",
        "tag": f"healthify-alert-{alert['id']}",
        "requireInteraction": alert["severity"] == alerts.SEVERITY_URGENT,
    }
    return (
        "if ('Notification' in window && Notification.permission === 'granted') {"
        f"new Notification({json.dumps(alert['title'])}, {json.dumps(options)});"
        "}"
    )


def notify(new_alerts: list[dict]) -> list:
    """Events that deliver freshly created alerts to the user."""
    events = []
    for alert in new_alerts:
        toast = rx.toast.error if alert["severity"] == alerts.SEVERITY_URGENT else rx.toast.warning
        events.append(toast(alert["message"], title=alert["title"], duration=15_000, close_button=True))
        events.append(rx.call_script(_browser_notification(alert)))
    if new_alerts:
        events.append(AlertState.load)
    return events


class AlertState(rx.State):
    items: list[dict[str, str]] = []
    unread: int = 0
    # default | granted | denied | unsupported
    permission: str = "default"

    def load(self):
        rows = alerts.list_alerts(DEMO_USER_ID)
        self.items = [
            {
                "id": str(row["id"]),
                "title": row["title"],
                "message": row["message"],
                "severity": row["severity"],
                "when": _fmt(row["started_at"]),
                "acknowledged": "yes" if row["acknowledged"] else "",
            }
            for row in rows
        ]
        self.unread = sum(1 for row in rows if not row["acknowledged"])

    def load_page(self):
        """on_load for /alerts: read the list and the browser's permission."""
        self.load()
        return rx.call_script(
            "'Notification' in window ? Notification.permission : 'unsupported'",
            callback=AlertState.set_permission,
        )

    def set_permission(self, value: str):
        self.permission = value or "unsupported"

    def request_permission(self):
        return rx.call_script(
            "'Notification' in window ? Notification.requestPermission() : 'unsupported'",
            callback=AlertState.set_permission,
        )

    def acknowledge(self, alert_id: str):
        alerts.acknowledge(DEMO_USER_ID, int(alert_id))
        self.load()

    def acknowledge_all(self):
        alerts.acknowledge(DEMO_USER_ID)
        self.load()
