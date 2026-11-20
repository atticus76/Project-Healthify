import reflex as rx

from ..state.auth import AuthState
from ..components.brand import brand_mark


def _password_field(
    value: rx.Var[str],
    on_change,
    visible: rx.Var[bool],
    toggle,
) -> rx.Component:
    return rx.hstack(
        rx.input(
            placeholder="Password",
            type=rx.cond(visible, "text", "password"),
            value=value,
            on_change=on_change,
            width="100%",
            padding_right="3.25em",
        ),
        rx.icon_button(
            rx.icon(rx.cond(visible, "eye_off", "eye")),
            on_click=toggle,
            variant="ghost",
            aria_label=rx.cond(visible, "Hide password", "Show password"),
            position="absolute",
            right="0.35em",
            z_index="1",
        ),
        width="100%",
        align="center",
        position="relative",
    )


def _profile_picture_uploader() -> rx.Component:
    return rx.vstack(
        rx.upload.root(
            rx.cond(
                AuthState.profile_picture != "",
                rx.image(
                    src=AuthState.profile_picture,
                    width="72px",
                    height="72px",
                    border_radius="50%",
                    object_fit="cover",
                ),
                rx.avatar(fallback="?", size="6"),
            ),
            rx.text("Add profile picture (optional)", size="2"),
            id="signup-profile-picture",
            cursor="pointer",
            align="center",
            on_drop=AuthState.handle_profile_picture(
                rx.upload_files(upload_id="signup-profile-picture")
            ),
        ),
        rx.text(AuthState.profile_picture_error, color="red", size="2"),
        align="center",
        width="100%",
    )


@rx.page(route="/login", title="Sign in | Healthify")
def login_page() -> rx.Component:
    return rx.center(
        rx.card(
            rx.vstack(
                rx.hstack(
                    rx.hstack(
                        brand_mark("34px"),
                        rx.heading("Healthify", size="8", color=rx.color_mode_cond("#2f855a", "#68d391")),
                        align="center",
                        spacing="2",
                    ),
                    rx.spacer(),
                    rx.color_mode.button(),
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
                        _password_field(
                            AuthState.password,
                            AuthState.set_password,
                            AuthState.password_visible,
                            AuthState.toggle_password_visibility,
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    rx.vstack(
                        _profile_picture_uploader(),
                        rx.input(
                            placeholder="Username",
                            value=AuthState.signup_username,
                            on_change=AuthState.set_signup_username,
                            width="100%",
                        ),
                        rx.input(
                            placeholder="Email (optional)",
                            type="email",
                            value=AuthState.email,
                            on_change=AuthState.set_email,
                            width="100%",
                        ),
                        _password_field(
                            AuthState.password,
                            AuthState.set_password,
                            AuthState.signup_password_visible,
                            AuthState.toggle_signup_password_visibility,
                        ),
                        spacing="3",
                        width="100%",
                    ),
                ),
                rx.button(
                    rx.cond(AuthState.mode == "login", "Sign in", "Create account"),
                    on_click=AuthState.submit(rx.color_mode_cond("light", "dark")),
                    width="100%",
                    background_color=rx.color_mode_cond("#2f855a", "#276749"),
                    color="white",
                    _hover={"background_color": rx.color_mode_cond("#276749", "#22543d")},
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
            background_color=rx.color_mode_cond( "white", "#2d3748"
            ),
            color=rx.color_mode_cond( "#1a202c", "#f7fafc"
            ),
        ),
        min_height="100vh",
        width="100%",
        padding="2em",
        background_color=rx.color_mode_cond( "#f7fafc", "#1a202c"
        ),
    )
