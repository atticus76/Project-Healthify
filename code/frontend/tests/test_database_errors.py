"""Any page shows the friendly message when the database is unreachable (S2-04).

Spec scenario "Database is unreachable": the page shows "Couldn't reach the
database. Try again in a moment." Event handlers that don't catch
DatabaseError themselves are covered by one app-wide handler.
"""

from reflex_base.event import EventSpec

from backend.db import DatabaseError, UNREACHABLE_MESSAGE
from healthify import errors


def _text(spec: EventSpec) -> str:
    return repr(spec)


def test_database_errors_show_the_friendly_message():
    spec = errors.handle_backend_exception(DatabaseError("load goals"))
    assert isinstance(spec, EventSpec)
    assert UNREACHABLE_MESSAGE in _text(spec)


def test_repeated_database_errors_reuse_one_toast():
    # Goals and Reports reload every second; don't stack a toast per second.
    first = _text(errors.handle_backend_exception(DatabaseError("load goals")))
    assert errors.DATABASE_TOAST_ID in first


def test_other_errors_keep_reflexs_default_handling():
    spec = errors.handle_backend_exception(RuntimeError("boom"))
    assert UNREACHABLE_MESSAGE not in _text(spec)
    assert "An error occurred." in _text(spec)


def test_the_app_uses_the_handler():
    import importlib
    import os
    from unittest import mock

    with mock.patch.dict(os.environ, {"DATABASE_URL": "postgresql://example"}), \
            mock.patch("backend.goals.start_scheduler"), mock.patch("backend.reports.start_scheduler"):
        app_module = importlib.import_module("healthify.healthify")
    assert app_module.app.backend_exception_handler is errors.handle_backend_exception
