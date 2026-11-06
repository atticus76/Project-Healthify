"""The signed-in user is per browser session, not one global (S2-04 task 5, cleanup C2).

Each test builds separate Reflex state trees, one per "browser", and mocks the
backend so no database is needed.
"""

from unittest import mock

import pytest
import reflex as rx

from backend import auth_controller
from healthify.state.alerts import AlertState
from healthify.state.auth import AuthState
from healthify.state.devices import DeviceState
from healthify.state.goals import GoalsState
from healthify.state.reports import ReportsState
from healthify.state.session import SessionState
from healthify.state.telemetry import TelemetryState

PAGE_STATES = (AlertState, DeviceState, GoalsState, ReportsState, TelemetryState, AuthState)


def _browser() -> rx.State:
    """A fresh state tree, like a new browser tab."""
    return rx.State(_reflex_internal_init=True)


def _state(browser: rx.State, cls):
    return browser.get_substate(cls.get_full_name().split(".")[1:])


def _sign_in(browser: rx.State, username: str) -> None:
    auth = _state(browser, AuthState)
    auth.identifier, auth.password = username, "Testpass1!"
    account = {"username": username, "email": "", "app_state": {}, "has_profile": True}
    with mock.patch.object(auth_controller, "sign_in", return_value=(True, "Signed in.", account)):
        AuthState.submit.fn(auth)


def _redirects(events) -> bool:
    return events is not None


def test_there_is_no_global_signed_in_user():
    for name in ("get_active_user", "set_active_user", "clear_active_user", "_active_user"):
        assert not hasattr(auth_controller, name), name


@pytest.mark.parametrize("cls", PAGE_STATES, ids=lambda c: c.__name__)
def test_every_page_state_shares_the_session(cls):
    assert issubclass(cls, SessionState)


def test_two_browsers_stay_signed_in_as_different_users():
    alice_browser, bob_browser = _browser(), _browser()
    _sign_in(alice_browser, "alice")
    _sign_in(bob_browser, "bob")

    assert _state(alice_browser, GoalsState).username == "alice"
    assert _state(bob_browser, GoalsState).username == "bob"


def test_pages_load_the_data_of_the_user_in_that_browser():
    alice_browser, bob_browser = _browser(), _browser()
    _sign_in(alice_browser, "alice")
    _sign_in(bob_browser, "bob")

    with mock.patch("healthify.state.goals.goals_backend.list_goals", return_value=[]) as list_goals:
        GoalsState.refresh_goals.fn(_state(alice_browser, GoalsState))
        GoalsState.refresh_goals.fn(_state(bob_browser, GoalsState))

    assert [c.args[0] for c in list_goals.call_args_list] == ["alice", "bob"]


def test_signing_out_only_affects_that_browser():
    alice_browser, bob_browser = _browser(), _browser()
    _sign_in(alice_browser, "alice")
    _sign_in(bob_browser, "bob")

    AuthState.logout.fn(_state(alice_browser, AuthState))

    assert _state(alice_browser, GoalsState).username == ""
    assert _state(bob_browser, GoalsState).username == "bob"


def test_typing_a_username_on_the_sign_up_form_does_not_sign_you_in():
    browser = _browser()
    auth = _state(browser, AuthState)
    AuthState.set_signup_username.fn(auth, "mallory")

    assert auth.username == ""
    assert _redirects(SessionState.require_login.fn(_state(browser, GoalsState)))


def test_signed_in_users_pass_the_login_check():
    browser = _browser()
    _sign_in(browser, "alice")
    assert not _redirects(SessionState.require_login.fn(_state(browser, GoalsState)))


def test_sign_up_uses_the_sign_up_form_field():
    browser = _browser()
    auth = _state(browser, AuthState)
    auth.mode = "signup"
    AuthState.set_signup_username.fn(auth, "Alice")
    auth.password = "Testpass1!"
    account = {"username": "Alice", "email": "", "app_state": {}, "has_profile": False}
    with mock.patch.object(
        auth_controller, "sign_up", return_value=(True, "Account created.", account)
    ) as sign_up:
        AuthState.submit.fn(auth)

    assert sign_up.call_args.args[0] == "Alice"
    assert auth.username == "Alice"
