import reflex as rx
from backend import db
from backend import goals as goals_backend
from backend import reports as reports_backend
from backend.google_health import DEMO_USER_ID
from .pages import dashboard, profile, emulator, devices, alerts, goals, reports, login
from .pages.placeholders import cloud_data, disclaimer

# Stop with a clear message instead of failing on the first sign-in (S2-04).
db.require_database_url()

app = rx.App()
goals_backend.start_scheduler(DEMO_USER_ID)
reports_backend.start_scheduler(DEMO_USER_ID)