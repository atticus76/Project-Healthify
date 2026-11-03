"""Generate local Fitbit-shaped telemetry for the dashboard emulator."""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta, timezone
from typing import Any


DATA_TYPES = {
    "steps": 50,
    "heart-rate": 50,
    "daily-resting-heart-rate": 14,
    "heart-rate-variability": 50,
    "daily-heart-rate-variability": 14,
    "sleep": 5,
    "exercise": 10,
    "active-zone-minutes": 50,
    "total-calories": 50,
    "distance": 50,
    "daily-oxygen-saturation": 14,
}

DEVICE_NAME = "HealthTrack Simulator"
UTC = timezone.utc
LOCAL = timezone(timedelta(hours=-7))
PROFILES = {
    "Low": {
        "steps": (2_500, 5_000),
        "heart_rate": (75, 90),
        "resting_heart_rate": (72, 82),
        "hrv": (18.0, 35.0),
        "sleep_hours": (5.2, 6.5),
        "exercise_sessions": (0, 1),
        "active_zone_minutes": (5, 18),
        "calories": (1_600, 2_100),
        "oxygen": (93.0, 96.0),
    },
    "Medium": {
        "steps": (6_000, 9_500),
        "heart_rate": (65, 80),
        "resting_heart_rate": (60, 72),
        "hrv": (30.0, 55.0),
        "sleep_hours": (6.8, 8.0),
        "exercise_sessions": (1, 2),
        "active_zone_minutes": (25, 55),
        "calories": (1_900, 2_600),
        "oxygen": (94.5, 98.0),
    },
    "High": {
        "steps": (10_000, 16_000),
        "heart_rate": (58, 75),
        "resting_heart_rate": (52, 66),
        "hrv": (45.0, 80.0),
        "sleep_hours": (7.5, 9.0),
        "exercise_sessions": (2, 3),
        "active_zone_minutes": (50, 90),
        "calories": (2_300, 3_400),
        "oxygen": (95.0, 99.5),
    },
}

# Emulated events for demoing alerts (US-04). "normal" is the default.
SCENARIOS = ("normal", "heart-rate-spike", "connection-drop")
SPIKE_SAMPLES = 14  # 30 s apart, so the spike lasts 6.5 minutes
DROP_SAMPLES = (6, 22)  # newest-first indexes missing while "disconnected" (8 min)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _date_fields(value: date) -> dict[str, int]:
    return {"year": value.year, "month": value.month, "day": value.day}


def _civil_time(value: datetime, include_seconds: bool = False) -> dict[str, Any]:
    local_value = value.astimezone(LOCAL)
    fields = {
        "hours": local_value.hour,
        "minutes": local_value.minute,
    }
    if include_seconds:
        fields["seconds"] = local_value.second
    return {"date": _date_fields(local_value.date()), "time": fields}


def _interval(start: datetime, end: datetime) -> dict[str, Any]:
    return {
        "startTime": _iso_utc(start),
        "startUtcOffset": "-25200s",
        "endTime": _iso_utc(end),
        "endUtcOffset": "-25200s",
        "civilStartTime": _civil_time(start),
        "civilEndTime": _civil_time(end),
    }


def _data_source(recording_method: str = "PASSIVELY_MEASURED") -> dict[str, Any]:
    return {
        "recordingMethod": recording_method,
        "device": {"displayName": DEVICE_NAME},
        "platform": "FITBIT",
    }


def _sample_time(value: datetime) -> dict[str, Any]:
    return {
        "physicalTime": _iso_utc(value),
        "utcOffset": "-25200s",
        "civilTime": _civil_time(value, include_seconds=True),
    }


def _date_record(value: date) -> dict[str, int]:
    return _date_fields(value)


