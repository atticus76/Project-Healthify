import reflex as rx

#states
from ..state.dashboard import DashboardState
from ..state.alerts import AlertState
from ..state.telemetry import TelemetryState
from ..state.auth import AuthState

#components
from ..components import page_header, device_card, feature_grid


FEATURES = [
    ("Health Profile", "/profile"),
    ("Connect Device", "/devices"),
    ("Telemetry Emulator", "/emulator"),
    ("Health Goals", "/goals"),
    ("Alerts & Notifications", "/alerts"),
    ("Reports & Analytics", "/reports"),
    ("Account", "/account"),
    ("Cloud Data", "/cloud-data"),
    ("Legal Disclaimer", "/disclaimer"),
]
SORTED_FEATURES = sorted(FEATURES, key=lambda feature: feature[0].lower())

@rx.page(route="/", on_load=[AuthState.require_login, AlertState.load, TelemetryState.load_page])
def dashboard() -> rx.Component:
    return rx.vstack(
        page_header(),
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