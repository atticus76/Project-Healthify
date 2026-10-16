import reflex as rx
from .empty import empty_feature_page

@rx.page(route="/goals")
def goals_page() -> rx.Component:
    return empty_feature_page("Health Goals")