import reflex as rx
from .button import feature_button

def feature_grid(features: list[tuple[str, str]]) -> rx.Component:
    return rx.grid(
        *[feature_button(label, route) for label, route in features],
        columns="repeat(3, 1fr)",
        gap="1em",
        width="100%",
    )