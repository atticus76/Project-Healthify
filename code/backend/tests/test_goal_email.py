import os
from pathlib import Path
import tempfile
from unittest import TestCase, mock

import pytest

from backend import alerts, auth_controller, goals


@pytest.mark.usefixtures("test_db")
class GoalEmailTests(TestCase):
    def setUp(self):
        # Goals are still in SQLite (temp file) until their S2-04 port; the
        # alert email setting is in the cloud test database.
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = mock.patch.object(goals, "DATABASE_PATH", Path(self.temp.name) / "test.db")
        self.database.start()
        self.addCleanup(self.database.stop)
        auth_controller.register("user", "", "Testpass1!")

    def test_goal_progress_uses_shared_alert_email_setting(self):
        from backend import email_alerts

        alerts.set_alert_email("user", "goal@example.com")
        with mock.patch.dict(
            "os.environ",
            {
                "SMTP_USERNAME": "sender@example.com",
                "SMTP_PASSWORD": "secret",
                "DATABASE_URL": os.environ["DATABASE_URL"],
            },
            clear=True,
        ), mock.patch("backend.email_alerts.dispatch") as dispatch:
            goals.save_goal("user", goals.GOAL_DAILY_STEPS, 10_000, True)
            result = goals.record_steps("user", 5_000)
            self.assertEqual(email_alerts.recipient("user"), "goal@example.com")

        self.assertEqual(result["milestones"], [25, 50])
