from pathlib import Path
import tempfile
from unittest import TestCase, mock

from backend import alerts, goals


class GoalEmailTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database_path = Path(self.temp.name) / "test.db"
        self.database = mock.patch.multiple(
            goals,
            DATABASE_PATH=self.database_path,
        )
        self.alert_database = mock.patch.object(
            alerts, "DATABASE_PATH", self.database_path
        )
        self.database.start()
        self.alert_database.start()
        self.addCleanup(self.database.stop)
        self.addCleanup(self.alert_database.stop)

    def test_goal_progress_uses_shared_alert_email_setting(self):
        from backend import email_alerts

        alerts.set_alert_email("user", "goal@example.com")
        with mock.patch.dict(
            "os.environ",
            {"SMTP_USERNAME": "sender@example.com", "SMTP_PASSWORD": "secret"},
            clear=True,
        ), mock.patch("backend.email_alerts.dispatch") as dispatch:
            goals.save_goal("user", goals.GOAL_DAILY_STEPS, 10_000, True)
            result = goals.record_steps("user", 5_000)
            self.assertEqual(email_alerts.recipient("user"), "goal@example.com")

        self.assertEqual(result["milestones"], [25, 50])
