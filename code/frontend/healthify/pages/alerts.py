"""Alerts & Notifications page (US-04 / FR-02, FR-03)."""

import reflex as rx

from backend.alerts import DISCLAIMER
from ..components import page_header
from ..state.alerts import AlertState


def _alert_row(alert) -> rx.Component:
    urgent = alert["severity"] == "urgent"
    return rx.box(
        rx.hstack(
            rx.cond(urgent, rx.icon("heart_pulse", size=22), rx.icon("wifi_off", size=22)),
            rx.vstack(
                rx.hstack(
                    rx.text(alert["title"], weight="bold"),
                    rx.badge(
                        rx.cond(urgent, "Urgent", "Check device"),
                        color_scheme=rx.cond(urgent, "red", "orange"),
                    ),
                    align="center",
                ),
                rx.text(alert["message"]),
                rx.text(alert["when"], size="2", color_scheme="gray"),
                spacing="1",
                align="start",
                flex="1",
            ),
            rx.cond(
                alert["acknowledged"] == "",
                rx.button(
                    "Mark as seen",
                    on_click=AlertState.acknowledge(alert["id"]),
                    variant="outline",
                    size="2",
                ),
                rx.badge("Seen", color_scheme="gray"),
            ),
            align="start",
            spacing="3",
            width="100%",
        ),
        width="100%",
        padding="1em",
        border_radius="12px",
        background_color=rx.color_mode_cond("#f7fafc", "#2d3748"),
        border=rx.cond(
            (alert["acknowledged"] == "") & urgent,
            "2px solid #e53e3e",
            rx.color_mode_cond("1px solid #e2e8f0", "1px solid #4a5568"),
        ),
    )


def _notification_settings() -> rx.Component:
    return rx.match(
        AlertState.permission,
        ("granted", rx.callout("Browser notifications are on.", icon="bell", color_scheme="green")),
        ("denied", rx.callout(
            "Browser notifications are blocked. Allow them in your browser's site settings "
            "to get urgent alerts while Healthify is in the background.",
            icon="bell_off",
            color_scheme="orange",
        )),
        ("unsupported", rx.callout(
            "This browser doesn't support notifications. Alerts will only show inside Healthify.",
            icon="bell_off",
            color_scheme="gray",
        )),
        rx.hstack(
            rx.text("Get urgent alerts even when this tab is in the background."),
            rx.button("Enable browser notifications", on_click=AlertState.request_permission),
            align="center",
            spacing="3",
            wrap="wrap",
        ),
    )


@rx.page(route="/alerts", title="Alerts | Healthify", on_load=AlertState.load_page)
def alerts_page() -> rx.Component:
    return rx.vstack(
        page_header(),
        rx.vstack(
            rx.heading("Alerts & Notifications", size="8"),
            rx.callout(DISCLAIMER, icon="info", color_scheme="blue"),
            _notification_settings(),
            rx.hstack(
                rx.heading("Alert history", size="5"),
                rx.spacer(),
                rx.cond(
                    AlertState.unread > 0,
                    rx.button("Mark all as seen", on_click=AlertState.acknowledge_all, variant="outline"),
                ),
                align="center",
                width="100%",
            ),
            rx.cond(
                AlertState.items.length() > 0,
                rx.foreach(AlertState.items, _alert_row),
                rx.text(
                    "No alerts yet. To try one, open the ",
                    rx.link("Telemetry Emulator", href="/emulator"),
                    " and pick the \"Heart-rate spike\" or \"Connection drop\" scenario.",
                    color_scheme="gray",
                ),
            ),
            rx.button("Back to Dashboard", on_click=rx.redirect("/"), variant="outline", width="fit-content"),
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
