# Tech Stack

Our project is a web application written in Python 3.12 using a framework called Reflex (pinned to `reflex==0.9.12`). Reflex compiles our Python UI into React JavaScript components, so the frontend ends up as a React project. To manage our environment variables and secrets, including our Client ID, secret, and redirect URI for the Google Health API OAuth, we use the python-dotenv library (see `.env.example`), which keeps everything in our project in Python. We use google-auth-oauthlib for the OAuth 2.0 (PKCE) flow and the requests library for making and handling API calls to the Google Health API. Tests are written with pytest and live in `code/backend/tests/` and `code/frontend/tests/`.

## Data storage

All app data lives in a cloud-hosted **PostgreSQL** database on **Supabase** (S2-04, FR-06). We use Supabase only as a PostgreSQL server: the app connects with `psycopg` (v3) through a small connection pool (`psycopg_pool`) and plain SQL, with no ORM and no Supabase SDK. The connection string is `DATABASE_URL` in `.env`; tests use a separate `healthify-test` project (`TEST_DATABASE_URL`). The schema is in `code/backend/db/schema.sql`. See [features/S2-04-cloud-data-storage.md](features/S2-04-cloud-data-storage.md).

| Data | Table(s) | Code |
|---|---|---|
| Accounts (username, email, password hash, app settings) | `users` (SHA-256 password hashes until S3-02) | `auth_controller.py` |
| Health profiles | `health_profiles` | `profile_controller.py` |
| Goals and goal progress | `health_goals`, `goal_progress` | `goals.py` |
| Health alerts and alert email address | `health_alerts`, `alert_settings` | `alerts.py` |
| Report preferences and generated reports | `report_preferences`, `health_reports` | `reports.py` |
| Google OAuth tokens and in-progress OAuth requests | `google_connections`, `oauth_pending` (plaintext tokens until S3-02) | `token_store.py` |
| Latest synced telemetry (emulator and Google) | `telemetry_snapshots`; kept in memory and saved at most once a minute, Google syncs right away | `telemetry_store.py` |

The `/account` registration page (US-02, `account_controller.py`) still writes `data/accounts.json` and isn't reachable from the app; whether to remove or rework it is open (S2-04 cleanup C3). SQLite (`healthtrack.db`) and `users.txt` are no longer used.

## Charts

Dashboard charts use Reflex's built-in Recharts components (`rx.recharts`), so they need no extra library.

## Notifications

Health alerts (US-04) use Reflex's built-in `rx.toast` for in-app messages and the browser's Notifications API (called through `rx.call_script`) for OS-level pop-ups. Neither needs a third-party service or API key. Alerts, goal reminders, and reports can also be emailed using Python's built-in `smtplib` (`email_alerts.py`) through any SMTP server. We use a Gmail account with an app password, which is free. SMTP settings live in `.env` (see `.env.example`). Web Push is a possible later upgrade.

## Planned

- **Docker:** a Dockerfile that installs Python 3.12 and the pinned Reflex version, for packaging the app only. The database stays on Supabase; there is no PostgreSQL container, including for tests (S2-04).
- **Password hashing:** switch from SHA-256 to bcrypt (`bcrypt` library) (S3-02, NFR-03).
- **Token encryption:** encrypt OAuth tokens at rest with Fernet from the `cryptography` library (S3-02, NFR-03).
- **Load testing:** Locust, to verify NFR-04 (10 concurrent users, <1 s response time).
