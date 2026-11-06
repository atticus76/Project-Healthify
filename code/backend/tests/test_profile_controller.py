"""Health profiles in the cloud health_profiles table (S2-04, cleanup C4).

health_profiles is the only copy of gender, age and weight. Runs against
healthify-test and is skipped if TEST_DATABASE_URL isn't set.
"""

import pytest

from backend import auth_controller, db, profile_controller

pytestmark = pytest.mark.usefixtures("test_db")


@pytest.fixture
def alice():
    auth_controller.register("alice", "", "Testpass1!")
    return "alice"


def test_saved_profile_comes_back_with_baseline_metrics(alice):
    saved = profile_controller.save_profile(alice, "Female", 28, 140.5)
    loaded = profile_controller.get_profile(alice)
    for profile in (saved, loaded):
        assert profile["user_id"] == alice
        assert (profile["gender"], profile["age"], profile["weight_lb"]) == ("Female", 28, 140.5)
        assert profile["baseline_weight_lb"] == 140.5
        assert profile["estimated_daily_calories"] > 0


def test_saving_again_updates_the_same_row(alice):
    profile_controller.save_profile(alice, "Female", 28, 140.5)
    profile_controller.save_profile(alice, "Female", 29, 138.0)
    assert profile_controller.get_profile(alice)["age"] == 29
    with db.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM health_profiles").fetchone()["n"] == 1
