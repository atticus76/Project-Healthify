"""Who is signed in, per browser session (S2-04 task 5, cleanup C2).

Every page state inherits from SessionState and reads `self.username`, so each
browser tab sees its own user. (Decided 2026-11-05: inherit instead of
`await self.get_state(AuthState)`, which would make every handler async.)

SessionState holds only the session so page states don't clash with
AuthState's form fields (email, error, message, ...): Reflex doesn't allow a
substate to redefine a parent's var.
"""

import reflex as rx


class SessionState(rx.State):
    # Set only by a successful sign-in or sign-up; never by typing in a form.
    username: str = ""

    def require_login(self):
        if not self.username:
            return rx.redirect("/login")
