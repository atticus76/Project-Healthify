import reflex as rx
from ..state.telemetry import TelemetryState

def feature_button(label: str, route: str) -> rx.Component:
    is_emulator = route == "/emulator"
    return rx.button(
        label,
        on_click=rx.redirect(route),
        width="100%",
        height="4em",
        background_color=rx.cond(
            is_emulator,
            rx.cond(TelemetryState.enabled, "#48bb78", "#c53030"),
            rx.color_mode_cond("#2f855a", "#276749"),
        ),
        color="white",
        _hover={
            "background_color": rx.cond(
                is_emulator,
                rx.cond(TelemetryState.enabled, "#38a169", "#9b2c2c"),
                rx.color_mode_cond("#276749", "#1c4532"),
            ),
        },
    )