def generate_fitbit_data(
    level: str, now: datetime | None = None, scenario: str = "normal"
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Return profile-scaled data points grouped by Fitbit data type.

    scenario="heart-rate-spike" makes the latest heart-rate samples read above
    130 BPM at rest. scenario="connection-drop" removes heart-rate samples as if
    the wearable disconnected, with the readings just before the drop elevated.
    """
    if level not in PROFILES:
        raise ValueError(f"Unknown simulation level: {level}")
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown simulation scenario: {scenario}")

    profile = PROFILES[level]
    rng = random.Random()
    current = (now or datetime.now(UTC)).astimezone(UTC).replace(second=0, microsecond=0)
    today = current.astimezone(LOCAL).date()
    daily_steps = rng.randint(*profile["steps"])
    daily_calories = rng.randint(*profile["calories"])
    daily_distance_m = round(daily_steps * 0.76, 1)

    def build_records() -> dict[str, dict[str, list[dict[str, Any]]]]:
        return {data_type: {"dataPoints": []} for data_type in DATA_TYPES}

    result = build_records()

    def append(data_type: str, record: dict[str, Any]) -> None:
        result[data_type]["dataPoints"].append(record)

    for index in range(DATA_TYPES["steps"]):
        end = current - timedelta(minutes=index)
        start = end - timedelta(minutes=1)
        append(
            "steps",
            {
                "dataSource": _data_source(),
                "steps": {
                    "interval": _interval(start, end),
                    "count": str(rng.randint(0, max(1, daily_steps // 720))),
                },
            },
        )

    for index in range(DATA_TYPES["heart-rate"]):
        if scenario == "connection-drop" and DROP_SAMPLES[0] <= index < DROP_SAMPLES[1]:
            continue
        sample = current - timedelta(seconds=index * 30)
        bpm = rng.randint(*profile["heart_rate"])
        if scenario == "heart-rate-spike" and index < SPIKE_SAMPLES:
            bpm = rng.randint(135, 155)
        elif scenario == "connection-drop" and DROP_SAMPLES[1] <= index < DROP_SAMPLES[1] + 4:
            bpm = rng.randint(135, 155)
        append(
            "heart-rate",
            {
                "dataSource": _data_source(),
                "heartRate": {
                    "sampleTime": _sample_time(sample),
                    "beatsPerMinute": str(bpm),
                },
            },
        )

    for index in range(DATA_TYPES["daily-resting-heart-rate"]):
        day = today - timedelta(days=index)
        append(
            "daily-resting-heart-rate",
            {
                "dataSource": _data_source("DERIVED"),
                "dailyRestingHeartRate": {
                    "date": _date_record(day),
                    "beatsPerMinute": str(
                        rng.randint(*profile["resting_heart_rate"])
                    ),
                    "dailyRestingHeartRateMetadata": {
                        "calculationMethod": "WITH_SLEEP"
                    },
                },
            },
        )

    for index in range(DATA_TYPES["heart-rate-variability"]):
        sample = current - timedelta(minutes=index * 15)
        hrv_value = round(rng.uniform(*profile["hrv"]), 1)
        append(
            "heart-rate-variability",
            {
                "dataSource": _data_source("DERIVED"),
                "heartRateVariability": {
                    "sampleTime": _sample_time(sample),
                    "rootMeanSquareOfSuccessiveDifferencesMilliseconds": hrv_value,
                    "metadata": {
                        "highFrequencyPower": round(hrv_value * 4.1, 1),
                        "lowFrequencyPower": round(hrv_value * 18.5, 1),
                    },
                },
            },
        )

    for index in range(DATA_TYPES["daily-heart-rate-variability"]):
        day = today - timedelta(days=index)
        average_hrv = round(rng.uniform(*profile["hrv"]), 1)
        append(
            "daily-heart-rate-variability",
            {
                "dataSource": _data_source("DERIVED"),
                "dailyHeartRateVariability": {
                    "date": _date_record(day),
                    "averageHeartRateVariabilityMilliseconds": average_hrv,
                    "nonRemHeartRateBeatsPerMinute": str(
                        rng.randint(*profile["resting_heart_rate"])
                    ),
                    "entropy": round(rng.uniform(2.5, 3.4), 3),
                    "deepSleepRootMeanSquareOfSuccessiveDifferencesMilliseconds": round(
                        average_hrv * rng.uniform(0.8, 1.0), 2
                    ),
                },
            },
        )

    for index in range(DATA_TYPES["sleep"]):
        day = today - timedelta(days=index)
        sleep_hours = rng.uniform(*profile["sleep_hours"])
        local_start = datetime.combine(
            day - timedelta(days=1), time(22, 30), tzinfo=LOCAL
        )
        start = local_start.astimezone(UTC)
        duration_minutes = int(sleep_hours * 60)
        stage_lengths = [
            max(5, int(duration_minutes * fraction))
            for fraction in (0.05, 0.48, 0.18, 0.19)
        ]
        stage_lengths.append(max(5, duration_minutes - sum(stage_lengths)))
        stages = []
        stage_start = start
        for stage_type, stage_length in zip(
            ("AWAKE", "LIGHT", "DEEP", "LIGHT", "REM"), stage_lengths
        ):
            stage_end = stage_start + timedelta(minutes=stage_length)
            stages.append(
                {
                    "startTime": _iso_utc(stage_start),
                    "startUtcOffset": "-25200s",
                    "endTime": _iso_utc(stage_end),
                    "endUtcOffset": "-25200s",
                    "type": stage_type,
                }
            )
            stage_start = stage_end
        append(
            "sleep",
            {
                "name": f"users/simulator/dataTypes/sleep/dataPoints/{index}",
                "dataSource": _data_source("DERIVED"),
                "sleep": {
                    "interval": {
                        "startTime": _iso_utc(start),
                        "startUtcOffset": "-25200s",
                        "endTime": _iso_utc(stage_start),
                        "endUtcOffset": "-25200s",
                    },
                    "type": "STAGES",
                    "stages": stages,
                },
            },
        )

    sessions_per_day = rng.randint(*profile["exercise_sessions"])
    # In alert scenarios, start sessions yesterday so the spike reads as at rest.
    first_exercise_day = 0 if scenario == "normal" else 1
    for index in range(DATA_TYPES["exercise"]):
        duration_seconds = rng.randint(20, 60) * 60
        end = current - timedelta(
            days=first_exercise_day + index // max(sessions_per_day, 1)
        )
        start = end - timedelta(seconds=duration_seconds)
        steps = rng.randint(1_000, 5_000)
        distance_m = round(steps * 0.76, 2)
        calories = rng.randint(90, 450)
        exercise_type = rng.choice(("WALKING", "RUNNING", "CYCLING"))
        append(
            "exercise",
            {
                "name": f"users/simulator/dataTypes/exercise/dataPoints/{index}",
                "dataSource": _data_source("ACTIVELY_MEASURED"),
                "exercise": {
                    "interval": {
                        "startTime": _iso_utc(start),
                        "startUtcOffset": "-25200s",
                        "endTime": _iso_utc(end),
                        "endUtcOffset": "-25200s",
                    },
                    "exerciseType": exercise_type,
                    "metricsSummary": {
                        "caloriesKcal": calories,
                        "distanceMillimeters": int(distance_m * 1_000),
                        "steps": str(steps),
                        "averagePaceSecondsPerMeter": round(
                            duration_seconds / max(distance_m, 1), 3
                        ),
                        "averageHeartRateBeatsPerMinute": str(
                            rng.randint(*profile["heart_rate"])
                        ),
                        "heartRateZoneDurations": {
                            "lightTime": f"{duration_seconds}s",
                            "moderateTime": "0s",
                            "vigorousTime": "0s",
                            "peakTime": "0s",
                        },
                    },
                    "exerciseMetadata": {},
                    "displayName": exercise_type.title(),
                    "activeDuration": f"{duration_seconds}s",
                    "exerciseEvents": [
                        {
                            "eventTime": _iso_utc(start),
                            "eventUtcOffset": "-25200s",
                            "exerciseEventType": "START",
                        },
                        {
                            "eventTime": _iso_utc(end),
                            "eventUtcOffset": "-25200s",
                            "exerciseEventType": "STOP",
                        },
                    ],
                    "updateTime": _iso_utc(end),
                    "createTime": _iso_utc(end),
                },
            },
        )

    for index in range(DATA_TYPES["active-zone-minutes"]):
        end = current - timedelta(minutes=index)
        start = end - timedelta(minutes=1)
        append(
            "active-zone-minutes",
            {
                "dataSource": _data_source(),
                "activeZoneMinutes": {
                    "interval": _interval(start, end),
                    "heartRateZone": rng.choice(
                        ("FAT_BURN", "CARDIO", "PEAK")
                    ),
                    "activeZoneMinutes": str(
                        rng.randint(0, max(1, profile["active_zone_minutes"][1] // 50))
                    ),
                },
            },
        )

    for index in range(DATA_TYPES["total-calories"]):
        end = current - timedelta(minutes=index)
        start = end - timedelta(minutes=1)
        calorie_slice = daily_calories / (24 * 60)
        append(
            "total-calories",
            {
                "dataSource": _data_source("DERIVED"),
                "totalCalories": {
                    "interval": _interval(start, end),
                    "caloriesKcal": round(calorie_slice, 2),
                },
            },
        )

    for index in range(DATA_TYPES["distance"]):
        end = current - timedelta(minutes=index)
        start = end - timedelta(minutes=1)
        distance_slice = daily_distance_m / (24 * 60)
        append(
            "distance",
            {
                "dataSource": _data_source(),
                "distance": {
                    "interval": _interval(start, end),
                    "distanceMillimeters": round(distance_slice * 1_000, 1),
                },
            },
        )

    for index in range(DATA_TYPES["daily-oxygen-saturation"]):
        day = today - timedelta(days=index)
        average = round(rng.uniform(*profile["oxygen"]), 1)
        append(
            "daily-oxygen-saturation",
            {
                "dataSource": _data_source(),
                "dailyOxygenSaturation": {
                    "date": _date_record(day),
                    "averagePercentage": average,
                    "lowerBoundPercentage": round(
                        max(85.0, average - rng.uniform(1.0, 3.0)), 1
                    ),
                    "upperBoundPercentage": round(
                        min(100.0, average + rng.uniform(1.0, 2.0)), 1
                    ),
                },
            },
        )

    return result


def summarize_fitbit_data(
    data: dict[str, dict[str, list[dict[str, Any]]]],
) -> list[str]:
    """Create short dashboard labels for each generated data type."""
    paths = {
        "steps": ("steps", "count", " steps"),
        "heart-rate": ("heartRate", "beatsPerMinute", " bpm"),
        "daily-resting-heart-rate": (
            "dailyRestingHeartRate",
            "beatsPerMinute",
            " bpm resting",
        ),
        "heart-rate-variability": (
            "heartRateVariability",
            "rootMeanSquareOfSuccessiveDifferencesMilliseconds",
            " ms HRV",
        ),
        "daily-heart-rate-variability": (
            "dailyHeartRateVariability",
            "averageHeartRateVariabilityMilliseconds",
            " ms avg HRV",
        ),
        "sleep": ("sleep", None, ""),
        "exercise": ("exercise", "displayName", ""),
        "active-zone-minutes": (
            "activeZoneMinutes",
            "activeZoneMinutes",
            " zone min",
        ),
        "total-calories": ("totalCalories", "caloriesKcal", " kcal"),
        "distance": ("distance", "distanceMillimeters", " mm"),
        "daily-oxygen-saturation": (
            "dailyOxygenSaturation",
            "averagePercentage",
            "% SpO2",
        ),
    }
    summaries = []
    for data_type, limit in DATA_TYPES.items():
        points = data[data_type]["dataPoints"]
        value_key, field_key, unit = paths[data_type]
        value = "Sleep stages" if field_key is None else points[0][value_key][field_key]
        summaries.append(
            f"{data_type}: {len(points)}/{limit} points | latest {value}{unit}"
        )
    return summaries
