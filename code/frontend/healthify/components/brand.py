import reflex as rx


def brand_mark(size: str = "28px") -> rx.Component:
    return rx.image(
        src="/leaf.svg",
        alt="Healthify leaf",
        width=size,
        height=size,
    )
