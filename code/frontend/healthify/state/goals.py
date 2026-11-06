import json
import smtplib
from datetime import datetime, timedelta, timezone

import reflex as rx

from backend import alerts, email_alerts, goals as goals_backend
from .session import SessionState


class GoalsState(SessionState):
    goals: list[dict[str, str]] = []
    goal_type: str = goals_backend.GOAL_DAILY_STEPS
    target_input: str = "10000"
    reminders_enabled: bool = True
    reminder_25_enabled: bool = True
    reminder_50_enabled: bool = True
    reminder_75_enabled: bool = True
    is_daily: bool = True
    deadline_mode: str = "deadline"
    deadline_input: str = ""
    duration_input: str = "1"
    duration_unit: str = "days"
    today_steps_input: str = ""
    goal_dialog_open: bool = False
    goal_error: str = ""
    progress_error: str = ""
    progress_message: str = ""
    motivational_prompt: str = ""
    email_input: str = ""
    alert_email: str = ""
    email_configured: bool = False
    email_message: str = ""
    email_error: str = ""
    sending_test_email: bool = False

    def _user_id(self) -> str:
        return self.username

    def load_page(self):
        email_alerts.reload_config()
        user_id = self._user_id()
        self.alert_email = email_alerts.recipient(user_id)
        self.email_input = self.alert_email
        self.email_configured = email_alerts.is_configured()
        self._load_goals()
        events = self._deliver_notifications(goals_backend.refresh_reminders(user_id))
        events.append(
            rx.call_script(
                "if (window.healthifyGoalsRefresh) clearInterval(window.healthifyGoalsRefresh);"
                "window.healthifyGoalsRefresh = setInterval(() => {"
                "const button = document.getElementById('goals-auto-refresh');"
                "if (button) button.click();"
                "}, 1000);"
            )
        )
        return events

    def refresh_goals(self):
        self._load_goals()

    def _load_goals(self):
        self.goals = []
        for item in goals_backend.list_goals(self._user_id()):
            target = item["target"]
            steps = item.get("steps", 0)
            self.goals.append(
                {
                    "id": str(item["id"]),
                    "label": "Step Count" + (" (daily)" if item["is_daily"] else ""),
                    "target": str(target),
                    "steps": str(steps),
                    "percent": str(min(100, int(steps * 100 / target))),
                    "status": item.get("status", "in_progress").replace("_", " ").title(),
                    "reminders": "Reminders on" if item["reminders_enabled"] else "Reminders off",
                    "created": item["created_at"],
                    "deadline": item["deadline_at"].replace("T", " T", 1),
                }
            )

    def open_goal_dialog(self):
        self.goal_type = goals_backend.GOAL_DAILY_STEPS
        self.target_input = "10000"
        self.reminders_enabled = True
        self.reminder_25_enabled = True
        self.reminder_50_enabled = True
        self.reminder_75_enabled = True
        self.is_daily = True
        self.deadline_mode = "deadline"
        self.deadline_input = ""
        self.duration_input = "1"
        self.duration_unit = "days"
        self.goal_error = ""
        self.goal_dialog_open = True

    def set_goal_dialog_open(self, is_open: bool):
        self.goal_dialog_open = is_open

    def set_goal_type(self, value: str):
        self.goal_type = value

    def set_target_input(self, value: str):
        self.target_input = value

    def set_reminders_enabled(self, value: bool):
        self.reminders_enabled = value

    def set_reminder_25_enabled(self, value: bool):
        self.reminder_25_enabled = value

    def set_reminder_50_enabled(self, value: bool):
        self.reminder_50_enabled = value

    def set_reminder_75_enabled(self, value: bool):
        self.reminder_75_enabled = value

    def set_is_daily(self, value: bool):
        self.is_daily = value

    def set_deadline_mode(self, value: str):
        self.deadline_mode = value

    def set_deadline_input(self, value: str):
        self.deadline_input = value

    def set_duration_input(self, value: str):
        self.duration_input = value

    def set_duration_unit(self, value: str):
        self.duration_unit = value

    def set_today_steps_input(self, value: str):
        self.today_steps_input = value

    def add_goal(self):
        self.goal_error = ""
        try:
            target = int(self.target_input.strip())
            deadline = None
            if not self.is_daily:
                if self.deadline_mode == "deadline":
                    deadline = self.deadline_input
                else:
                    amount = float(self.duration_input)
                    seconds = amount * (3600 if self.duration_unit == "hours" else 86400)
                    deadline = (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()
            goals_backend.add_goal(
                self._user_id(), self.goal_type, target, self.reminders_enabled,
                self.is_daily, deadline, self.reminder_25_enabled,
                self.reminder_50_enabled, self.reminder_75_enabled,
            )
        except (ValueError, TypeError) as exc:
            self.goal_error = str(exc)
            return
        self.goal_dialog_open = False
        self._load_goals()

    def record_steps(self, goal_id: str):
        self.progress_error = ""
        self.progress_message = ""
        try:
            steps = int(self.today_steps_input.strip())
            result = goals_backend.record_steps(self._user_id(), steps, goal_id=int(goal_id))
        except (ValueError, TypeError) as exc:
            self.progress_error = str(exc)
            return
        self._load_goals()
        if result["milestones"]:
            milestone = result["milestones"][-1]
            message = f"You reached the {milestone}% step-goal milestone."
            email_alerts.dispatch(
                self._user_id(),
                [{"title": "Fitness goal progress", "message": message, "severity": alerts.SEVERITY_INFO}],
            )
            self.progress_message = message
            return [
                rx.toast.success(message, title="Goal progress"),
                rx.call_script(self._notification_script("Goal progress", message)),
            ]
        self.progress_message = "Today's step progress was updated."

    def check_day(self, goal_id: str):
        self.progress_error = ""
        try:
            result = goals_backend.complete_day(self._user_id(), goal_id=int(goal_id))
        except ValueError as exc:
            self.progress_error = str(exc)
            return
        self.motivational_prompt = result["prompt"]
        self._load_goals()
        if result["status"] == "incomplete":
            self.progress_message = "Today was logged as incomplete."
            if result["prompt"]:
                return [
                    rx.toast.info(result["prompt"], title="Tomorrow's motivation", duration=15000),
                    rx.call_script(
                        self._notification_script("Tomorrow's motivation", result["prompt"])
                    ),
                ]
        else:
            self.progress_message = "Today's goal was completed."

    def end_goal(self, goal_id: str):
        self.progress_error = ""
        try:
            result = goals_backend.end_goal(self._user_id(), goal_id=int(goal_id))
        except ValueError as exc:
            self.progress_error = str(exc)
            return
        self.motivational_prompt = result["prompt"]
        self._load_goals()
        self.progress_message = (
            "Goal completed and locked." if result["status"] == "complete"
            else "Goal ended as incomplete."
        )

    def delete_goal(self, goal_id: str):
        goals_backend.delete_goal(self._user_id(), int(goal_id))
        self._load_goals()

    def _deliver_notifications(self, notifications: list[dict[str, str]]):
        events = []
        for notification in notifications:
            email_alerts.dispatch(self._user_id(), [{
                "title": notification["title"],
                "message": notification["message"],
                "severity": alerts.SEVERITY_INFO,
            }])
            events.extend([
                rx.toast.info(notification["message"], title=notification["title"], duration=15000),
                rx.call_script(
                    self._notification_script(notification["title"], notification["message"])
                ),
            ])
        return events

    def set_email_input(self, value: str):
        self.email_input = value

    def save_email(self):
        self.email_error = ""
        self.email_message = ""
        address = self.email_input.strip()
        if not email_alerts.is_valid_address(address):
            self.email_error = "Enter a valid email address, like name@example.com."
            return
        alerts.set_alert_email(self._user_id(), address)
        self.alert_email = address
        self.email_message = "This address will receive alert and goal emails."

    def turn_off_email(self):
        alerts.set_alert_email(self._user_id(), "")
        self.alert_email = ""
        self.email_input = ""
        self.email_message = "Email notifications are off."

    def send_test_email(self):
        self.email_message = ""
        self.email_error = ""
        self.sending_test_email = True
        yield
        try:
            sent_to = email_alerts.send_test(self._user_id())
            self.email_message = f"Test email sent to {sent_to}."
        except (ValueError, email_alerts.EmailNotConfigured) as exc:
            self.email_error = str(exc)
        except smtplib.SMTPAuthenticationError:
            self.email_error = "The mail server rejected the SMTP credentials."
        except (smtplib.SMTPException, OSError) as exc:
            self.email_error = f"Couldn't send the test email: {exc}"
        finally:
            self.sending_test_email = False

    @staticmethod
    def _notification_script(title: str, message: str) -> str:
        return (
            "if ('Notification' in window && Notification.permission === 'granted') {"
            f"new Notification({json.dumps(title)}, "
            f"{{body: {json.dumps(message)}, requireInteraction: false}});"
            "}"
        )
