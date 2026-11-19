"""Account settings and editable health profile."""

import reflex as rx
from backend.profile_controller import ACTIVITY_LEVELS

from ..components.measurements import measurement_fields
from ..components import page_header
from ..state.auth import AuthState


def _profile_picture_editor() -> rx.Component:
    return rx.vstack(
        rx.cond(
            AuthState.profile_picture != "",
            rx.image(
                src=AuthState.profile_picture,
                width="112px",
                height="112px",
                border_radius="50%",
                object_fit="cover",
            ),
            rx.avatar(fallback="?", size="9"),
        ),
        rx.hstack(
            rx.upload.root(
                rx.hstack(
                    rx.icon("pen"),
                    rx.text("Change picture"),
                    align="center",
                    spacing="2",
                ),
                id="account-profile-picture",
                cursor="pointer",
                on_drop=AuthState.handle_profile_picture(
                    rx.upload_files(upload_id="account-profile-picture")
                ),
            ),
            rx.cond(
                AuthState.profile_picture != "",
                rx.button(
                    "Remove picture",
                    on_click=AuthState.remove_profile_picture,
                    variant="ghost",
                    color_scheme="red",
                    size="2",
                ),
            ),
            align="center",
            spacing="2",
        ),
        rx.text(AuthState.profile_picture_error, color="red", size="2"),
        align="center",
        spacing="2",
    )


@rx.page(route="/account", on_load=AuthState.load_account, title="Account | Healthify")
def account_page() -> rx.Component:
    return rx.vstack(
        page_header(),
        rx.vstack(
            rx.heading("Account", size="8"),
            rx.text("Manage your profile and the health information used for your baseline."),
            _profile_picture_editor(),
            rx.text("Username: ", AuthState.username, weight="bold"),
            rx.form(
                rx.vstack(
                    rx.text("Email", weight="bold"),
                    rx.input(
                        type="email",
                        value=AuthState.email,
                        on_change=AuthState.set_email,
                        width="100%",
                    ),
                    rx.text("Gender", weight="bold"),
                    rx.select(
                        ["Male", "Female", "Non-binary", "Prefer not to say"],
                        value=AuthState.gender,
                        on_change=AuthState.set_gender,
                        width="100%",
                    ),
                    rx.text("Age", weight="bold"),
                    rx.input(
                        type="number",
                        value=AuthState.age,
                        on_change=AuthState.set_age,
                        min="13",
                        width="100%",
                    ),
                    measurement_fields(),
                    rx.text("Activity level", weight="bold"),
                    rx.select(list(ACTIVITY_LEVELS), placeholder="Select activity level",
                              value=AuthState.activity_level, on_change=AuthState.set_activity_level,
                              width="100%"),
                    rx.text("Your saved measurements are used by MyPlate.food for your daily calorie target.", size="1"),
                    rx.text(AuthState.profile_error, color="red"),
                    rx.button("Save changes", type="submit", width="100%"),
                    rx.text(AuthState.profile_saved, color="green"),
                    spacing="3",
                    width="100%",
                ),
                on_submit=AuthState.save_profile_on_account,
                reset_on_submit=False,
                width="100%",
            ),
            rx.button(
                rx.cond(
                    AuthState.changing_password,
                    "Cancel password change",
                    "Change password",
                ),
                on_click=AuthState.toggle_password_change,
                variant="outline",
                size="2",
            ),
            rx.cond(
                AuthState.changing_password,
                rx.form(
                    rx.vstack(
                        rx.input(
                            placeholder="Current password",
                            type="password",
                            value=AuthState.current_password,
                            on_change=AuthState.set_current_password,
                            width="100%",
                        ),
                        rx.input(
                            placeholder="New password",
                            type="password",
                            value=AuthState.new_password,
                            on_change=AuthState.set_new_password,
                            width="100%",
                        ),
                        rx.input(
                            placeholder="Repeat new password",
                            type="password",
                            value=AuthState.repeated_password,
                            on_change=AuthState.set_repeated_password,
                            width="100%",
                        ),
                        rx.text(
                            "New password: at least 8 characters, one capital letter, "
                            "one number, and one special character.",
                            size="2",
                            color="gray",
                        ),
                        rx.text(AuthState.password_change_error, color="red"),
                        rx.button("Update password", type="submit", width="100%"),
                        spacing="3",
                        width="100%",
                    ),
                    on_submit=AuthState.change_password,
                    reset_on_submit=False,
                    width="100%",
                ),
            ),
            rx.text(AuthState.password_change_message, color="green"),
            rx.button(
                "Back to Dashboard",
                on_click=rx.redirect("/"),
                variant="outline",
            ),
            width="100%",
            max_width="600px",
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
