import reflex as rx
from .empty import empty_feature_page

@rx.page(route="/cloud-data")
def cloud_data_page() -> rx.Component:
    return empty_feature_page("Cloud Data")