import reflex as rx

#states
from ..state.alerts import AlertState
from ..state.telemetry import TelemetryState
from ..state.auth import AuthState
from ..state.devices import DeviceState

#components
from ..components.food_dialog import food_dialog, suggested_meals
from ..state.nutrition import NutritionState
from ..components import page_header, device_card, feature_grid


LEFT_FEATURES = [
    ("Connect Device", "/devices"),
    ("Telemetry Emulator", "/emulator"),
    ("Health Goals", "/goals"),
]
RIGHT_FEATURES = [
    ("Alerts & Notifications", "/alerts"),
    ("Reports & Analytics", "/reports"),
    ("Legal Disclaimer", "/disclaimer"),
]

def _side_card(title: str | rx.Component, *content: rx.Component, panel=False, grow=False) -> rx.Component:
    return rx.vstack(
        rx.heading(title, size="5") if isinstance(title, str) else title,
        *content,
        spacing="3",
        width="100%",
        flex_grow=1 if grow else 0,
        background_color=rx.color_mode_cond("white", "#2d3748") if panel else "transparent",
        padding="1.25em",
        border_radius="12px",
        border=rx.color_mode_cond("1px solid #e2e8f0", "1px solid #4a5568"),
    )


def _calories_card() -> rx.Component:
    displays = [
        ("Target", TelemetryState.calorie_target),
        ("Burned", TelemetryState.burned_kcal),
        ("Consumed", TelemetryState.consumed_kcal),
    ]
    return _side_card(
        rx.hstack(rx.heading("Calories", size="5"),
                  rx.button("Reset", size="1", variant="ghost", color_scheme="green", on_click=TelemetryState.reset_calories),
                  align="center"),
        rx.cond(TelemetryState.incomplete_profile,
                rx.text("Complete your missing details in Health Profile to get a calorie target.",
                        size="1", color_scheme="red", role="status")),
        rx.grid(
            *[rx.vstack(rx.text(label, size="1"), rx.text(value, weight="bold"),
                        rx.text("kcal", size="1"), spacing="1", align="center")
              for label, value in displays],
            columns="3", gap="2", width="100%", padding="0.55em 0.15em",
            background_color=rx.color_mode_cond("#f0fff4", "#203b32"),
            border=rx.color_mode_cond("1px solid #c6e8ce", "1px solid #38634e"), border_radius="8px",
        ),
        rx.hstack(rx.button("Health Profile", on_click=rx.redirect("/profile"), size="2",
                            color_scheme="green", flex_grow=1),
                  food_dialog(), spacing="2", wrap="wrap", width="100%"),
        rx.form(rx.hstack(rx.input(name="kcal", placeholder="Food kcal", aria_label="Consumed calories",
                                   type="number", min="1", max="10000", required=True, size="1",
                                   flex="1 1 0%", min_width="0"),
                          rx.button("Add Calories", type="submit", size="1", color_scheme="green",
                                    flex_shrink=0), width="100%"),
                on_submit=TelemetryState.log_food, reset_on_submit=True, width="100%"),
        panel=True,
    )


@rx.page(route="/", on_load=[AuthState.require_login, AlertState.load_unread, TelemetryState.load_page, DeviceState.load_dashboard, TelemetryState.load_calories, NutritionState.cycle_suggestions])
def dashboard() -> rx.Component:
    return rx.vstack(
        page_header(),
        rx.grid(
            rx.vstack(
                _side_card("Track", feature_grid(LEFT_FEATURES)),
                _calories_card(),
                gap="1.5em",
                width="100%",
            ),
            rx.vstack(
                rx.heading("Dashboard", size="8"),
                rx.text("Choose a feature to get started."),
                rx.button(
                    "Automatic refresh",
                    id="telemetry-auto-refresh",
                    on_click=[TelemetryState.dashboard_refresh, NutritionState.cycle_suggestions],
                    opacity="0",
                    position="absolute",
                    width="1px",
                    height="1px",
                    pointer_events="none",
                ),
                device_card(),
                width="100%",
                align="stretch",
                spacing="3",
                min_width="0",
                flex="1",
                padding="1.25em",
                border_radius="12px",
                border=rx.color_mode_cond(
                    "1px solid #e2e8f0", "1px solid #4a5568"
                ),
            ),
            rx.vstack(
                _side_card("Review", feature_grid(RIGHT_FEATURES), panel=True),
                _side_card("Recipes", food_dialog(recipes=True), suggested_meals(), grow=True),
                gap="1.5em",
                width="100%",
            ),
            columns=rx.breakpoints(initial="1", md="1fr 2.5fr 1fr"),
            gap="1.5em",
            width="100%",
            padding="1.5em 2em 3em",
            align="stretch",
        ),
        width="100%",
        min_height="100vh",
        align="center",
        background_color=rx.color_mode_cond("white", "#1a202c"),
        color=rx.color_mode_cond("#1a202c", "white"),
    )