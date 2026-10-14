import reflex as rx
from ..state.telemetry import TelemetryState
from backend.telemetry_emulator import DATA_TYPES

def device_card() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading("Device Telemetry", size="6"),
            rx.cond(
                TelemetryState.enabled,
                rx.vstack(
                    rx.badge("SIMULATED FITBIT DATA", color_scheme="green"),
                    rx.text(
                        "Profile: ",
                        TelemetryState.level,
                        " | ",
                        str(len(DATA_TYPES)),
                        " data types active",
                    ),
                    rx.button(
                        "View Telemetry",
                        on_click=rx.redirect("/emulator"),
                        size="4",
                        width="240px",
                        background_color=rx.color_mode_cond(
                            "#2f855a", "#276749"
                        ),
                        color="white",
                    ),
                    align="center",
                    spacing="3",
                ),
                rx.vstack(
                    rx.text("Connect a device or enable simulated Fitbit telemetry."),
                    rx.button(
                        "Connect a Device",
                        on_click=rx.redirect("/devices"),
                        size="4",
                        width="240px",
                        background_color=rx.color_mode_cond(
                            "#2f855a", "#276749"
                        ),
                        color="white",
                        _hover={
                            "background_color": rx.color_mode_cond(
                                "#276749", "#1c4532"
                            ),
                        },
                    ),
                    align="center",
                    spacing="3",
                ),
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