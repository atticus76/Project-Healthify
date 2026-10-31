"""Tests for US-04 Health Abnormality Alerts.

Spec: code/specs/features/S2-03-health-abnormality-alerts.md
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from backend import alerts
from backend.telemetry_emulator import generate_fitbit_data


NOW = datetime(2026, 10, 12, 23, 5, tzinfo=timezone.utc)


def samples(*bpms, start=NOW, every=timedelta(seconds=30)):
    return [alerts.HeartRateSample(start + every * i, bpm) for i, bpm in enumerate(bpms)]


class EvaluateHeartRateTests(unittest.TestCase):
    def test_sustained_high_heart_rate_raises_urgent_alert(self):
        # Scenario 1: above 130 BPM for over 5 minutes (11 samples = 5 min).
        findings = alerts.evaluate_heart_rate(samples(*[140] * 11))

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].kind, alerts.KIND_HIGH_HEART_RATE)
        self.assertEqual(findings[0].severity, alerts.SEVERITY_URGENT)
        self.assertEqual(findings[0].peak_bpm, 140)

    def test_short_spike_does_not_alert(self):
        self.assertEqual(alerts.evaluate_heart_rate(samples(*[140] * 10)), [])

    def test_exactly_threshold_does_not_alert(self):
        self.assertEqual(alerts.evaluate_heart_rate(samples(*[130] * 20)), [])

    def test_dip_below_threshold_resets_the_window(self):
        bpms = [140] * 6 + [100] + [140] * 6
        self.assertEqual(alerts.evaluate_heart_rate(samples(*bpms)), [])

    def test_high_heart_rate_during_exercise_does_not_alert(self):
        exercise = [(NOW - timedelta(minutes=1), NOW + timedelta(minutes=30))]
        self.assertEqual(alerts.evaluate_heart_rate(samples(*[150] * 20), exercise), [])

    def test_spike_across_a_disconnection_logs_gap_without_alarm(self):
        # Scenario 2: 3 min high, 8 min with no data, 3 min high.
        before = samples(*[150] * 7)
        after = samples(*[150] * 7, start=NOW + timedelta(minutes=11))

        findings = alerts.evaluate_heart_rate(before + after)

        self.assertEqual([f.kind for f in findings], [alerts.KIND_DATA_GAP])
        self.assertEqual(findings[0].severity, alerts.SEVERITY_INFO)
        self.assertIn("worn", findings[0].message)

    def test_small_gaps_are_not_data_gaps(self):
        readings = samples(*[70] * 5, every=alerts.MAX_SAMPLE_GAP)
        self.assertEqual(alerts.evaluate_heart_rate(readings), [])


class EmulatorScenarioTests(unittest.TestCase):
    def evaluate(self, scenario):
        data = generate_fitbit_data("Medium", NOW, scenario=scenario)
        return alerts.evaluate_heart_rate(
            alerts.extract_heart_rate(data), alerts.extract_exercise_intervals(data)
        )

    def test_normal_data_has_no_alerts(self):
        self.assertEqual(self.evaluate("normal"), [])

    def test_heart_rate_spike_scenario_alerts(self):
        self.assertEqual(
            [f.kind for f in self.evaluate("heart-rate-spike")],
            [alerts.KIND_HIGH_HEART_RATE],
        )

    def test_connection_drop_scenario_only_logs_gap(self):
        self.assertEqual(
            [f.kind for f in self.evaluate("connection-drop")],
            [alerts.KIND_DATA_GAP],
        )

    def test_unknown_scenario_is_rejected(self):
        with self.assertRaises(ValueError):
            generate_fitbit_data("Medium", NOW, scenario="meteor")


class AlertStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patcher = mock.patch.object(alerts, "DATABASE_PATH", Path(self.tmp.name) / "test.db")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)
        self.spike = generate_fitbit_data("Medium", NOW, scenario="heart-rate-spike")

    def test_new_alert_is_stored_and_returned(self):
        new = alerts.check_telemetry(self.spike, "user-1")

        self.assertEqual(len(new), 1)
        self.assertEqual(new[0]["kind"], alerts.KIND_HIGH_HEART_RATE)
        self.assertEqual(alerts.unacknowledged_count("user-1"), 1)

    def test_resyncing_the_same_data_does_not_alert_twice(self):
        alerts.check_telemetry(self.spike, "user-1")

        self.assertEqual(alerts.check_telemetry(self.spike, "user-1"), [])
        self.assertEqual(len(alerts.list_alerts("user-1")), 1)

    def test_alerts_are_scoped_per_user(self):
        alerts.check_telemetry(self.spike, "user-1")
        self.assertEqual(alerts.list_alerts("user-2"), [])

    def test_acknowledge_clears_unread_count(self):
        alerts.check_telemetry(self.spike, "user-1")
        alerts.check_telemetry(
            generate_fitbit_data("Medium", NOW, scenario="connection-drop"), "user-1"
        )
        first = alerts.list_alerts("user-1")[0]

        alerts.acknowledge("user-1", first["id"])
        self.assertEqual(alerts.unacknowledged_count("user-1"), 1)
        alerts.acknowledge("user-1")
        self.assertEqual(alerts.unacknowledged_count("user-1"), 0)


if __name__ == "__main__":
    unittest.main()
