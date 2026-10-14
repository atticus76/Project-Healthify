import reflex as rx
from ...components import page_header

def empty_feature_page(title: str) -> rx.Component:
    return rx.vstack(
        page_header(),
        rx.center(
            rx.vstack(
                rx.heading(title, size="7"),
                rx.button(
                    "Back to Dashboard",
                    on_click=rx.redirect("/"),
                    background_color=rx.color_mode_cond("#2f855a", "#276749"),
                    color="white",
                    _hover={
                        "background_color": rx.color_mode_cond(
                            "#276749", "#1c4532"
                        ),
                    },
                ),
                align="center",
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