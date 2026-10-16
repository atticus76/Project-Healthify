import reflex as rx
from ..components import page_header
from ..state.telemetry import TelemetryState

@rx.page(route="/emulator")
def emulator_page() -> rx.Component:
    return rx.vstack(
        page_header(),
        rx.vstack(
            rx.heading("Fitbit Telemetry Emulator", size="8"),
            rx.text(
                "Generate synthetic Fitbit-style records for all supported data types. "
                "This data is simulated and is not a health measurement."
            ),
            rx.text("Simulation activity level", weight="bold"),
            rx.select(
                ["Low", "Medium", "High"],
                value=TelemetryState.level,
                on_change=TelemetryState.set_level,
                width="100%",
            ),
            rx.cond(
                TelemetryState.enabled,
                rx.hstack(
                    rx.button(
                        "Refresh Data",
                        on_click=TelemetryState.refresh,
                        background_color=rx.color_mode_cond("#2f855a", "#276749"),
                        color="white",
                    ),
                    rx.button(
                        "Disable Emulator",
                        on_click=TelemetryState.disable,
                        variant="outline",
                    ),
                    align="center",
                    spacing="3",
                ),
                rx.button(
                    "Enable Emulator",
                    on_click=TelemetryState.enable,
                    background_color=rx.color_mode_cond("#2f855a", "#276749"),
                    color="white",
                ),
            ),
            rx.cond(
                TelemetryState.enabled,
                rx.vstack(
                    rx.heading("Generated data points", size="5"),
                    rx.foreach(
                        TelemetryState.summaries,
                        lambda summary: rx.text(summary),
                    ),
                    rx.button(
                        rx.cond(
                            TelemetryState.show_payload,
                            "Hide Fitbit payload",
                            "View Fitbit payload",
                        ),
                        on_click=TelemetryState.toggle_payload,
                        variant="outline",
                    ),
                    rx.cond(
                        TelemetryState.show_payload,
                        rx.box(
                            rx.text(
                                TelemetryState.payload_json,
                                white_space="pre-wrap",
                                font_family="monospace",
                                font_size="0.8em",
                            ),
                            width="100%",
                            max_height="500px",
                            overflow_y="auto",
                            padding="1em",
                            border_radius="8px",
                            background_color=rx.color_mode_cond(
                                "#f7fafc", "#2d3748"
                            ),
                        ),
                    ),
                    align="stretch",
                    spacing="3",
                    width="100%",
                ),
            ),
            rx.button(
                "Back to Dashboard",
                on_click=rx.redirect("/"),
                variant="outline",
            ),
            width="100%",
            max_width="800px",
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