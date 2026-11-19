"""Health profiles (cloud `health_profiles` table) and baseline metric calculations.

health_profiles is the only copy of a user's gender, age and weight (S2-04,
cleanup C4). A user with no row hasn't completed their profile yet.
"""

from __future__ import annotations

from typing import Any

import requests

from backend.db import connect

MIN_AGE = 13
MAX_AGE = 120
MIN_WEIGHT_LB = 1.0
MAX_WEIGHT_LB = 1_000.0
VALID_GENDERS = {"Male", "Female", "Non-binary", "Prefer not to say"}


ACTIVITY_LEVELS = {"Sedentary": "sedentary", "Moderately active": "moderately-active", "Active": "active"}


def myplate_target(gender, age, height_cm, weight_lb, activity_level):
    if gender not in {"Male", "Female"} or activity_level not in ACTIVITY_LEVELS:
        return None
    try:
        response = requests.get(
            "https://myplate.food/api/v1/calculate/myplate-plan",
            params={"sex": gender.lower(), "age": age, "height_cm": height_cm,
                    "weight_kg": round(weight_lb * 0.45359237, 3),
                    "activity": ACTIVITY_LEVELS[activity_level]},
            timeout=5,
        )
        response.raise_for_status()
        target = response.json()["calorie_level"]
        return target if type(target) is int and target > 0 else None
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None


def validate_profile(gender: str, age: str, weight_lb: str, height_cm=None, activity_level=None) -> dict[str, str]:
    """Return field-level validation messages without writing anything."""
    errors: dict[str, str] = {}

    if gender not in VALID_GENDERS:
        errors["gender"] = "Please select a gender."

    try:
        age_value = int(age)
        if not MIN_AGE <= age_value <= MAX_AGE:
            errors["age"] = f"Age must be between {MIN_AGE} and {MAX_AGE}."
    except (TypeError, ValueError):
        errors["age"] = "Please enter a valid age."

    try:
        weight_value = float(weight_lb)
        if not MIN_WEIGHT_LB <= weight_value <= MAX_WEIGHT_LB:
            errors["weight"] = "Weight must be a valid number greater than zero."
    except (TypeError, ValueError):
        errors["weight"] = "Weight must be a valid number greater than zero."

    if height_cm is not None:
        try:
            if not 0 < float(height_cm) <= 300:
                raise ValueError
        except (TypeError, ValueError):
            errors["height"] = "Enter a height in centimeters between 0 and 300."
    if activity_level is not None and activity_level not in ACTIVITY_LEVELS:
        errors["activity"] = "Select an activity level."
    return errors


def calculate_baseline_metrics(
    gender: str, age: int, weight_lb: float
) -> dict[str, float | str]:
    """Calculate an initial weight-based estimate for the profile.

    Height and activity level are intentionally not assumed. The estimate is
    labeled as preliminary and can be refined when those profile fields exist.
    """
    weight_kg = weight_lb * 0.45359237
    gender_factor = {"Male": 1.05, "Female": 0.95}.get(gender, 1.0)
    age_factor = max(0.80, 1.0 - max(age - 30, 0) * 0.002)
    estimated_calories = round(weight_kg * 24 * gender_factor * age_factor)

    return {
        "baseline_weight_lb": round(weight_lb, 1),
        "estimated_daily_calories": float(estimated_calories),
    }


def save_profile(user_id: str, gender: str, age: int, weight_lb: float, height_cm=None, activity_level=None) -> dict[str, Any]:
    """Save (or replace) the user's profile and return it with baseline metrics."""
    metrics = calculate_baseline_metrics(gender, age, weight_lb)
    target = myplate_target(gender, age, height_cm, weight_lb, activity_level)
    with connect("save profile") as conn:
        row = conn.execute(
            """
            INSERT INTO health_profiles (
                user_id, gender, age, weight_lb,
                baseline_weight_lb, estimated_daily_calories, height_cm, activity_level, calorie_target
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                calorie_target = CASE WHEN (health_profiles.gender, health_profiles.age,
                    health_profiles.weight_lb, health_profiles.height_cm, health_profiles.activity_level)
                    IS NOT DISTINCT FROM (excluded.gender, excluded.age, excluded.weight_lb,
                    excluded.height_cm, excluded.activity_level)
                    THEN coalesce(excluded.calorie_target, health_profiles.calorie_target)
                    ELSE excluded.calorie_target END,
                height_cm = excluded.height_cm,
                activity_level = excluded.activity_level,
                gender = excluded.gender,
                age = excluded.age,
                weight_lb = excluded.weight_lb,
                baseline_weight_lb = excluded.baseline_weight_lb,
                estimated_daily_calories = excluded.estimated_daily_calories,
                updated_at = to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')
            RETURNING *
            """,
            (
                user_id,
                gender,
                age,
                weight_lb,
                metrics["baseline_weight_lb"],
                metrics["estimated_daily_calories"], height_cm, activity_level, target,
            ),
        ).fetchone()
    return row


def get_profile(user_id: str) -> dict[str, Any] | None:
    """Return the user's profile, or None if they haven't completed one."""
    with connect("load profile") as conn:
        return conn.execute(
            "SELECT * FROM health_profiles WHERE user_id = %s", (user_id,)
        ).fetchone()
