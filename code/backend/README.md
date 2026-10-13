# Backend services

`telemetry_emulator.py` generates synthetic Fitbit-style telemetry locally for
the dashboard. It supports Low, Medium, and High activity profiles and returns
records grouped by Fitbit data type using the per-type limits in `DATA_TYPES`.
The generated data is illustrative only and is not written to the database.

Run the emulator tests from the repository root with:

```powershell
$env:PYTHONPATH = "code"
python -m unittest discover -s code\backend\tests
```