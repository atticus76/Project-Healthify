# Backend services

All persistent data lives in a PostgreSQL database on Supabase (S2-04). Every
module talks to it through one connection pool:

```python
from backend.db import connect

with connect("load goals") as conn:  # one transaction; rows come back as dicts
    rows = conn.execute("SELECT * FROM health_goals WHERE user_id = %s", (user,)).fetchall()
```

- `db/schema.sql` has every table; `python -m backend.db.init` (from `code/`) creates any missing ones.
- Failures raise `backend.db.DatabaseError`, whose message is the one users see; the app shows it as a toast.
- Every `user_id` column must be an existing account (`users.username`); deleting an account deletes its data.

`telemetry_emulator.py` generates synthetic Fitbit-style telemetry locally for
the dashboard. It supports Low, Medium, and High activity profiles and returns
records grouped by Fitbit data type using the per-type limits in `DATA_TYPES`.
The generated data is illustrative only. The latest telemetry (emulator or a
Google sync) is kept in memory by `telemetry_store.py` and saved to the database
at most once a minute.

Run the tests from the repository root with pytest (the database tests need
`TEST_DATABASE_URL` in `.env`; see the root README):

```powershell
pytest
```
