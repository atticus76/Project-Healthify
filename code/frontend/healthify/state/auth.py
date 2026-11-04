import reflex as rx

from backend import auth_controller
from backend.profile_controller import calculate_baseline_metrics, validate_profile


class AuthState(rx.State):
    identifier: str = ""
    username: str = ""
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

    def set_username(self, value: str):
        self.username = value
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
        if self.mode == "signup":
            success, message, username = auth_controller.register(
                self.username, self.email, self.password, selected_theme
            )
        else:
            success, message, username = auth_controller.authenticate(
                self.identifier, self.password
            )
        if not success:
            self.error = message
            return
        user = auth_controller.get_user(username)
        self.username = username
        auth_controller.set_active_user(username)
        self.email = user.get("email", "") if user else ""
        self.theme = selected_theme
        auth_controller.set_theme(username, selected_theme)
        self.password = ""
        self.error = ""
        self.message = message
        profile_complete = bool(user and user.get("profile", {}).get("complete"))
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
        user = auth_controller.get_user(self.username)
        profile = user.get("profile", {}) if user else {}
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
        auth_controller.save_profile(
            self.username, self.gender, int(self.age), float(self.weight_lb)
        )
        metrics = calculate_baseline_metrics(
            self.gender, int(self.age), float(self.weight_lb)
        )
        self.baseline_weight_lb = f"{metrics['baseline_weight_lb']:.1f} lb"
        self.estimated_daily_calories = (
            f"{int(metrics['estimated_daily_calories'])} kcal/day"
        )
        self.profile_error = ""
        self.profile_saved = "Profile saved."
        return rx.redirect("/")

    def logout(self):
        auth_controller.clear_active_user()
        self.username = ""
        self.email = ""
        self.identifier = ""
        self.password = ""
        self.theme = "light"
        return rx.redirect("/login")

    def require_login(self):
        if not self.username:
            return rx.redirect("/login")
