import reflex as rx

from backend import auth_controller, profile_controller

from .session import SessionState
from backend.db import DatabaseError
from backend.profile_controller import validate_profile


class AuthState(SessionState):
    identifier: str = ""
    # The sign-up form's username box. Signing in sets SessionState.username.
    signup_username: str = ""
    email: str = ""
    password: str = ""
    mode: str = "login"
    error: str = ""
    message: str = ""
    gender: str = ""
    age: str = ""
    weight_lb: str = ""
    profile_error: str = ""
    profile_saved: str = ""
    baseline_weight_lb: str = ""
    estimated_daily_calories: str = ""
    theme: str = "light"

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

    def set_theme(self, value: str):
        if value in {"light", "dark"}:
            self.theme = value

    def toggle_theme(self):
        self.theme = "dark" if self.theme == "light" else "light"
        return rx.call_script(
            "localStorage.setItem('color-mode', '"
            + self.theme
            + "'); document.cookie = 'color-mode="
            + self.theme
            + "; path=/';"
        )

    def load_login(self):
        self.theme = "light"
        return rx.call_script(
            "localStorage.setItem('color-mode', 'light');"
            "document.cookie = 'color-mode=light; path=/';"
        )

    def toggle_mode(self):
        self.mode = "signup" if self.mode == "login" else "login"
        self.error = ""
        self.message = ""

    def submit(self):
        selected_theme = self.theme
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
        self.signup_username = ""
        self.email = account["email"]
        self.theme = selected_theme
        self.password = ""
        self.error = ""
        self.message = message
        theme_script = (
            "localStorage.setItem('color-mode', '"
            + self.theme
            + "'); document.cookie = 'color-mode="
            + self.theme
            + "; path=/';"
        )
        return [
            rx.call_script(theme_script),
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
        self.gender = profile.get("gender", "Prefer not to say")
        self.age = str(profile.get("age", 30))
        self.weight_lb = str(profile.get("weight_lb", 170.0))

    def set_gender(self, value: str):
        self.gender = value

    def set_age(self, value: str):
        self.age = value

    def set_weight_lb(self, value: str):
        self.weight_lb = value

    def save_profile(self):
        errors = validate_profile(self.gender, self.age, self.weight_lb)
        if errors:
            self.profile_error = " ".join(errors.values())
            self.profile_saved = ""
            return
        try:
            saved = profile_controller.save_profile(
                self.username, self.gender, int(self.age), float(self.weight_lb)
            )
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
        return rx.redirect("/")

    def logout(self):
        self.username = ""
        self.signup_username = ""
        self.email = ""
        self.identifier = ""
        self.password = ""
        self.theme = "light"
        return rx.redirect("/login")
