"""US-02 Account Registration Page."""

from __future__ import annotations

import reflex as rx
from healthify.components.header import header
from healthify.state.account import AccountState


@rx.page(route="/account")
def account_page() -> rx.Component:
    return rx.box(
        header(),
        rx.center(
            rx.card(
                rx.vstack(
                    rx.heading("Create Account", size="6"),
                    rx.text(
                        "Create a secure account using your email and password "
                        "(min 8 characters, 1 capital letter, 1 number, 1 special character).",
                        size="2",
                        color="gray",
                    ),
                    # Scenario 2: Error popup if email already exists or password fails validation
                    rx.cond(
                        AccountState.error_message != "",
                        rx.callout(
                            AccountState.error_message,
                            icon="triangle_alert",
                            color_scheme="red",
                            role="alert",
                            width="100%",
                        ),
                    ),
                    rx.vstack(
                        rx.text("Email", size="2", weight="bold"),
                        rx.input(
                            placeholder="you@wsu.edu",
                            type="email",
                            value=AccountState.email,
                            on_change=AccountState.set_email,
                            width="100%",
                        ),
                        rx.text("Password", size="2", weight="bold"),
                        rx.input(
                            placeholder="1 Capital, 1 Number, 1 Special Character",
                            type="password",
                            value=AccountState.password,
                            on_change=AccountState.set_password,
                            width="100%",
                        ),
                        rx.button(
                            "Create Account",
                            on_click=AccountState.handle_registration,
                            width="100%",
                            margin_top="0.5rem",
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    spacing="4",
                    width="100%",
                    align="start",
                ),
                size="4",
                width="100%",
                max_width="440px",
            ),
            padding_y="4rem",
            padding_x="1rem",
            width="100%",
        ),
        min_height="100vh",
        width="100%",
    )