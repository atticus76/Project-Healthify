import reflex as rx

#states
from ..state.dashboard import DashboardState

#components
from ..components import page_header, device_card, feature_grid


FEATURES = [
    ("Alerts & Notifications", "/alerts"),
    ("Health Profile", "/profile"),
    ("Connect Device", "/devices"),
    ("Account", "/account"),
    ("Cloud Data", "/cloud-data"),
    ("Reports & Analytics", "/reports"),
    ("Telemetry Emulator", "/emulator"),
    ("Health Goals", "/goals"),
    ("Legal Disclaimer", "/disclaimer"),
]
SORTED_FEATURES = sorted(FEATURES, key=lambda feature: feature[0].lower())

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