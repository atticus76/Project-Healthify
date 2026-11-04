import reflex as rx

from ..components import page_header
from ..state.reports import ReportsState
from ..state.auth import AuthState
from ..state.telemetry import TelemetryState


def _report_content() -> rx.Component:
    return rx.vstack(
        rx.heading("Latest report", size="5"),
        rx.cond(
            ReportsState.latest_report.length() > 0,
            rx.vstack(
                rx.text("Period: ", ReportsState.latest_report["period"]),
                rx.text("Last updated: ", ReportsState.latest_report["updated"]),
                rx.text("Delivery: ", ReportsState.latest_report["delivery"]),
                rx.cond(
                    ~ReportsState.metrics_available,
                    rx.callout(ReportsState.metrics_message, icon="triangle_alert", color_scheme="orange"),
                    rx.callout(ReportsState.metrics_message, icon="activity", color_scheme="green"),
                ),
                rx.heading("Live telemetry", size="4"),
                rx.cond(
                    ReportsState.telemetry_summary.length() > 0,
                    rx.foreach(
                        ReportsState.telemetry_summary,
                        lambda summary: rx.text(summary),
                    ),
                    rx.text(
                        "No live telemetry samples are currently available.",
                        color_scheme="gray",
                    ),
                ),
                rx.heading("Fitness goal progress", size="4"),
                rx.cond(
                    ReportsState.goal_summary.length() > 0,
                    rx.foreach(
                        ReportsState.goal_summary,
                        lambda goal: rx.text(
                            goal["steps"], " / ", goal["target"], " steps (",
                            goal["percent"], "%) — ", goal["status"],
                        ),
                    ),
                    rx.text("No goal data was available for this period.", color_scheme="gray"),
                ),
                rx.heading("Telemetry alerts", size="4"),
                rx.cond(
                    ReportsState.alert_summary.length() > 0,
                    rx.foreach(
                        ReportsState.alert_summary,
                        lambda alert: rx.text(alert["title"], ": ", alert["message"]),
                    ),
                    rx.text("No alerts were recorded for this period.", color_scheme="gray"),
                ),
                align="stretch",
                spacing="2",
            ),
            rx.text("No report has been generated yet.", color_scheme="gray"),
        ),
        rx.hstack(
            rx.spacer(),
            rx.button(
                "Print",
                on_click=ReportsState.export_report,
                size="1",
                variant="outline",
            ),
            width="100%",
        ),
        align="stretch",
        spacing="3",
    )


@rx.page(route="/reports", title="Analytics & Reports | Healthify", on_load=[AuthState.require_login, ReportsState.load_page])
def reports_page() -> rx.Component:
    return rx.vstack(
        page_header(),
        rx.vstack(
            rx.heading("Analytics and Reports", size="8"),
            rx.text("Schedule recurring summaries and review your latest health report."),
            rx.button(
                "Refresh report",
                id="report-refresh",
                on_click=[TelemetryState.auto_refresh, ReportsState.refresh_report],
                opacity="0",
                position="absolute",
                width="1px",
                height="1px",
                pointer_events="none",
            ),
            rx.button(
                "Automatic telemetry refresh",
                id="reports-telemetry-refresh",
                on_click=TelemetryState.auto_refresh,
                opacity="0",
                position="absolute",
                width="1px",
                height="1px",
                pointer_events="none",
            ),
            rx.cond(ReportsState.error != "", rx.text(ReportsState.error, color_scheme="red")),
            _report_content(),
            rx.box(
                rx.vstack(
                    rx.heading("Recurring report preferences", size="5"),
                    rx.select.root(
                        rx.select.trigger(width="100%"),
                        rx.select.content(
                            rx.select.item("Daily", value="daily"),
                            rx.select.item("Weekly", value="weekly"),
                        ),
                        value=ReportsState.frequency,
                        on_change=ReportsState.set_frequency,
                    ),
                    rx.input(
                        placeholder="Email address",
                        type="email",
                        value=ReportsState.email,
                        on_change=ReportsState.set_email,
                    ),
                    rx.button("Save preferences", on_click=ReportsState.save_preferences),
                    rx.cond(ReportsState.preferences_saved != "", rx.text(ReportsState.preferences_saved, color_scheme="green")),
                    align="stretch",
                    spacing="3",
                ),
                width="100%",
                padding="1em",
                border=rx.color_mode_cond("1px solid #e2e8f0", "1px solid #4a5568"),
                border_radius="10px",
            ),
            rx.button("Back to Dashboard", on_click=rx.redirect("/"), variant="outline"),
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
