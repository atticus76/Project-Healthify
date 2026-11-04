from datetime import date
from pathlib import Path
from unittest import TestCase, mock

from backend import goals


class GoalTests(TestCase):
    def setUp(self):
        self.database = mock.patch.object(
            goals, "DATABASE_PATH", Path(self._testMethodName + ".db")
        )
        self.database.start()
        self.addCleanup(self.database.stop)
        self.addCleanup(lambda: Path(self._testMethodName + ".db").unlink(missing_ok=True))

    def test_saves_daily_step_goal_and_records_milestones(self):
        goals.save_goal("user", goals.GOAL_DAILY_STEPS, 10_000, True)

        result = goals.record_steps("user", 5_000, date(2026, 11, 4))

        self.assertEqual(result["milestones"], [25, 50])
        self.assertEqual(goals.get_progress("user", date(2026, 11, 4))["steps"], 5_000)

    def test_low_incomplete_day_gets_motivational_prompt(self):
        goals.save_goal("user", goals.GOAL_DAILY_STEPS, 10_000, True)
        goals.record_steps("user", 4_999, date(2026, 11, 4))

        result = goals.complete_day("user", date(2026, 11, 4))

        self.assertEqual(result["status"], "incomplete")
        self.assertTrue(result["prompt"])
