"""The dashboard loads the unread alert count, not the alert list (S3-01 optimisation 2).

Spec: code/specs/features/S3-01-response-time-check.md
Scenario: The dashboard reads the unread alert count, not the alert list
"""

import ast
from pathlib import Path
from unittest import mock

import reflex as rx

from healthify.state.alerts import AlertState
from healthify.state.session import SessionState

DASHBOARD = Path(__file__).resolve().parents[1] / "healthify" / "pages" / "dashboard.py"


def _alert_state(username: str) -> AlertState:
    browser = rx.State(_reflex_internal_init=True)
    browser.get_substate(SessionState.get_full_name().split(".")[1:]).username = username
    return browser.get_substate(AlertState.get_full_name().split(".")[1:])


def _on_load_handlers(route: str) -> list[str]:
    tree = ast.parse(DASHBOARD.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            keywords = {k.arg: k.value for k in decorator.keywords}
            if isinstance(keywords.get("route"), ast.Constant) and keywords["route"].value == route:
                return [ast.unparse(item) for item in keywords["on_load"].elts]
    raise AssertionError(f"no page for {route}")


def test_dashboard_loads_the_unread_count_without_the_alert_list():
    state = _alert_state("alice")

    with mock.patch("healthify.state.alerts.alerts.unacknowledged_count", return_value=500) as count, \
            mock.patch("healthify.state.alerts.alerts.list_alerts") as list_alerts:
        AlertState.load_unread.fn(state)

    count.assert_called_once_with("alice")
    list_alerts.assert_not_called()
    assert state.unread == 500


def test_dashboard_on_load_uses_the_unread_count():
    handlers = _on_load_handlers("/")

    assert "AlertState.load_unread" in handlers
    assert "AlertState.load" not in handlers
