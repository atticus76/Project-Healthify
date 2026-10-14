import reflex as rx
from .empty import empty_feature_page

@rx.page(route="/account")
def disclaimer_page() -> rx.Component:
    return empty_feature_page("Account")