import reflex as rx
from .empty import empty_feature_page

@rx.page(route="/reports")
def reports_page() -> rx.Component:
    return empty_feature_page("Reports & Analytics")