import reflex as rx
from ...components import page_header

@rx.page(route="/disclaimer")
def disclaimer_page() -> rx.Component:
    return rx.vstack(
        page_header(),
        rx.center(
            rx.vstack(
                rx.heading("Legal Disclaimer", size="7"),
                rx.text(
                    "Healthify is an educational health and fitness monitoring "
                    "application for beginner and intermediate athletes."
                ),
                rx.text(
                    "Healthify is not a medical device and does not provide "
                    "medical advice, diagnosis, treatment, or emergency detection."
                ),
                rx.text(
                    "Information from wearable devices and the telemetry emulator "
                    "may be incomplete, delayed, or inaccurate. Trends, alerts, "
                    "goals, and estimates are for informational purposes only."
                ),
                rx.text(
                    "Do not use Healthify to make urgent health decisions or as a "
                    "substitute for a qualified healthcare professional. Contact "
                    "local emergency services for an emergency and speak with a "
                    "licensed clinician about medical concerns."
                ),
                rx.text(
                    "By using Healthify, you acknowledge these limitations and "
                    "understand that you are responsible for decisions made using "
                    "the information shown in the application."
                ),
                rx.button(
                    "Back to Dashboard",
                    on_click=rx.redirect("/"),
                    background_color=rx.color_mode_cond("#2f855a", "#276749"),
                    color="white",
                ),
                max_width="720px",
                padding="2em",
                spacing="4",
            ),
            flex="1",
            width="100%",
        ),
        min_height="100vh",
        width="100%",
        background_color=rx.color_mode_cond("white", "#1a202c"),
        color=rx.color_mode_cond("#1a202c", "white"),
    )