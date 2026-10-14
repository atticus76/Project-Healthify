import reflex as rx
from ..components.header import page_header
from ..state.profile import ProfileState

@rx.page(route="/profile")
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
                        value=ProfileState.gender,
                        on_change=ProfileState.set_gender,
                        width="100%",
                    ),
                    rx.text(ProfileState.gender_error, color="red"),
                    rx.text("Age", weight="bold"),
                    rx.input(
                        name="age",
                        type="number",
                        placeholder="e.g. 29",
                        value=ProfileState.age,
                        on_change=ProfileState.set_age,
                        min="13",
                        width="100%",
                    ),
                    rx.text(ProfileState.age_error, color="red"),
                    rx.text("Weight (lb)", weight="bold"),
                    rx.input(
                        name="weight_lb",
                        type="text",
                        placeholder="e.g. 175",
                        value=ProfileState.weight_lb,
                        on_change=ProfileState.set_weight_lb,
                        width="100%",
                    ),
                    rx.text(ProfileState.weight_error, color="red"),
                    rx.text(ProfileState.form_error, color="red"),
                    rx.button("Save Profile", type="submit", width="100%"),
                    rx.text(ProfileState.save_message, color="green"),
                ),
                on_submit=ProfileState.save_profile,
                reset_on_submit=False,
                width="100%",
            ),
            rx.cond(
                ProfileState.save_message != "",
                rx.box(
                    rx.heading("Your baseline", size="5"),
                    rx.text(
                        "Baseline weight: ",
                        ProfileState.baseline_weight_lb,
                    ),
                    rx.text(
                        "Estimated daily calories: ",
                        ProfileState.estimated_daily_calories,
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