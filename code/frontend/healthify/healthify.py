import reflex as rx
from backend import goals as goals_backend
from backend import reports as reports_backend
from backend.google_health import DEMO_USER_ID
from .pages import dashboard, profile, emulator, devices, alerts, goals, reports, login
from .pages.placeholders import cloud_data, disclaimer

app = rx.App()
goals_backend.start_scheduler(DEMO_USER_ID)
reports_backend.start_scheduler(DEMO_USER_ID)