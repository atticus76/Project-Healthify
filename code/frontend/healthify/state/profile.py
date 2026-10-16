import reflex as rx
from backend.profile_controller import save_profile, validate_profile

class ProfileState(rx.State):
    gender: str = ""
    age: str = ""
    weight_lb: str = ""
    gender_error: str = ""
    age_error: str = ""
    weight_error: str = ""
    form_error: str = ""
    save_message: str = ""
    baseline_weight_lb: str = ""
    estimated_daily_calories: str = ""

    def set_gender(self, value: str):
        self.gender = value

    def set_age(self, value: str):
        self.age = value

    def set_weight_lb(self, value: str):
        self.weight_lb = value

    def save_profile(self):
        errors = validate_profile(self.gender, self.age, self.weight_lb)
        self.gender_error = errors.get("gender", "")
        self.age_error = errors.get("age", "")
        self.weight_error = errors.get("weight", "")
        self.form_error = "Please correct the errors below." if errors else ""
        self.save_message = ""

        if errors:
            return

        saved_profile = save_profile(
            "new-user",
            self.gender,
            int(self.age),
            float(self.weight_lb),
        )
        self.baseline_weight_lb = f"{saved_profile['baseline_weight_lb']:.1f} lb"
        self.estimated_daily_calories = (
            f"{int(saved_profile['estimated_daily_calories'])} kcal/day"
        )
        self.save_message = "Profile saved and baseline metrics updated."