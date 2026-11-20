"""Who is signed in, per browser session (S2-04 task 5, cleanup C2).

Every page state inherits from SessionState and reads `self.username`, so each
browser tab sees its own user. (Decided 2026-11-05: inherit instead of
`await self.get_state(AuthState)`, which would make every handler async.)

SessionState holds only the session so page states don't clash with
AuthState's form fields (email, error, message, ...): Reflex doesn't allow a
substate to redefine a parent's var.
"""

import reflex as rx
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from backend.db import connect


class SessionState(rx.State):
    # Set only by a successful sign-in or sign-up; never by typing in a form.
    username: str = ""

    meal_timezone: str = ""
    _timezone_user: str = ""

    def set_meal_timezone(self, name: str):
        if not self.username or (name == self.meal_timezone and self._timezone_user == self.username):
            return
        try:
            ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            return
        with connect("save meal time zone") as conn:
            conn.execute("UPDATE users SET app_state=jsonb_set(app_state,'{meal_timezone}',to_jsonb(%s::text)) "
                         "WHERE username=%s", (name, self.username))
        self.meal_timezone = name
        self._timezone_user = self.username

    def require_login(self):
        if not self.username:
            return rx.redirect("/login")
