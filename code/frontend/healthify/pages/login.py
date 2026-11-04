import reflex as rx

from ..state.auth import AuthState


@rx.page(route="/login", title="Sign in | Healthify", on_load=AuthState.load_login)
def login_page() -> rx.Component:
    return rx.center(
        rx.card(
            rx.vstack(
                rx.hstack(
                    rx.heading("Healthify", size="8", color="#2f855a"),
                    rx.spacer(),
                    rx.button(
                        rx.cond(AuthState.theme == "light", "🌙", "☀️"),
                        on_click=AuthState.toggle_theme,
                        size="2",
                        variant="outline",
                        aria_label="Toggle light and dark mode",
                        background_color=rx.cond(
                            AuthState.theme == "light", "#edf2f7", "#2d3748"
                        ),
                        color=rx.cond(
                            AuthState.theme == "light", "#1a202c", "#f7fafc"
                        ),
                    ),
                    width="100%",
                    align="center",
                ),
                rx.text(
                    rx.cond(
                        AuthState.mode == "login",
                        "Sign in to continue to your health dashboard.",
                        "Create a demo account to get started.",
                    )
                ),
                rx.cond(
                    AuthState.error != "",
                    rx.callout(AuthState.error, icon="triangle_alert", color_scheme="red"),
                ),
                rx.cond(
                    AuthState.mode == "login",
                    rx.vstack(
                        rx.input(
                            placeholder="Username or email",
                            value=AuthState.identifier,
                            on_change=AuthState.set_identifier,
                            width="100%",
                        ),
                        rx.input(
                            placeholder="Password",
                            type="password",
                            value=AuthState.password,
                            on_change=AuthState.set_password,
                            width="100%",
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.input(
                            placeholder="Username",
                            value=AuthState.username,
                            on_change=AuthState.set_username,
                            width="100%",
                        ),
                        rx.input(
                            placeholder="Email (optional)",
                            type="email",
                            value=AuthState.email,
                            on_change=AuthState.set_email,
                            width="100%",
                        ),
                        rx.input(
                            placeholder="Password",
                            type="password",
                            value=AuthState.password,
                            on_change=AuthState.set_password,
                            width="100%",
                        ),
                        spacing="3",
                        width="100%",
                    ),
                ),
                rx.button(
                    rx.cond(AuthState.mode == "login", "Sign in", "Create account"),
                    on_click=AuthState.submit,
                    width="100%",
                    background_color="#2f855a",
                    color="white",
                    _hover={"background_color": "#276749"},
                ),
                rx.button(
                    rx.cond(
                        AuthState.mode == "login",
                        "Need an account? Sign up",
                        "Already have an account? Sign in",
                    ),
                    on_click=AuthState.toggle_mode,
                    variant="ghost",
                ),
                spacing="4",
                width="100%",
            ),
            width="100%",
            max_width="440px",
            border_top="6px solid #2f855a",
            background_color=rx.cond(
                AuthState.theme == "light", "white", "#2d3748"
            ),
            color=rx.cond(
                AuthState.theme == "light", "#1a202c", "#f7fafc"
            ),
        ),
        min_height="100vh",
        width="100%",
        padding="2em",
        background_color=rx.cond(
            AuthState.theme == "light", "#f7fafc", "#1a202c"
        ),
    )
