import reflex as rx
from .empty import empty_feature_page

@rx.page(route="/devices")
def device_page() -> rx.Component:
    return empty_feature_page("Connect a Device")