# Tech Stack

Our project is a web application written in Python 3.12 using a framework called Reflex (pinned to `reflex==0.9.12`). Reflex compiles our Python UI into React JavaScript components, so the frontend ends up as a React project. To manage our environment variables and secrets, including our Client ID, secret, and redirect URI for the Google Health API OAuth, we use the python-dotenv library (see `.env.example`), which keeps everything in our project in Python. We use google-auth-oauthlib for the OAuth 2.0 (PKCE) flow and the requests library for making and handling API calls to the Google Health API. Tests are written with pytest and live in `code/backend/tests/` and `code/frontend/tests/`.

## Data storage

| Data | Where it lives now | Code |
|---|---|---|
| OAuth tokens | SQLite (`code/backend/healthtrack.db`) | `token_store.py` |
| User profiles | SQLite (`code/backend/healthtrack.db`) | `profile_controller.py` |
| Accounts | JSON file (`data/accounts.json`), SHA-256 password hashes | `account_controller.py` |
| Health alerts | SQLite (`code/backend/healthtrack.db`) | `alerts.py` |

SQLite is our local development database. In Sprint 2 (S2-04, FR-06) we plan to move this data to a cloud-hosted PostgreSQL database. SQLite and PostgreSQL are two separate databases, so this is a migration, not a connection between them. Accounts will move off the JSON file as part of that work. Update this file when the cloud provider is chosen.

## Notifications

Health alerts (US-04) use Reflex's built-in `rx.toast` for in-app messages and the browser's Notifications API (called through `rx.call_script`) for OS-level pop-ups. Neither needs a third-party service or API key. Web Push is a possible later upgrade.

## Planned

- **Docker:** a Dockerfile that installs Python 3.12 and the pinned Reflex version, with a PostgreSQL container for the database (e.g. via Docker Compose).
- **Password hashing:** switch from SHA-256 to bcrypt or argon2 (S3-02, NFR-03).
- **Load testing:** Locust, to verify NFR-04 (10 concurrent users, <1 s response time).
