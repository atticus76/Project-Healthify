from datetime import datetime, timezone
import unittest

from backend.telemetry_emulator import (
    DATA_TYPES,
    generate_fitbit_data,
    summarize_fitbit_data,
)


class TelemetryEmulatorTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 12, 23, 5, tzinfo=timezone.utc)
        self.payload_names = {
            "steps": "steps",
            "heart-rate": "heartRate",
            "daily-resting-heart-rate": "dailyRestingHeartRate",
            "heart-rate-variability": "heartRateVariability",
            "daily-heart-rate-variability": "dailyHeartRateVariability",
            "sleep": "sleep",
            "exercise": "exercise",
            "active-zone-minutes": "activeZoneMinutes",
            "total-calories": "totalCalories",
            "distance": "distance",
            "daily-oxygen-saturation": "dailyOxygenSaturation",
        }

    def test_generates_requested_number_of_points_for_every_data_type(self):
        data = generate_fitbit_data("Medium", self.now)

        self.assertEqual(set(data), set(DATA_TYPES))
        for data_type, limit in DATA_TYPES.items():
            with self.subTest(data_type=data_type):
                self.assertEqual(len(data[data_type]["dataPoints"]), limit)

    def test_records_include_fitbit_source_and_type_payload(self):
        data = generate_fitbit_data("Medium", self.now)

        for data_type, wrapped in data.items():
            with self.subTest(data_type=data_type):
                for point in wrapped["dataPoints"]:
                    self.assertEqual(point["dataSource"]["platform"], "FITBIT")
                    self.assertIn(self.payload_names[data_type], point)

    def test_daily_oxygen_is_within_selected_profile_range(self):
        data = generate_fitbit_data("Low", self.now)
        oxygen_points = data["daily-oxygen-saturation"]["dataPoints"]

        for point in oxygen_points:
            oxygen = point["dailyOxygenSaturation"]
            self.assertGreaterEqual(oxygen["averagePercentage"], 93.0)
            self.assertLessEqual(oxygen["averagePercentage"], 96.0)
            self.assertLessEqual(
                oxygen["lowerBoundPercentage"], oxygen["averagePercentage"]
            )
            self.assertGreaterEqual(
                oxygen["upperBoundPercentage"], oxygen["averagePercentage"]
            )

    def test_summaries_cover_every_data_type(self):
        data = generate_fitbit_data("High", self.now)

        summaries = summarize_fitbit_data(data)

        self.assertEqual(len(summaries), len(DATA_TYPES))
        for data_type, limit in DATA_TYPES.items():
            self.assertTrue(
                any(
                    summary.startswith(f"{data_type}: {limit}/{limit} points")
                    for summary in summaries
                )
            )

    def test_unknown_level_is_rejected(self):
        with self.assertRaises(ValueError):
            generate_fitbit_data("Extreme", self.now)


if __name__ == "__main__":
    unittest.main()
