import reflex as rx
from ..state.telemetry import TelemetryState
from backend.telemetry_emulator import DATA_TYPES


def _telemetry_chart(title: str, points) -> rx.Component:
    return rx.vstack(
        rx.text(title, weight="bold", size="2"),
        rx.recharts.line_chart(
            rx.recharts.line(
                data_key="value",
                type_="monotone",
                stroke="#38a169",
                is_animation_active=False,
            ),
            rx.recharts.x_axis(
                data_key="time",
                type_="number",
                domain=[1, 10],
                ticks=list(range(1, 11)),
            ),
            rx.recharts.y_axis(),
            data=points,
            width="100%",
            height=120,
        ),
        width="100%",
        min_width="100%",
        max_width="100%",
        align="stretch",
        align_self="stretch",
        spacing="1",
    )


def device_card() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading("Device Telemetry", size="6"),
            rx.cond(
                TelemetryState.enabled,
                rx.vstack(
                    rx.text("Device: ", TelemetryState.device_name, weight="bold"),
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
                    rx.box(
                        _telemetry_chart("Steps", TelemetryState.steps_points),
                        _telemetry_chart("Heart rate", TelemetryState.heart_rate_points),
                        _telemetry_chart(
                            "Resting heart rate",
                            TelemetryState.resting_heart_rate_points,
                        ),
                        _telemetry_chart("Heart-rate variability", TelemetryState.hrv_points),
                        _telemetry_chart(
                            "Daily heart-rate variability",
                            TelemetryState.daily_hrv_points,
                        ),
                        _telemetry_chart(
                            "Active-zone minutes",
                            TelemetryState.zone_minutes_points,
                        ),
                        _telemetry_chart("Total calories", TelemetryState.calories_points),
                        _telemetry_chart("Distance", TelemetryState.distance_points),
                        _telemetry_chart(
                            "Oxygen saturation",
                            TelemetryState.oxygen_points,
                        ),
                        width="100%",
                        min_width="100%",
                        align="stretch",
                        align_self="stretch",
                        box_sizing="border-box",
                        max_height="390px",
                        overflow_y="auto",
                        overflow_x="hidden",
                        padding="0.5em",
                        border_radius="8px",
                        background_color=rx.color_mode_cond("#ffffff", "#1a202c"),
                    ),
                    width="100%",
                    align="stretch",
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