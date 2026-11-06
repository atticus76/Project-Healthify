"""Tests for emailing US-04 alerts. No real mail is sent; smtplib is mocked.

Spec: code/specs/features/S2-03-health-abnormality-alerts.md
"""

import os
import smtplib
import unittest
from unittest import mock

import pytest

from backend import alerts, auth_controller, email_alerts


SMTP_ENV = {
    "SMTP_HOST": "smtp.example.com",
    "SMTP_PORT": "587",
    "SMTP_USERNAME": "healthify@example.com",
    "SMTP_PASSWORD": "app-password",
}
URGENT = {
    "title": "Abnormal heart rate spike",
    "message": "Your heart rate stayed above 130 BPM for 6 minutes.",
    "severity": alerts.SEVERITY_URGENT,
}
GAP = {**URGENT, "title": "Wearable data gap", "severity": alerts.SEVERITY_INFO}


USER = "user1"


@pytest.mark.usefixtures("test_db")
class EmailAlertTests(unittest.TestCase):
    def setUp(self):
        auth_controller.register(USER, "", "Testpass1!")
        # Clear everything except the test database's address.
        patcher = mock.patch.dict(
            "os.environ", {**SMTP_ENV, "DATABASE_URL": os.environ["DATABASE_URL"]}, clear=True
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    # --- the email itself ---

    def test_urgent_alert_email_is_marked_urgent(self):
        message = email_alerts.build_message(URGENT, "user@example.com")

        self.assertEqual(message["Subject"], "[Healthify] URGENT: Abnormal heart rate spike")
        self.assertEqual(message["To"], "user@example.com")
        self.assertEqual(message["X-Priority"], "1")

    def test_data_gap_email_is_not_marked_urgent(self):
        message = email_alerts.build_message(GAP, "user@example.com")

        self.assertEqual(message["Subject"], "[Healthify] Wearable data gap")
        self.assertIsNone(message["X-Priority"])

    def test_email_carries_message_link_and_disclaimer(self):
        body = email_alerts.build_message(URGENT, "user@example.com").get_content()

        self.assertIn(URGENT["message"], body)
        self.assertIn("/alerts", body)
        self.assertIn("not a medical device", body)

    # --- who gets it ---

    def test_saved_address_wins_over_env_default(self):
        with mock.patch.dict("os.environ", {"ALERT_EMAIL_TO": "env@example.com"}):
            self.assertEqual(email_alerts.recipient(USER), "env@example.com")
            alerts.set_alert_email(USER, "saved@example.com")
            self.assertEqual(email_alerts.recipient(USER), "saved@example.com")

    def test_turning_email_off_overrides_env_default(self):
        with mock.patch.dict("os.environ", {"ALERT_EMAIL_TO": "env@example.com"}):
            alerts.set_alert_email(USER, "")
            self.assertEqual(email_alerts.recipient(USER), "")

    def test_address_validation(self):
        self.assertTrue(email_alerts.is_valid_address("name@example.com"))
        for bad in ("", "name", "name@", "@example.com", "a b@example.com"):
            with self.subTest(bad=bad):
                self.assertFalse(email_alerts.is_valid_address(bad))

    # --- sending ---

    def test_send_uses_starttls_and_login(self):
        with mock.patch("smtplib.SMTP") as smtp_class:
            email_alerts.send(email_alerts.build_message(URGENT, "user@example.com"))

        smtp_class.assert_called_once_with("smtp.example.com", 587, timeout=email_alerts.SMTP_TIMEOUT_S)
        smtp = smtp_class.return_value.__enter__.return_value
        smtp.starttls.assert_called_once()
        smtp.login.assert_called_once_with("healthify@example.com", "app-password")
        smtp.send_message.assert_called_once()

    def test_send_without_credentials_raises(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(email_alerts.EmailNotConfigured):
                email_alerts.send(email_alerts.build_message(URGENT, "user@example.com"))

    def test_dispatch_emails_every_new_alert(self):
        alerts.set_alert_email(USER, "user@example.com")
        with mock.patch("smtplib.SMTP") as smtp_class:
            email_alerts.dispatch(USER, [URGENT, GAP]).join(timeout=5)

        smtp = smtp_class.return_value.__enter__.return_value
        self.assertEqual(smtp.send_message.call_count, 2)

    def test_dispatch_skips_without_address_or_alerts(self):
        with mock.patch("smtplib.SMTP") as smtp_class:
            self.assertIsNone(email_alerts.dispatch(USER, [URGENT]))
            alerts.set_alert_email(USER, "user@example.com")
            self.assertIsNone(email_alerts.dispatch(USER, []))
        smtp_class.assert_not_called()

    def test_dispatch_skips_when_smtp_not_configured(self):
        alerts.set_alert_email(USER, "user@example.com")
        for key in SMTP_ENV:
            os.environ.pop(key)
        with mock.patch("smtplib.SMTP") as smtp_class:
            self.assertIsNone(email_alerts.dispatch(USER, [URGENT]))
        smtp_class.assert_not_called()

    def test_dispatch_skips_the_database_when_there_is_nothing_to_send(self):
        # Checking the saved address costs a database round trip; don't make
        # one when email is off or there are no alerts.
        with mock.patch.object(alerts, "get_alert_email") as lookup:
            email_alerts.dispatch(USER, [])
            for key in SMTP_ENV:
                os.environ.pop(key)
            email_alerts.dispatch(USER, [URGENT])
        lookup.assert_not_called()

    def test_mail_server_failure_is_logged_not_raised(self):
        alerts.set_alert_email(USER, "user@example.com")
        with mock.patch("smtplib.SMTP", side_effect=smtplib.SMTPConnectError(421, "down")), \
                self.assertLogs("backend.email_alerts", level="ERROR"):
            email_alerts.dispatch(USER, [URGENT]).join(timeout=5)

    def test_send_test_requires_an_address(self):
        with self.assertRaises(ValueError):
            email_alerts.send_test(USER)


if __name__ == "__main__":
    unittest.main()
