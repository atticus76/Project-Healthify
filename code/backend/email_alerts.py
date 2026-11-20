"""Email delivery for health alerts (US-04).

Spec: code/specs/features/S2-03-health-abnormality-alerts.md

Sends each new alert to the address saved on the Alerts page (or ALERT_EMAIL_TO
from .env if none is saved) via the configured HTTPS or SMTP provider.
See .env.example for sender settings.

Sending happens on a background thread so a slow mail server never freezes the
page. Failures are logged; the in-app and browser alerts still go out.
"""

from __future__ import annotations

import logging
import os
import re
import smtplib
import threading
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from . import alerts

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

log = logging.getLogger(__name__)

SMTP_TIMEOUT_S = 15
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EmailNotConfigured(Exception):
    """The selected email provider is missing required settings."""


def reload_config() -> None:
    """Reload local SMTP settings so page state reflects the current .env."""
    load_dotenv(REPO_ROOT / ".env", override=True)


def is_valid_address(address: str) -> bool:
    return bool(EMAIL_PATTERN.match(address.strip()))


def is_configured() -> bool:
    if os.environ.get("RESEND_API_KEY"):
        return bool(os.environ.get("SMTP_FROM"))
    return bool(os.environ.get("SMTP_USERNAME") and os.environ.get("SMTP_PASSWORD"))


def recipient(user_id: str) -> str:
    """The address alerts go to: the one saved in the app, else ALERT_EMAIL_TO.

    Clearing the address in the app turns email off even if ALERT_EMAIL_TO is set.
    """
    saved = alerts.get_alert_email(user_id)
    if saved is not None:
        return saved
    return os.environ.get("ALERT_EMAIL_TO", "").strip()


def build_message(alert: dict[str, Any], to: str) -> EmailMessage:
    urgent = alert["severity"] == alerts.SEVERITY_URGENT
    sender = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USERNAME", "")
    app_url = os.environ.get("HEALTHIFY_URL", "http://localhost:3000").rstrip("/")

    message = EmailMessage()
    message["Subject"] = f"[Healthify] {'URGENT: ' if urgent else ''}{alert['title']}"
    message["From"] = f"Healthify Alerts <{sender}>"
    message["To"] = to
    if urgent:
        message["X-Priority"] = "1"
        message["Importance"] = "high"
    message.set_content(
        f"{alert['title']}\n\n"
        f"{alert['message']}\n\n"
        f"See your alert history: {app_url}/alerts\n\n"
        f"{alerts.DISCLAIMER}\n"
    )
    return message


def send(message: EmailMessage) -> None:
    """Send one message. Raises EmailNotConfigured or smtplib/OSError errors."""
    if not is_configured():
        raise EmailNotConfigured(
            "Configure RESEND_API_KEY and SMTP_FROM for HTTPS email, or SMTP credentials for SMTP."
        )
    if api_key := os.environ.get("RESEND_API_KEY"):
        payload = {
            "from": str(message["From"]), "to": [str(message["To"])],
            "subject": str(message["Subject"]), "text": message.get_content(),
        }
        headers = {key: str(message[key]) for key in ("X-Priority", "Importance") if key in message}
        if headers:
            payload["headers"] = headers
        try:
            response = requests.post(
                "https://api.resend.com/emails", json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=SMTP_TIMEOUT_S, allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise OSError("Could not reach the Resend email service.") from exc
        if not 200 <= response.status_code < 300:
            raise OSError(f"Resend rejected delivery (HTTP {response.status_code}). Check the sender domain and API key.")
        return
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT_S) as smtp:
        smtp.starttls()
        smtp.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
        smtp.send_message(message)


def _send_all(messages: list[EmailMessage]) -> None:
    for message in messages:
        try:
            send(message)
        except (EmailNotConfigured, smtplib.SMTPException, OSError):
            log.exception("Couldn't email alert %r to %s", message["Subject"], message["To"])


def dispatch(user_id: str, new_alerts: list[dict[str, Any]]) -> threading.Thread | None:
    """Email new alerts in the background. Returns the thread, or None if skipped."""
    # Cheap checks first: looking up the saved address is a database call.
    if not new_alerts or not is_configured():
        return None
    to = recipient(user_id)
    if not to:
        return None
    messages = [build_message(alert, to) for alert in new_alerts]
    thread = threading.Thread(target=_send_all, args=(messages,), daemon=True)
    thread.start()
    return thread


def send_test(user_id: str) -> str:
    """Send a sample alert right away so the user can check their settings."""
    to = recipient(user_id)
    if not to:
        raise ValueError("Save an email address first.")
    sample = {
        "title": "Test alert",
        "message": "This is a test. Healthify alerts will arrive at this address.",
        "severity": alerts.SEVERITY_INFO,
    }
    send(build_message(sample, to))
    return to
