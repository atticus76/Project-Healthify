import reflex as rx
from .empty import empty_feature_page

@rx.page(route="/alerts")
def alerts_page() -> rx.Component:
    return empty_feature_page("Alerts")