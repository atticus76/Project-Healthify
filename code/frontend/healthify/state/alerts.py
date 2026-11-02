"""State for health abnormality alerts (US-04 / FR-02).

Spec: code/specs/features/S2-03-health-abnormality-alerts.md

Alerts reach the user three ways: an in-app toast plus the Alerts page
(always), a browser notification (only if the user granted permission), so an
urgent alert still pops up when the Healthify tab is in the background, and an
email (only if SMTP is set up in .env and an address is saved).
"""

import json
import smtplib
from datetime import datetime

import reflex as rx

from backend import alerts, email_alerts
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


def notify(new_alerts: list[dict], user_id: str = DEMO_USER_ID) -> list:
    """Deliver freshly created alerts: start the emails, return the UI events."""
    email_alerts.dispatch(user_id, new_alerts)
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
    alert_email: str = ""
    email_input: str = ""
    email_configured: bool = False
    email_message: str = ""
    email_error: str = ""
    sending_test: bool = False

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
        """on_load for /alerts: read the list, email settings, and browser permission."""
        self.load()
        self.alert_email = email_alerts.recipient(DEMO_USER_ID)
        self.email_input = self.alert_email
        self.email_configured = email_alerts.is_configured()
        self.email_message = ""
        self.email_error = ""
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

    def set_email_input(self, value: str):
        self.email_input = value

    def save_email(self, form_data: dict):
        """on_submit for the email form; the address comes from email_input."""
        self.email_message = ""
        self.email_error = ""
        address = self.email_input.strip()
        if not email_alerts.is_valid_address(address):
            self.email_error = "Enter a valid email address, like name@example.com."
            return
        alerts.set_alert_email(DEMO_USER_ID, address)
        self.alert_email = address
        self.email_message = f"Alerts will be emailed to {address}."

    def turn_off_email(self):
        alerts.set_alert_email(DEMO_USER_ID, "")
        self.alert_email = ""
        self.email_input = ""
        self.email_error = ""
        self.email_message = "Email alerts are off."

    def send_test_email(self):
        self.email_message = ""
        self.email_error = ""
        self.sending_test = True
        yield  # show the spinner while the mail server responds
        try:
            sent_to = email_alerts.send_test(DEMO_USER_ID)
            self.email_message = f"Test email sent to {sent_to}. Check your inbox (and spam folder)."
        except (ValueError, email_alerts.EmailNotConfigured) as exc:
            self.email_error = str(exc)
        except smtplib.SMTPAuthenticationError:
            self.email_error = "The mail server rejected SMTP_USERNAME / SMTP_PASSWORD. For Gmail, use an app password."
        except (smtplib.SMTPException, OSError) as exc:
            self.email_error = f"Couldn't send the test email: {exc}"
        finally:
            self.sending_test = False
