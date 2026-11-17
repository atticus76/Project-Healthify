import reflex as rx
from backend import db
from backend import goals as goals_backend
from backend import reports as reports_backend
from .errors import handle_backend_exception
from .pages import (
    account,
    alerts,
    dashboard,
    devices,
    emulator,
    goals,
    login,
    profile,
    reports,
)
from .pages.placeholders import disclaimer

# Stop with a clear message instead of failing on the first sign-in (S2-04).
db.require_database_url()

app = rx.App(
    backend_exception_handler=handle_backend_exception,
    head_components=[
        rx.el.link(rel="icon", href="/leaf.svg", type="image/svg+xml")
    ],
)
goals_backend.start_scheduler()
reports_backend.start_scheduler()