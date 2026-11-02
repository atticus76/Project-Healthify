"""Tests for emailing US-04 alerts. No real mail is sent; smtplib is mocked.

Spec: code/specs/features/S2-03-health-abnormality-alerts.md
"""

from pathlib import Path
import smtplib
import tempfile
import unittest
from unittest import mock

from backend import alerts, email_alerts


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


class EmailAlertTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for patcher in (
            mock.patch.object(alerts, "DATABASE_PATH", Path(self.tmp.name) / "test.db"),
            mock.patch.dict("os.environ", SMTP_ENV, clear=True),
        ):
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
            self.assertEqual(email_alerts.recipient("u"), "env@example.com")
            alerts.set_alert_email("u", "saved@example.com")
            self.assertEqual(email_alerts.recipient("u"), "saved@example.com")

    def test_turning_email_off_overrides_env_default(self):
        with mock.patch.dict("os.environ", {"ALERT_EMAIL_TO": "env@example.com"}):
            alerts.set_alert_email("u", "")
            self.assertEqual(email_alerts.recipient("u"), "")

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
        alerts.set_alert_email("u", "user@example.com")
        with mock.patch("smtplib.SMTP") as smtp_class:
            email_alerts.dispatch("u", [URGENT, GAP]).join(timeout=5)

        smtp = smtp_class.return_value.__enter__.return_value
        self.assertEqual(smtp.send_message.call_count, 2)

    def test_dispatch_skips_without_address_or_alerts(self):
        with mock.patch("smtplib.SMTP") as smtp_class:
            self.assertIsNone(email_alerts.dispatch("u", [URGENT]))
            alerts.set_alert_email("u", "user@example.com")
            self.assertIsNone(email_alerts.dispatch("u", []))
        smtp_class.assert_not_called()

    def test_dispatch_skips_when_smtp_not_configured(self):
        alerts.set_alert_email("u", "user@example.com")
        with mock.patch.dict("os.environ", {}, clear=True), mock.patch("smtplib.SMTP") as smtp_class:
            self.assertIsNone(email_alerts.dispatch("u", [URGENT]))
        smtp_class.assert_not_called()

    def test_mail_server_failure_is_logged_not_raised(self):
        alerts.set_alert_email("u", "user@example.com")
        with mock.patch("smtplib.SMTP", side_effect=smtplib.SMTPConnectError(421, "down")), \
                self.assertLogs("backend.email_alerts", level="ERROR"):
            email_alerts.dispatch("u", [URGENT]).join(timeout=5)

    def test_send_test_requires_an_address(self):
        with self.assertRaises(ValueError):
            email_alerts.send_test("u")


if __name__ == "__main__":
    unittest.main()
