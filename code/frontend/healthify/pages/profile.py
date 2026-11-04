import reflex as rx
from ..components import page_header
from ..state.auth import AuthState

@rx.page(route="/profile", on_load=AuthState.load_profile)
def profile_page() -> rx.Component:
    return rx.vstack(
        page_header(),
        rx.vstack(
            rx.heading("Profile Setup", size="8"),
            rx.text(
                "Enter your personal details so Healthify can calculate your initial baseline."
            ),
            rx.form(
                rx.vstack(
                    rx.text("Gender", weight="bold"),
                    rx.select(
                        [
                            "Male",
                            "Female",
                            "Non-binary",
                            "Prefer not to say",
                        ],
                        placeholder="Select gender",
                        value=AuthState.gender,
                        on_change=AuthState.set_gender,
                        width="100%",
                    ),
                    rx.text("Age", weight="bold"),
                    rx.input(
                        name="age",
                        type="number",
                        placeholder="e.g. 29",
                        value=AuthState.age,
                        on_change=AuthState.set_age,
                        min="13",
                        width="100%",
                    ),
                    rx.text("Weight (lb)", weight="bold"),
                    rx.input(
                        name="weight_lb",
                        type="text",
                        placeholder="e.g. 175",
                        value=AuthState.weight_lb,
                        on_change=AuthState.set_weight_lb,
                        width="100%",
                    ),
                    rx.text(AuthState.profile_error, color="red"),
                    rx.button("Save Profile", type="submit", width="100%"),
                    rx.text(AuthState.profile_saved, color="green"),
                ),
                on_submit=AuthState.save_profile,
                reset_on_submit=False,
                width="100%",
            ),
            rx.cond(
                AuthState.profile_saved != "",
                rx.box(
                    rx.heading("Your baseline", size="5"),
                    rx.text(
                        "Baseline weight: ",
                        AuthState.baseline_weight_lb,
                    ),
                    rx.text(
                        "Estimated daily calories: ",
                        AuthState.estimated_daily_calories,
                    ),
                    padding="1em",
                    width="100%",
                    border_radius="8px",
                    background_color=rx.color_mode_cond("#f0fff4", "#22543d"),
                ),
            ),
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