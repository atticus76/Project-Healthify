import reflex as rx
import json
from backend import alerts
from backend.google_health import DEMO_USER_ID
from backend.telemetry_emulator import PROFILES, SCENARIOS, generate_fitbit_data, summarize_fitbit_data
from .alerts import notify

class TelemetryState(rx.State):
    level: str = "Medium"
    scenario: str = "normal"
    enabled: bool = False
    show_payload: bool = False
    summaries: list[str] = []
    payload_json: str = ""

    def set_level(self, value: str):
        if value not in PROFILES:
            raise ValueError(f"Unknown simulation level: {value}")
        self.level = value
        if self.enabled:
            return self._generate_data()

    def set_scenario(self, value: str):
        if value not in SCENARIOS:
            raise ValueError(f"Unknown simulation scenario: {value}")
        self.scenario = value
        if self.enabled:
            return self._generate_data()

    def enable(self):
        self.enabled = True
        return self._generate_data()

    def refresh(self):
        if not self.enabled:
            raise RuntimeError("Enable the telemetry emulator before refreshing.")
        return self._generate_data()

    def disable(self):
        self.enabled = False
        self.show_payload = False
        self.summaries = []
        self.payload_json = ""

    def toggle_payload(self):
        self.show_payload = not self.show_payload

    def _generate_data(self):
        data = generate_fitbit_data(self.level, scenario=self.scenario)
        self.summaries = summarize_fitbit_data(data)
        self.payload_json = json.dumps(data, indent=2)
        return notify(alerts.check_telemetry(data, DEMO_USER_ID))
