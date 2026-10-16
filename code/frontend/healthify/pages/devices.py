"""Connect Device page (US-01 / FR-01) and the OAuth redirect target.

AI-GENERATED (Claude) for the device-connection demo.
"""

import reflex as rx

from ..components import page_header
from ..state.devices import DeviceState

GREEN = rx.color_mode_cond("#2f855a", "#276749")
GREEN_HOVER = rx.color_mode_cond("#276749", "#1c4532")


def _primary_button(label, on_click, **props) -> rx.Component:
    return rx.button(
        label,
        on_click=on_click,
        size="3",
        background_color=GREEN,
        color="white",
        _hover={"background_color": GREEN_HOVER},
        **props,
    )


def _panel(*children) -> rx.Component:
    return rx.box(
        rx.vstack(*children, spacing="3", align="stretch"),
        width="100%",
        padding="1.5em",
        border_radius="12px",
        background_color=rx.color_mode_cond("#f7fafc", "#2d3748"),
        border=rx.color_mode_cond("1px solid #e2e8f0", "1px solid #4a5568"),
    )


def _not_connected() -> rx.Component:
    return _panel(
        rx.hstack(rx.heading("Google Health", size="5"), rx.badge("Not connected", color_scheme="gray"), align="center"),
        rx.text(
            "Connect the Google account your Fitbit syncs to. You'll be sent to Google to approve "
            "read-only access to activity, heart, and sleep data, then brought back here."
        ),
        rx.hstack(_primary_button("Connect Google Health", DeviceState.start_connect)),
    )


def _reconnect() -> rx.Component:
    return _panel(
        rx.hstack(rx.heading("Google Health", size="5"), rx.badge("Reconnect required", color_scheme="orange"), align="center"),
        rx.text("Healthify's access to ", rx.text.strong(DeviceState.email), " expired or was revoked."),
        rx.text(
            "While our Google app is in Testing mode, access expires every 7 days.",
            size="2",
            color_scheme="gray",
        ),
        rx.hstack(
            _primary_button("Reconnect", DeviceState.start_connect),
            rx.button("Remove", on_click=DeviceState.disconnect_account, variant="outline", size="3"),
        ),
    )


def _connected() -> rx.Component:
    return _panel(
        rx.hstack(rx.heading("Google Health", size="5"), rx.badge("Device Connected", color_scheme="green"), align="center"),
        rx.text("Account: ", rx.text.strong(DeviceState.email)),
        rx.cond(DeviceState.device_name != "", rx.text("Device: ", rx.text.strong(DeviceState.device_name))),
        rx.text("Last sync: ", DeviceState.last_sync, size="2", color_scheme="gray"),
        rx.hstack(
            _primary_button("Sync Now", DeviceState.sync_now, loading=DeviceState.busy),
            rx.button("Disconnect", on_click=DeviceState.disconnect_account, variant="outline", size="3"),
        ),
        rx.cond(
            DeviceState.summaries.length() > 0,
            rx.vstack(
                rx.divider(),
                rx.heading("Latest from your wearable", size="4"),
                rx.foreach(DeviceState.summaries, lambda line: rx.text(line)),
                spacing="2",
                align="stretch",
            ),
        ),
    )


@rx.page(route="/devices", title="Connect Device | Healthify", on_load=DeviceState.load)
def device_page() -> rx.Component:
    return rx.vstack(
        page_header(),
        rx.vstack(
            rx.heading("Connect a Device", size="8"),
            rx.cond(
                DeviceState.error != "",
                rx.callout(DeviceState.error, icon="triangle_alert", color_scheme="red"),
            ),
            rx.cond(
                DeviceState.message != "",
                rx.callout(DeviceState.message, icon="check", color_scheme="green"),
            ),
            rx.match(
                DeviceState.status,
                ("connected", _connected()),
                ("reconnect_required", _reconnect()),
                _not_connected(),
            ),
            rx.text(
                "No wearable? Use the ",
                rx.link("Telemetry Emulator", href="/emulator"),
                " for simulated data.",
                size="2",
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


@rx.page(route="/devices/callback", title="Connecting... | Healthify", on_load=DeviceState.handle_callback)
def device_callback_page() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.spinner(size="3"),
            rx.text("Finishing your Google connection..."),
            align="center",
            spacing="3",
        ),
        min_height="100vh",
        width="100%",
        background_color=rx.color_mode_cond("white", "#1a202c"),
        color=rx.color_mode_cond("#1a202c", "white"),
    )
