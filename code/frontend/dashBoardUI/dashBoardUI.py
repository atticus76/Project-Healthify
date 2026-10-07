import reflex as rx

from backend.profile_controller import save_profile, validate_profile


FEATURES = [
    ("Alerts & Notifications", "/alerts"),
    ("Health Profile", "/profile"),
    ("Account", "/account"),
    ("Cloud Data", "/cloud-data"),
    ("Reports & Analytics", "/reports"),
    ("Telemetry Emulator", "/emulator"),
    ("Health Goals", "/goals"),
    ("Legal Disclaimer", "/disclaimer"),
]
SORTED_FEATURES = sorted(FEATURES, key=lambda feature: feature[0].lower())


class DashboardState(rx.State):
    sort_a_to_z: bool = False

    def toggle_sort(self):
        self.sort_a_to_z = not self.sort_a_to_z


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


def page_header() -> rx.Component:
    return rx.hstack(
        rx.heading("Healthify", size="7"),
        rx.text("Welcome USER", size="4"),
        rx.spacer(),
        rx.color_mode.button(),
        width="100%",
        padding="1em 2em",
        background_color=rx.color_mode_cond("#2f855a", "#22543d"),
        color="white",
        border_bottom=rx.color_mode_cond(
            "4px solid #276749", "4px solid #1c4532"
        ),
        align="center",
    )


def feature_button(label: str, route: str) -> rx.Component:
    return rx.button(
        label,
        on_click=rx.redirect(route),
        width="100%",
        height="4em",
        background_color=rx.color_mode_cond("#2f855a", "#276749"),
        color="white",
        _hover={
            "background_color": rx.color_mode_cond("#276749", "#1c4532"),
        },
    )


def feature_grid(features: list[tuple[str, str]]) -> rx.Component:
    return rx.grid(
        *[feature_button(label, route) for label, route in features],
        columns="repeat(3, 1fr)",
        gap="1em",
        width="100%",
    )


def device_card() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading("Device Telemetry", size="6"),
            rx.text("Connect a device to display telemetry here."),
            rx.button(
                "Connect a Device",
                on_click=rx.redirect("/device"),
                size="4",
                width="240px",
                background_color=rx.color_mode_cond("#2f855a", "#276749"),
                color="white",
                _hover={
                    "background_color": rx.color_mode_cond(
                        "#276749", "#1c4532"
                    ),
                },
            ),
            align="center",
            justify="center",
            spacing="3",
            width="100%",
            min_height="300px",
        ),
        width="100%",
        min_height="360px",
        padding="2em",
        border_radius="12px",
        background_color=rx.color_mode_cond("#f7fafc", "#2d3748"),
        border=rx.color_mode_cond("1px solid #e2e8f0", "1px solid #4a5568"),
        box_shadow=rx.color_mode_cond(
            "0 8px 24px rgba(0, 0, 0, 0.15)",
            "0 8px 24px rgba(0, 0, 0, 0.45)",
        ),
    )


@rx.page(route="/")
def dashboard() -> rx.Component:
    return rx.vstack(
        page_header(),
        rx.vstack(
            rx.heading("Dashboard", size="8"),
            rx.text("Choose a feature to get started."),
            device_card(),
            rx.hstack(
                rx.text("Feature buttons:"),
                rx.button(
                    rx.cond(
                        DashboardState.sort_a_to_z,
                        "A-Z Order: On",
                        "A-Z Order: Off",
                    ),
                    on_click=DashboardState.toggle_sort,
                ),
                align="center",
                spacing="3",
            ),
            rx.cond(
                DashboardState.sort_a_to_z,
                feature_grid(SORTED_FEATURES),
                feature_grid(FEATURES),
            ),
            width="100%",
            max_width="900px",
            padding="1.5em 2em 3em",
            align="stretch",
        ),
        width="100%",
        min_height="100vh",
        align="center",
        background_color=rx.color_mode_cond("white", "#1a202c"),
        color=rx.color_mode_cond("#1a202c", "white"),
    )


