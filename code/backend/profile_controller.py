"""Profile persistence and baseline metric calculations."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


DATABASE_PATH = Path(__file__).resolve().parent / "healthtrack.db"
MIN_AGE = 13
MAX_AGE = 120
MIN_WEIGHT_LB = 1.0
MAX_WEIGHT_LB = 1_000.0
VALID_GENDERS = {"Male", "Female", "Non-binary", "Prefer not to say"}


def validate_profile(gender: str, age: str, weight_lb: str) -> dict[str, str]:
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


def save_profile(
    profile_id: str, gender: str, age: int, weight_lb: float
) -> dict[str, Any]:
    """Persist a profile and return the saved profile with baseline metrics."""
    metrics = calculate_baseline_metrics(gender, age, weight_lb)

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS health_profiles (
                profile_id TEXT PRIMARY KEY,
                gender TEXT NOT NULL,
                age INTEGER NOT NULL,
                weight_lb REAL NOT NULL,
                baseline_weight_lb REAL NOT NULL,
                estimated_daily_calories INTEGER NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            INSERT INTO health_profiles (
                profile_id, gender, age, weight_lb,
                baseline_weight_lb, estimated_daily_calories
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(profile_id) DO UPDATE SET
                gender = excluded.gender,
                age = excluded.age,
                weight_lb = excluded.weight_lb,
                baseline_weight_lb = excluded.baseline_weight_lb,
                estimated_daily_calories = excluded.estimated_daily_calories,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                profile_id,
                gender,
                age,
                weight_lb,
                metrics["baseline_weight_lb"],
                metrics["estimated_daily_calories"],
            ),
        )

    return {
        "profile_id": profile_id,
        "gender": gender,
        "age": age,
        "weight_lb": weight_lb,
        **metrics,
    }
