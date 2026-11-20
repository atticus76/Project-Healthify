import base64
import reflex as rx

from backend import auth_controller, profile_controller

from .session import SessionState
from backend.db import DatabaseError
from backend.profile_controller import validate_profile


HEIGHT_UNITS = {"cm": 1.0, "meters": 100.0, "inches": 2.54, "feet": 30.48}
WEIGHT_UNITS = {"lb": 1.0, "kg": 1 / 0.45359237}


def _convert(value, factor):
    try:
        return format(float(value) * factor, ".12g")
    except ValueError:
        return value


class AuthState(SessionState):
    identifier: str = ""
    # The sign-up form's username box. Signing in sets SessionState.username.
    signup_username: str = ""
    email: str = ""
    password: str = ""
    password_visible: bool = False
    signup_password_visible: bool = False
    mode: str = "login"
    error: str = ""
    message: str = ""
    gender: str = ""
    age: str = ""
    height_unit: str = "cm"
    weight_unit: str = "lb"
    height_input: str = ""
    activity_level: str = ""
    weight_input: str = ""
    profile_error: str = ""
    profile_saved: str = ""
    baseline_weight_lb: str = ""
    estimated_daily_calories: str = ""
    profile_picture: str = ""
    profile_picture_error: str = ""
    changing_password: bool = False
    current_password: str = ""
    new_password: str = ""
    repeated_password: str = ""
    password_change_error: str = ""
    password_change_message: str = ""

    def set_identifier(self, value: str):
        self.identifier = value
        self.error = ""

    def set_signup_username(self, value: str):
        self.signup_username = value
        self.error = ""

    def set_email(self, value: str):
        self.email = value
        self.error = ""

    def set_password(self, value: str):
        self.password = value
        self.error = ""

    def toggle_password_visibility(self):
        self.password_visible = not self.password_visible

    def toggle_signup_password_visibility(self):
        self.signup_password_visible = not self.signup_password_visible

    def toggle_mode(self):
        self.mode = "signup" if self.mode == "login" else "login"
        self.error = ""
        self.message = ""
        self.password_visible = False
        self.signup_password_visible = False

    async def handle_profile_picture(self, files: list[rx.UploadFile]):
        if not files:
            return
        picture = files[0]
        if not picture.content_type or not picture.content_type.startswith("image/"):
            self.profile_picture_error = "Please choose an image file."
            return
        if picture.size > 2 * 1024 * 1024:
            self.profile_picture_error = "Profile pictures must be 2 MB or smaller."
            return
        content = await picture.read()
        self.profile_picture = (
            f"data:{picture.content_type};base64,"
            f"{base64.b64encode(content).decode('ascii')}"
        )
        self.profile_picture_error = ""
        if self.username:
            try:
                auth_controller.set_app_preference(self.username, "profile_picture", self.profile_picture)
            except DatabaseError as error:
                self.profile_picture_error = str(error)

    def remove_profile_picture(self):
        if not self.username:
            self.profile_picture_error = "You must be signed in to remove a profile picture."
            return
        try:
            auth_controller.set_app_preference(self.username, "profile_picture", None)
        except DatabaseError as error:
            self.profile_picture_error = str(error)
            return
        self.profile_picture = ""
        self.profile_picture_error = ""

    def toggle_password_change(self):
        self.changing_password = not self.changing_password
        self.password_change_error = ""
        self.password_change_message = ""

    def set_current_password(self, value: str):
        self.current_password = value
        self.password_change_error = ""

    def set_new_password(self, value: str):
        self.new_password = value
        self.password_change_error = ""

    def set_repeated_password(self, value: str):
        self.repeated_password = value
        self.password_change_error = ""

    def change_password(self):
        if self.new_password != self.repeated_password:
            self.password_change_error = "The new passwords do not match."
            self.password_change_message = ""
            return
        try:
            success, message = auth_controller.change_password(
                self.username, self.current_password, self.new_password
            )
        except DatabaseError as error:
            self.password_change_error = str(error)
            self.password_change_message = ""
            return
        if not success:
            self.password_change_error = message
            self.password_change_message = ""
            return
        self.current_password = ""
        self.new_password = ""
        self.repeated_password = ""
        self.password_change_error = ""
        self.password_change_message = message
        self.changing_password = False

    def _load_profile_values(self, profile: dict):
        self.gender = profile.get("gender", "Prefer not to say")
        self.age = str(profile.get("age", 30))
        self.height_unit, self.weight_unit = "cm", "lb"
        self.height_input = str(profile.get("height_cm") or "")
        self.activity_level = profile.get("activity_level") or ""
        self.weight_input = str(profile.get("weight_lb", 170.0))
        self.baseline_weight_lb = f"{profile['baseline_weight_lb']:.1f} lb"
        self.estimated_daily_calories = (
            f"{int(profile['estimated_daily_calories'])} kcal/day"
        )

    def load_account(self):
        if not self.username:
            return rx.redirect("/login")
        try:
            account = auth_controller.get_user(self.username) or {}
            self.email = account.get("email", "")
            self.profile_picture = (account.get("app_state") or {}).get(
                "profile_picture", ""
            )
            profile = profile_controller.get_profile(self.username)
            if profile:
                self._load_profile_values(profile)
        except DatabaseError as error:
            self.profile_error = str(error)


    def submit(self, selected_theme: str = "light"):
        # sign_up / sign_in each use one database connection (~200 ms each).
        try:
            if self.mode == "signup":
                success, message, account = auth_controller.sign_up(
                    self.signup_username, self.email, self.password, selected_theme
                )
            else:
                success, message, account = auth_controller.sign_in(
                    self.identifier, self.password, selected_theme
                )
        except DatabaseError as error:
            self.error = str(error)
            return
        if not success:
            self.error = message
            return
        username = account["username"]
        profile_complete = account["has_profile"]
        self.username = username  # this browser is now signed in
        uploaded_picture = self.profile_picture
        if uploaded_picture:
            try:
                auth_controller.set_app_preference(username, "profile_picture", uploaded_picture)
            except DatabaseError as error:
                self.error = str(error)
                return
        self.signup_username = ""
        self.email = account["email"]
        self.profile_picture = uploaded_picture or (account.get("app_state") or {}).get(
            "profile_picture", ""
        )
        self.password = ""
        self.password_visible = False
        self.signup_password_visible = False
        self.error = ""
        self.message = message
        return [
            rx.redirect("/" if profile_complete else "/profile"),
        ]

    def load_profile(self):
        if not self.username:
            return rx.redirect("/login")
        try:
            profile = profile_controller.get_profile(self.username) or {}
        except DatabaseError as error:
            self.profile_error = str(error)
            return
        self.profile_error = ""
        if profile:
            self._load_profile_values(profile)
        else:
            self.gender = "Prefer not to say"
            self.age = "30"
            self.height_unit, self.weight_unit = "cm", "lb"
            self.weight_input = "170.0"
            self.height_input = ""
            self.activity_level = ""

    def set_gender(self, value: str):
        self.gender = value

    def set_age(self, value: str):
        self.age = value

    def set_height_unit(self, unit: str):
        if unit in HEIGHT_UNITS:
            self.height_input = _convert(self.height_input, HEIGHT_UNITS[self.height_unit] / HEIGHT_UNITS[unit])
            self.height_unit = unit

    def set_weight_unit(self, unit: str):
        if unit in WEIGHT_UNITS:
            self.weight_input = _convert(self.weight_input, WEIGHT_UNITS[self.weight_unit] / WEIGHT_UNITS[unit])
            self.weight_unit = unit

    def set_height_input(self, value: str):
        self.height_input = value

    def set_activity_level(self, value: str):
        self.activity_level = value

    def set_weight_input(self, value: str):
        self.weight_input = value

    def save_profile(self):
        return self._save_profile(redirect_to_dashboard=True)

    def save_profile_on_account(self):
        return self._save_profile(redirect_to_dashboard=False)

    def navigate_dashboard(self):
        if not self.username:
            return rx.redirect("/login")
        return rx.redirect("/")

    def _save_profile(self, redirect_to_dashboard: bool):
        weight_lb = _convert(self.weight_input, WEIGHT_UNITS[self.weight_unit])
        height_cm = _convert(self.height_input, HEIGHT_UNITS[self.height_unit])
        errors = validate_profile(self.gender, self.age, weight_lb, height_cm, self.activity_level)
        if errors:
            self.profile_error = " ".join(errors.values())
            self.profile_saved = ""
            return
        try:
            saved = profile_controller.save_profile(
                self.username, self.gender, int(self.age), float(weight_lb),
                float(height_cm), self.activity_level
            )
            auth_controller.update_user(self.username, email=self.email)
        except DatabaseError as error:
            self.profile_error = str(error)
            self.profile_saved = ""
            return
        self.baseline_weight_lb = f"{saved['baseline_weight_lb']:.1f} lb"
        self.estimated_daily_calories = (
            f"{int(saved['estimated_daily_calories'])} kcal/day"
        )
        self.profile_error = ""
        self.profile_saved = "Profile saved."
        if saved.get("calorie_target") is None:
            self.profile_saved = "Profile saved."
            if self.gender in {"Male", "Female"}:
                self.profile_error = "MyPlate could not provide a target. Save again to retry."
            else:
                self.profile_saved += " MyPlate only provides targets for male or female calculator inputs."
            return
        if redirect_to_dashboard:
            return rx.redirect("/")

    def logout(self):
        self.gender = self.age = self.weight_input = self.height_input = self.activity_level = ""
        self.profile_error = self.profile_saved = ""
        self.username = ""
        self.signup_username = ""
        self.email = ""
        self.identifier = ""
        self.password = ""
        self.profile_picture = ""
        self.changing_password = False
        self.current_password = ""
        self.new_password = ""
        self.repeated_password = ""
        self.password_visible = False
        self.signup_password_visible = False
        return rx.redirect("/login")
