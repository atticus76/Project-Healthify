import json
import reflex as rx
from datetime import datetime

from backend import email_alerts, reports as reports_backend
from .session import SessionState


def _readable_timestamp(value: str) -> str:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone().strftime(
            "%Y-%m-%d %I:%M:%S %p"
        )
    except ValueError:
        return value.replace("T", " ", 1)


def _readable_period(start: str, end: str) -> str:
    return f"{_readable_timestamp(start)} through {_readable_timestamp(end)}"


class ReportsState(SessionState):
    frequency: str = "weekly"
    email: str = ""
    preferences_saved: str = ""
    error: str = ""
    report_message: str = ""
    latest_report: dict[str, str] = {}
    metrics_available: bool = False
    metrics_message: str = ""
    goal_summary: list[dict[str, str]] = []
    alert_summary: list[dict[str, str]] = []
    telemetry_summary: list[str] = []
    calorie_lines: list[str] = []
    report_text: str = ""

    def _user_id(self) -> str:
        return self.username

    def load_page(self):
        email_alerts.reload_config()
        user_id = self._user_id()
        preferences = reports_backend.get_preferences(user_id)
        if preferences:
            self.frequency = preferences["frequency"]
            self.email = preferences["email"]
        else:
            self.email = email_alerts.recipient(user_id)
        if reports_backend.get_report(user_id) is None:
            self._generate_report()
        else:
            self.refresh_report()
        return rx.call_script(
            "if (window.healthifyReportRefresh) clearInterval(window.healthifyReportRefresh);"
            "window.healthifyReportRefresh = setInterval(() => {"
            "const button = document.getElementById('report-refresh');"
            "if (button) button.click();"
            "}, 1000);"
        )

    def set_frequency(self, value: str):
        self.frequency = value

    def set_email(self, value: str):
        self.email = value

    def save_preferences(self):
        self.error = ""
        self.preferences_saved = ""
        try:
            reports_backend.save_preferences(self._user_id(), self.frequency, self.email)
        except ValueError as exc:
            self.error = str(exc)
            return
        self.preferences_saved = "Reporting preferences saved."

    def _generate_report(self):
        self.error = ""
        self.report_message = ""
        try:
            report = reports_backend.generate_report(self._user_id())
        except (ValueError, OSError) as exc:
            self.error = str(exc)
            return
        self._set_report(report)

    def refresh_report(self):
        try:
            self._set_report(reports_backend.generate_report(self._user_id(), persist=False))
        except (ValueError, OSError) as exc:
            self.error = str(exc)

    def print_report(self):
        self._set_report(reports_backend.generate_report(self._user_id(), persist=False))
        return rx.call_script(
            "const frame = document.createElement('iframe');"
            "frame.style.cssText='position:fixed;width:0;height:0;border:0';"
            "document.body.appendChild(frame);"
            "const doc=frame.contentDocument; doc.title='Healthify Health Report';"
            "const text=doc.createElement('pre');text.style.whiteSpace='pre-wrap';"
            "text.textContent=" + json.dumps(self.report_text) + ";doc.body.appendChild(text);"
            "frame.contentWindow.onafterprint=()=>frame.remove();frame.contentWindow.print();"
        )

    def export_report(self):
        self._set_report(reports_backend.generate_report(self._user_id(), persist=False))
        escaped_text = (
            self.report_text.replace("\\", "\\\\")
            .replace("`", "\\`")
            .replace("${", "\\${")
        )
        return rx.call_script(
            "const blob = new Blob([`"
            + escaped_text
            + "`], {type: 'text/plain'});"
            "const link = document.createElement('a');"
            "link.href = URL.createObjectURL(blob);"
            "link.download = 'healthify-report.txt';"
            "link.click();"
            "URL.revokeObjectURL(link.href);"
        )

    def _set_report(self, report: dict):
        content = report["content"]
        self.latest_report = {
            "period": _readable_period(report["period_start"], report["period_end"]),
            "updated": _readable_timestamp(report["generated_at"]),
            "delivery": report["delivery_status"],
            "delivery_error": report["delivery_error"],
        }
        snapshot = content.get("calories", {})
        self.calorie_lines = [
            f"{name.title()}: {snapshot[name]} kcal" if snapshot.get(name) is not None
            else f"{name.title()}: unavailable"
            for name in ("target", "burned", "consumed")
        ]
        self.report_text = self._format_report(report)
        self.metrics_available = content["metrics"]["available"]
        self.metrics_message = content["metrics"]["message"]
        self.telemetry_summary = content["metrics"].get("summaries", [])
        self.goal_summary = [
            {**{key: str(value) for key, value in item.items()}, "unit": item.get("label", "steps")}
            for item in content["goals"]
        ]
        self.alert_summary = [
            {key: str(value) for key, value in item.items()}
            for item in content["alerts"]
        ]

    def _format_report(self, report: dict) -> str:
        content = report["content"]
        lines = [
            "Healthify Health Report",
            f"Period: {_readable_period(report['period_start'], report['period_end'])}",
            f"Last updated: {_readable_timestamp(report['generated_at'])}",
            f"Delivery: {report['delivery_status']}",
            "",
            "Calories",
            *self.calorie_lines,
            "",
            "Telemetry",
            content["metrics"]["message"],
            "",
            "Live telemetry",
        ]
        lines.extend(
            f"- {summary}"
            for summary in content["metrics"].get("summaries", [])
        )
        if not content["metrics"].get("summaries"):
            lines.append("- No live telemetry samples are currently available.")
        lines.append("")
        lines.append("Fitness goal progress")
        lines.extend(
            f"- {item['steps']} / {item['target']} {item.get('label', 'steps')} ({item['percent']}%) - {item['status']}"
            for item in content["goals"]
        )
        if not content["goals"]:
            lines.append("- No goal data was available for this period.")
        lines.append("")
        lines.append("Telemetry alerts")
        lines.extend(
            f"- {item['title']}: {item['message']}"
            for item in content["alerts"]
        )
        if not content["alerts"]:
            lines.append("- No alerts were recorded for this period.")
        return "\n".join(lines)
