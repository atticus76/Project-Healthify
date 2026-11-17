import reflex as rx

#states
from ..state.alerts import AlertState
from ..state.telemetry import TelemetryState
from ..state.auth import AuthState

#components
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

@rx.page(route="/", on_load=[AuthState.require_login, AlertState.load, TelemetryState.load_page])
def dashboard() -> rx.Component:
    return rx.vstack(
        page_header(),
        rx.grid(
            rx.vstack(
                rx.heading("Track", size="5"),
                feature_grid(LEFT_FEATURES),
                spacing="3",
                width="100%",
                padding="1.25em",
                border_radius="12px",
                border=rx.color_mode_cond(
                    "1px solid #e2e8f0", "1px solid #4a5568"
                ),
            ),
            rx.vstack(
                rx.heading("Dashboard", size="8"),
                rx.text("Choose a feature to get started."),
                rx.button(
                    "Automatic refresh",
                    id="telemetry-auto-refresh",
                    on_click=TelemetryState.auto_refresh,
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
                rx.heading("Review", size="5"),
                feature_grid(RIGHT_FEATURES),
                spacing="3",
                width="100%",
                padding="1.25em",
                border_radius="12px",
                border=rx.color_mode_cond(
                    "1px solid #e2e8f0", "1px solid #4a5568"
                ),
            ),
            columns=rx.breakpoints(initial="1", md="1fr 2.5fr 1fr"),
            gap="1.5em",
            width="100%",
            padding="1.5em 2em 3em",
            align="start",
        ),
        width="100%",
        min_height="100vh",
        align="center",
        background_color=rx.color_mode_cond("white", "#1a202c"),
        color=rx.color_mode_cond("#1a202c", "white"),
    )