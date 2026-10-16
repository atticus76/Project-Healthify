import reflex as rx

def page_header() -> rx.Component:
    return rx.hstack(
        rx.heading("Healthify", size="7"),
        rx.text("Welcome USER", size="4"),
        rx.spacer(),
        rx.color_mode.button(),
        width="100%",
        padding="1em 2em",
        background_color=rx.color_mode_cond("#2f855a", "#22543d"),
        color="white",
        border_bottom=rx.color_mode_cond(
            "4px solid #276749", "4px solid #1c4532"
        ),
        align="center",
    )