def empty_feature_page(title: str) -> rx.Component:
    return rx.vstack(
        page_header(),
        rx.center(
            rx.vstack(
                rx.heading(title, size="7"),
                rx.button(
                    "Back to Dashboard",
                    on_click=rx.redirect("/"),
                    background_color=rx.color_mode_cond("#2f855a", "#276749"),
                    color="white",
                    _hover={
                        "background_color": rx.color_mode_cond(
                            "#276749", "#1c4532"
                        ),
                    },
                ),
                align="center",
                spacing="4",
            ),
            flex="1",
            width="100%",
        ),
        min_height="100vh",
        width="100%",
        background_color=rx.color_mode_cond("white", "#1a202c"),
        color=rx.color_mode_cond("#1a202c", "white"),
    )


@rx.page(route="/device")
def device_page() -> rx.Component:
    return empty_feature_page("Connect a Device")


@rx.page(route="/alerts")
def alerts_page() -> rx.Component:
    return empty_feature_page("Alerts & Notifications")


@rx.page(route="/profile")
def profile_page() -> rx.Component:
    return rx.vstack(
        page_header(),
        rx.vstack(
            rx.heading("Profile Setup", size="8"),
            rx.text(
                "Enter your personal details so Healthify can calculate your initial baseline."
            ),
            rx.form(
                rx.vstack(
                    rx.text("Gender", weight="bold"),
                    rx.select(
                        [
                            "Male",
                            "Female",
                            "Non-binary",
                            "Prefer not to say",
                        ],
                        placeholder="Select gender",
                        value=ProfileState.gender,
                        on_change=ProfileState.set_gender,
                        width="100%",
                    ),
                    rx.text(ProfileState.gender_error, color="red"),
                    rx.text("Age", weight="bold"),
                    rx.input(
                        name="age",
                        type="number",
                        placeholder="e.g. 29",
                        value=ProfileState.age,
                        on_change=ProfileState.set_age,
                        min="13",
                        width="100%",
                    ),
                    rx.text(ProfileState.age_error, color="red"),
                    rx.text("Weight (lb)", weight="bold"),
                    rx.input(
                        name="weight_lb",
                        type="text",
                        placeholder="e.g. 175",
                        value=ProfileState.weight_lb,
                        on_change=ProfileState.set_weight_lb,
                        width="100%",
                    ),
                    rx.text(ProfileState.weight_error, color="red"),
                    rx.text(ProfileState.form_error, color="red"),
                    rx.button("Save Profile", type="submit", width="100%"),
                    rx.text(ProfileState.save_message, color="green"),
                ),
                on_submit=ProfileState.save_profile,
                reset_on_submit=False,
                width="100%",
            ),
            rx.cond(
                ProfileState.save_message != "",
                rx.box(
                    rx.heading("Your baseline", size="5"),
                    rx.text(
                        "Baseline weight: ",
                        ProfileState.baseline_weight_lb,
                    ),
                    rx.text(
                        "Estimated daily calories: ",
                        ProfileState.estimated_daily_calories,
                    ),
                    padding="1em",
                    width="100%",
                    border_radius="8px",
                    background_color=rx.color_mode_cond("#f0fff4", "#22543d"),
                ),
            ),
            rx.button(
                "Back to Dashboard",
                on_click=rx.redirect("/"),
                variant="outline",
            ),
            width="100%",
            max_width="600px",
            padding="2em",
            align="stretch",
            spacing="4",
        ),
        width="100%",
        min_height="100vh",
        align="center",
        background_color=rx.color_mode_cond("white", "#1a202c"),
        color=rx.color_mode_cond("#1a202c", "white"),
    )


@rx.page(route="/account")
def account_page() -> rx.Component:
    return empty_feature_page("Account")


@rx.page(route="/cloud-data")
def cloud_data_page() -> rx.Component:
    return empty_feature_page("Cloud Data")


@rx.page(route="/reports")
def reports_page() -> rx.Component:
    return empty_feature_page("Reports & Analytics")


@rx.page(route="/emulator")
def emulator_page() -> rx.Component:
    return empty_feature_page("Telemetry Emulator")


@rx.page(route="/goals")
def goals_page() -> rx.Component:
    return empty_feature_page("Health Goals")


@rx.page(route="/disclaimer")
def disclaimer_page() -> rx.Component:
    return empty_feature_page("Legal Disclaimer")


app = rx.App()
