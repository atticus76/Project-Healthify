"""App-wide handling of errors raised by event handlers (S2-04).

Spec scenario "Database is unreachable": the page shows "Couldn't reach the
database. Try again in a moment." Forms that can show the message inline
(sign-in, profile, devices) catch DatabaseError themselves; everything else
ends up here and gets a toast. backend.db has already logged the failure with
the operation that failed.
"""

from reflex.app import default_backend_exception_handler
from reflex_base.event import EventSpec

import reflex as rx

from backend.db import DatabaseError

# One toast id, so pages that reload every second (Goals, Reports) show one
# message while the database is down instead of a new toast each second.
DATABASE_TOAST_ID = "database_unreachable"


def handle_backend_exception(exception: Exception) -> EventSpec:
    if isinstance(exception, DatabaseError):
        return rx.toast.error(
            str(exception),
            id=DATABASE_TOAST_ID,
            position="top-center",
        )
    return default_backend_exception_handler(exception)
