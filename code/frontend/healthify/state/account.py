"""Reflex state management for US-02 Account Registration."""

from __future__ import annotations

import sys
from pathlib import Path
import reflex as rx

# Ensure backend directory is importable regardless of working directory
BACKEND_DIR = Path(__file__).resolve().parents[3] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from account_controller import register_account  # noqa: E402


class AccountState(rx.State):
    """State for account creation and authentication feedback."""

    email: str = ""
    password: str = ""
    error_message: str = ""
    current_user: str = ""

    def set_email(self, value: str) -> None:
        self.email = value
        if self.error_message:
            self.error_message = ""

    def set_password(self, value: str) -> None:
        self.password = value
        if self.error_message:
            self.error_message = ""

    def submit_registration(self):
        """Handle registration submission for Scenario 1 & Scenario 2."""
        success, message = register_account(self.email, self.password)

        if not success:
            # Scenario 2 / Validation Failure: Show error popup message
            self.error_message = message
            return

        # Scenario 1: Save session user, clear form, and redirect to dashboard
        self.current_user = self.email.strip().lower()
        self.email = ""
        self.password = ""
        self.error_message = ""
        return rx.redirect("/")