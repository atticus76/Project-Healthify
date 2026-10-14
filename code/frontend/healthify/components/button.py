import reflex as rx

def feature_button(label: str, route: str) -> rx.Component:
    return rx.button(
        label,
        on_click=rx.redirect(route),
        width="100%",
        height="4em",
        background_color=rx.color_mode_cond("#2f855a", "#276749"),
        color="white",
        _hover={
            "background_color": rx.color_mode_cond("#276749", "#1c4532"),
        },
    )