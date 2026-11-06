import reflex as rx
import json
from backend import alerts, telemetry_store
from backend.telemetry_emulator import (
    PROFILES,
    SCENARIOS,
    generate_fitbit_data,
    summarize_fitbit_data,
)
from backend import goals as goals_backend
from backend.auth_controller import get_user, update_user
from .alerts import notify
from .session import SessionState

class TelemetryState(SessionState):
    chart_window_seconds: int = 10
    level: str = "Medium"
    scenario: str = "normal"
    enabled: bool = False
    show_payload: bool = False
    summaries: list[str] = []
    payload_json: str = ""
    device_name: str = "Telemetry Emulator"
    steps_points: list[dict[str, int | float | None]] = []
    heart_rate_points: list[dict[str, int | float | None]] = []
    resting_heart_rate_points: list[dict[str, int | float | None]] = []
    hrv_points: list[dict[str, int | float | None]] = []
    daily_hrv_points: list[dict[str, int | float | None]] = []
    zone_minutes_points: list[dict[str, int | float | None]] = []
    calories_points: list[dict[str, int | float | None]] = []
    distance_points: list[dict[str, int | float | None]] = []
    oxygen_points: list[dict[str, int | float | None]] = []
    chart_cycle_position: int = 0

    def load_page(self):
        user_id = self.username
        user = get_user(user_id)
        if user:
            self.enabled = bool(user.get("app_state", {}).get("telemetry_enabled", False))
        if not self.enabled:
            telemetry_store.clear(user_id, "emulator")
        return rx.call_script(
            "if (window.healthifyTelemetryRefresh) "
            "clearInterval(window.healthifyTelemetryRefresh);"
            "window.healthifyTelemetryRefresh = setInterval(() => {"
            "const button = document.getElementById('telemetry-auto-refresh');"
            "if (button) button.click();"
            "}, 1000);"
        )

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
        user = get_user(self.username) or {}
        app_state = dict(user.get("app_state", {}))
        app_state["telemetry_enabled"] = True
        update_user(self.username, app_state=app_state)
        return self._generate_data()

    def refresh(self):
        if not self.enabled:
            raise RuntimeError("Enable the telemetry emulator before refreshing.")
        return self._generate_data()

    def auto_refresh(self):
        if self.enabled:
            return self._generate_data()

    def disable(self):
        self.enabled = False
        user = get_user(self.username) or {}
        app_state = dict(user.get("app_state", {}))
        app_state["telemetry_enabled"] = False
        update_user(self.username, app_state=app_state)
        telemetry_store.clear(self.username, "emulator")
        self.show_payload = False
        self.summaries = []
        self.payload_json = ""
        self._clear_chart_points()

    def toggle_payload(self):
        self.show_payload = not self.show_payload

    def _generate_data(self):
        data = generate_fitbit_data(self.level, scenario=self.scenario)
        # In memory every refresh; saved to the cloud at most once a minute.
        telemetry_store.save(self.username, data, source="emulator")
        self.summaries = summarize_fitbit_data(data)
        self.payload_json = json.dumps(data, indent=2)
        if self.chart_cycle_position >= self.chart_window_seconds:
            self._clear_chart_points()
            self.chart_cycle_position = 1
        else:
            self.chart_cycle_position += 1
        timestamp = self.chart_cycle_position
        step_value = self._latest_value("steps", data["steps"]["dataPoints"])
        if step_value is not None:
            try:
                goals_backend.record_steps(self.username, int(step_value))
            except (IndexError, ValueError):
                pass
        series = {
            "steps": "steps_points",
            "heart-rate": "heart_rate_points",
            "daily-resting-heart-rate": "resting_heart_rate_points",
            "heart-rate-variability": "hrv_points",
            "daily-heart-rate-variability": "daily_hrv_points",
            "active-zone-minutes": "zone_minutes_points",
            "total-calories": "calories_points",
            "distance": "distance_points",
            "daily-oxygen-saturation": "oxygen_points",
        }
        next_points: dict[str, list[dict[str, int | float | None]]] = {}
        for data_type, field_name in series.items():
            value = self._latest_value(data_type, data[data_type]["dataPoints"])
            if value is not None:
                points = getattr(self, field_name)
                if len(points) != self.chart_window_seconds:
                    points = [
                        {"time": second, "value": None}
                        for second in range(1, self.chart_window_seconds + 1)
                    ]
                next_points[field_name] = points.copy()
                next_points[field_name][timestamp - 1] = {
                    "time": timestamp,
                    "value": value,
                }
        self.steps_points = next_points.get("steps_points", self.steps_points)
        self.heart_rate_points = next_points.get(
            "heart_rate_points", self.heart_rate_points
        )
        self.resting_heart_rate_points = next_points.get(
            "resting_heart_rate_points", self.resting_heart_rate_points
        )
        self.hrv_points = next_points.get("hrv_points", self.hrv_points)
        self.daily_hrv_points = next_points.get(
            "daily_hrv_points", self.daily_hrv_points
        )
        self.zone_minutes_points = next_points.get(
            "zone_minutes_points", self.zone_minutes_points
        )
        self.calories_points = next_points.get(
            "calories_points", self.calories_points
        )
        self.distance_points = next_points.get("distance_points", self.distance_points)
        self.oxygen_points = next_points.get("oxygen_points", self.oxygen_points)
        return notify(alerts.check_telemetry(data, self.username), self.username)

    def _clear_chart_points(self):
        for field_name in (
            "steps_points",
            "heart_rate_points",
            "resting_heart_rate_points",
            "hrv_points",
            "daily_hrv_points",
            "zone_minutes_points",
            "calories_points",
            "distance_points",
            "oxygen_points",
        ):
            setattr(
                self,
                field_name,
                [
                    {"time": second, "value": None}
                    for second in range(1, self.chart_window_seconds + 1)
                ],
            )
        self.chart_cycle_position = 0

    @staticmethod
    def _latest_value(data_type: str, points: list[dict]) -> float | None:
        if not points:
            return None
        record = points[0]
        paths = {
            "steps": ("steps", "count"),
            "heart-rate": ("heartRate", "beatsPerMinute"),
            "daily-resting-heart-rate": ("dailyRestingHeartRate", "beatsPerMinute"),
            "heart-rate-variability": (
                "heartRateVariability",
                "rootMeanSquareOfSuccessiveDifferencesMilliseconds",
            ),
            "daily-heart-rate-variability": (
                "dailyHeartRateVariability",
                "averageHeartRateVariabilityMilliseconds",
            ),
            "active-zone-minutes": ("activeZoneMinutes", "activeZoneMinutes"),
            "total-calories": ("totalCalories", "caloriesKcal"),
            "distance": ("distance", "distanceMillimeters"),
            "daily-oxygen-saturation": ("dailyOxygenSaturation", "averagePercentage"),
        }
        path = paths.get(data_type)
        if not path:
            return None
        try:
            return float(record[path[0]][path[1]])
        except (KeyError, TypeError, ValueError):
            return None
