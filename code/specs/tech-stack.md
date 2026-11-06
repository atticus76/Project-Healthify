# Tech Stack

Our project is a web application written in Python 3.12 using a framework called Reflex (pinned to `reflex==0.9.12`). Reflex compiles our Python UI into React JavaScript components, so the frontend ends up as a React project. To manage our environment variables and secrets, including our Client ID, secret, and redirect URI for the Google Health API OAuth, we use the python-dotenv library (see `.env.example`), which keeps everything in our project in Python. We use google-auth-oauthlib for the OAuth 2.0 (PKCE) flow and the requests library for making and handling API calls to the Google Health API. Tests are written with pytest and live in `code/backend/tests/` and `code/frontend/tests/`.

## Data storage

| Data | Where it lives now | Code |
|---|---|---|
| Accounts used by the login page (username, email, password hash, theme, profile) | JSON in `code/backend/users.txt`, SHA-256 password hashes | `auth_controller.py` |
| Accounts from the `/account` registration page (US-02) | JSON in `data/accounts.json`, SHA-256 password hashes | `account_controller.py` |
| User profiles | SQLite (`code/backend/healthtrack.db`) | `profile_controller.py` |
| Goals and goal progress | SQLite (`code/backend/healthtrack.db`) | `goals.py` |
| Health alerts and alert email address | SQLite (`code/backend/healthtrack.db`) | `alerts.py` |
| Report preferences and generated reports | SQLite (`code/backend/healthtrack.db`) | `reports.py` |
| OAuth tokens and in-progress OAuth requests | SQLite (`code/backend/healthtrack.db`) | `token_store.py` |
| Latest synced telemetry | In memory only (lost when the server restarts) | `telemetry_emulator.py` |

SQLite is our local development database. In Sprint 2 (S2-04, FR-06) we are moving this data to a cloud-hosted PostgreSQL database on **Supabase**. SQLite and PostgreSQL are two separate databases, so this is a migration, not a connection between them. We use Supabase only as a PostgreSQL server: the app connects with `psycopg` and plain SQL, with no ORM and no Supabase SDK. Both account files move into one `users` table as part of that work. See [features/S2-04-cloud-data-storage.md](features/S2-04-cloud-data-storage.md) (draft).

## Charts

Dashboard charts use Reflex's built-in Recharts components (`rx.recharts`), so they need no extra library.

## Notifications

Health alerts (US-04) use Reflex's built-in `rx.toast` for in-app messages and the browser's Notifications API (called through `rx.call_script`) for OS-level pop-ups. Neither needs a third-party service or API key. Alerts, goal reminders, and reports can also be emailed using Python's built-in `smtplib` (`email_alerts.py`) through any SMTP server. We use a Gmail account with an app password, which is free. SMTP settings live in `.env` (see `.env.example`). Web Push is a possible later upgrade.

## Planned

- **Docker:** a Dockerfile that installs Python 3.12 and the pinned Reflex version, with a PostgreSQL container for the database (e.g. via Docker Compose).
- **Password hashing:** switch from SHA-256 to bcrypt (`bcrypt` library) (S3-02, NFR-03).
- **Token encryption:** encrypt OAuth tokens at rest with Fernet from the `cryptography` library (S3-02, NFR-03).
- **Load testing:** Locust, to verify NFR-04 (10 concurrent users, <1 s response time).
