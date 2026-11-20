from healthify.state.session import SessionState
import reflex as rx
from ..state.alerts import AlertState
from ..state.auth import AuthState
from .brand import brand_mark


def page_header() -> rx.Component:
    return rx.hstack(
        rx.button(
            rx.hstack(
                brand_mark(),
                rx.heading("Healthify", size="7"),
                align="center",
                spacing="2",
            ),
            on_click=AuthState.navigate_dashboard,
            variant="ghost",
            color="white",
            padding="0",
            background_color="transparent",
            cursor="pointer",
            _hover={"background_color": "transparent"},
            aria_label="Return to dashboard and save changes",
            title="Return to Dashboard",
        ),
        rx.text("Welcome, ", SessionState.username, "!", size="4",
                font_family='"Comic Sans MS", cursive',
                margin_left=rx.breakpoints(initial="0.25rem", md="1rem")),
        rx.button("Check meal alerts", id="meal-alert-check", display="none",
                  on_click=AlertState.check_meal_alerts),
        rx.spacer(),
        rx.hstack(
            rx.color_mode.button(),
            rx.link(
                rx.hstack(
                    rx.icon("bell", color="white"),
                    rx.cond(
                        AlertState.unread > 0,
                        rx.badge(
                            AlertState.unread,
                            color_scheme="red",
                            variant="solid",
                        ),
                    ),
                    align="center",
                    spacing="1",
                ),
                href="/alerts",
                aria_label="Alerts",
            ),
            rx.button(
                rx.cond(
                    AuthState.profile_picture != "",
                    rx.avatar(src=AuthState.profile_picture, size="3"),
                    rx.avatar(fallback="?", size="3"),
                ),
                on_click=rx.redirect("/account"),
                variant="ghost",
                aria_label="Account",
                title="Account: view and edit your profile",
                padding="0",
                margin_left="0.5em",
                margin_right="0.5em",
            ),
            rx.button(
                "Sign out",
                on_click=AuthState.logout,
                variant="solid",
                color="white",
                background_color=rx.color_mode_cond("#276749", "#22543d"),
                _hover={
                    "background_color": rx.color_mode_cond("#2f855a", "#276749")
                },
                border="1px solid rgba(255, 255, 255, 0.35)",
                border_radius="8px",
                font_weight="500",
            ),
            align="center",
            spacing="2",
        ),
        width="100%",
        padding="1em 2em",
        background_color=rx.color_mode_cond("#2f855a", "#22543d"),
        color="white",
        on_unmount=rx.call_script("clearInterval(window.healthifyMealAlerts)"),
        on_mount=rx.call_script("clearInterval(window.healthifyMealAlerts);"
                                "window.healthifyMealAlerts=setInterval(()=>document.getElementById('meal-alert-check')?.click(),60000);"
                                "Intl.DateTimeFormat().resolvedOptions().timeZone",
                                callback=SessionState.set_meal_timezone),
        border_bottom=rx.color_mode_cond(
            "4px solid #276749", "4px solid #1c4532"
        ),
        align="center",
    )