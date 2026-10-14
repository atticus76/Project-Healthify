import reflex as rx

class TelemetryState(rx.State):
    level: str = "Medium"
    enabled: bool = False
    show_payload: bool = False
    summaries: list[str] = []
    payload_json: str = ""

    def set_level(self, value: str):
        if value not in PROFILES:
            raise ValueError(f"Unknown simulation level: {value}")
        self.level = value
        if self.enabled:
            self._generate_data()

    def enable(self):
        self._generate_data()
        self.enabled = True

    def refresh(self):
        if not self.enabled:
            raise RuntimeError("Enable the telemetry emulator before refreshing.")
        self._generate_data()

    def disable(self):
        self.enabled = False
        self.show_payload = False
        self.summaries = []
        self.payload_json = ""

    def toggle_payload(self):
        self.show_payload = not self.show_payload

    def _generate_data(self):
        data = generate_fitbit_data(self.level)
        self.summaries = summarize_fitbit_data(data)
        self.payload_json = json.dumps(data, indent=2)