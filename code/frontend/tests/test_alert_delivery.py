"""Tests for how US-04 alerts are delivered (toast + browser notification).

Spec: code/specs/features/S2-03-health-abnormality-alerts.md
"""

import json
import unittest

from backend import alerts
from healthify.state.alerts import _browser_notification, notify


URGENT = {
    "id": 7,
    "title": "Abnormal heart rate spike",
    "message": "Your heart rate stayed above 130 BPM for 6 minutes.",
    "severity": alerts.SEVERITY_URGENT,
}
GAP = {**URGENT, "id": 8, "title": "Wearable data gap", "severity": alerts.SEVERITY_INFO}


class AlertDeliveryTests(unittest.TestCase):
    def test_no_new_alerts_sends_nothing(self):
        self.assertEqual(notify([]), [])

    def test_each_alert_gets_a_toast_and_a_browser_notification(self):
        # two per alert, plus one event that refreshes the unread count
        self.assertEqual(len(notify([URGENT, GAP])), 5)

    def test_browser_notification_only_fires_with_permission(self):
        script = _browser_notification(URGENT)
        self.assertIn("Notification.permission === 'granted'", script)
        self.assertIn('"Abnormal heart rate spike"', script)

    def test_urgent_notifications_stay_until_dismissed(self):
        self.assertIn('"requireInteraction": true', _browser_notification(URGENT))
        self.assertIn('"requireInteraction": false', _browser_notification(GAP))

    def test_notification_carries_the_disclaimer(self):
        self.assertIn("not a medical device", _browser_notification(URGENT))

    def test_notification_text_is_escaped(self):
        tricky = {**URGENT, "title": '"); alert("x'}
        self.assertIn(json.dumps(tricky["title"]), _browser_notification(tricky))


if __name__ == "__main__":
    unittest.main()
