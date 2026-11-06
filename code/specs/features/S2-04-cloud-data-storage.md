# S2-04: Cloud Data Storage & Retrieval

**Requirements:** FR-06, NFR-02, NFR-04 (partial)  ·  **Board item:** FR-07: Data Storage and Retrieval for the user (Cloud) (#8)
**Owner:** atticus76  ·  **Status:** Draft

## User story
As a registered user, I want my account, profile, goals, alerts, reports, and device connection stored in the cloud, so that my data is still there after I sign out, the app restarts, or I use Healthify from another computer.

## Acceptance scenarios
```gherkin
Feature: Cloud data storage and retrieval

  Scenario: Data survives an app restart
    Given a registered user has saved a profile and a daily steps goal
    When the Healthify server is stopped and started again
    And the user signs in
    Then their profile and goal are shown exactly as they saved them

  Scenario: Data follows the user to another computer
    Given a registered user created an account and a goal on one teammate's machine
    When they sign in on a different machine running Healthify with the same DATABASE_URL
    Then they see the same account, profile, goals, alerts, and reports

  Scenario: Two users at the same time only see their own data
    Given user "alice" is signed in in one browser
    And user "bob" is signed in in another browser
    When each of them opens the Goals, Alerts, and Reports pages
    Then each sees only their own records
    And neither session changes who the other is signed in as

  Scenario: Registering and signing in use the cloud users table
    Given no account named "alice" exists
    When "alice" registers with a valid email and password
    Then a row for "alice" is stored in the users table
    And she can sign in with her username or her email
    And registering "alice" again is rejected with "That username is already in use."

  Scenario: Database is unreachable
    Given the user is signed in
    When a page tries to read or save data and the database cannot be reached
    Then the page shows "Couldn't reach the database. Try again in a moment."
    And the error is logged with the operation that failed
    And nothing is written to a local file instead

  Scenario: DATABASE_URL is missing
    Given DATABASE_URL is not set in .env
    When the app starts
    Then it stops with a message that says DATABASE_URL is required and points to .env.example
```

## Design

### Provider: Supabase (decided 2026-11-05)
We compared Supabase, Neon, Firestore, Turso, and Google Cloud SQL.

| Option | Why / why not |
|---|---|
| **Supabase (chosen)** | Hosted PostgreSQL. Most tutorials and community answers, and a table editor teammates can use to check their data without writing SQL. Free plan pauses a project after about a week with no activity. |
| Neon | Also hosted PostgreSQL, wakes up on its own after idling. Fewer extras and a smaller community. Close second; switching later only changes `DATABASE_URL`. |
| Firestore | Document database, not SQL. Every query and the data model would be rewritten. |
| Turso | SQLite in the cloud, so the smallest code change, but a less mature Python client and less transferable learning. |
| Cloud SQL | Billed by the hour even when idle. |

**Rule: we use Supabase only as a PostgreSQL server.** The app connects with `psycopg` (v3) and plain SQL. We do **not** use the `supabase-py` SDK, Supabase Auth, Supabase Storage, or the auto-generated REST API. This keeps the code portable to any PostgreSQL host and keeps the SQL visible.

**No ORM (decided 2026-11-05).** Milestone 1 planned `Reflex[db]` (SQLModel for table schemas, Alembic for migrations). No code ever used it; every module was written with raw `sqlite3` and plain SQL. Porting that SQL to psycopg is a much smaller change than rewriting every query as SQLModel, and it keeps the SQL visible while we learn it. The cost is that schema changes are made by hand in `schema.sql` instead of by Alembic migrations. Revisit if the schema starts changing often.

**Pausing:** if the project has been paused, the app will get connection errors (see "Database is unreachable"). Restore it from the Supabase dashboard. Whoever runs a demo checks the dashboard first.

### Connecting
- One shared module, `code/backend/db.py`, with a `connect()` context manager. It reads `DATABASE_URL` from `.env` (python-dotenv), opens a `psycopg` connection with `row_factory=dict_row`, commits on success, rolls back on error, and closes the connection. It replaces the five separate `DATABASE_PATH` / `_connect()` copies.
- Use Supabase's **Session pooler** connection string (Project → Connect). The direct connection string is IPv6-only on the free plan and fails on many home and campus networks. Avoid the Transaction pooler (port 6543), because it doesn't support the prepared statements psycopg creates automatically.
- New dependency: `psycopg[binary]` in `code/requirements.txt`. Add `DATABASE_URL=` to `.env.example`. The real value is shared privately inside the team and never committed.
- A connection per call, same as today. Opening a remote connection is slower than opening a local SQLite file; if pages get close to the 1 s budget (NFR-01), switch to `psycopg_pool` in S3-01.

### Schema
All `CREATE TABLE` statements move into one file, `code/backend/db/schema.sql`, which can be re-run safely (`CREATE TABLE IF NOT EXISTS`). A small script, `python -m backend.db.init`, runs it. Modules no longer create or alter tables at import time, and the ad-hoc `ALTER TABLE` / `PRAGMA table_info` / `sqlite_master` migration code in `goals.py` is deleted because the new database starts from the final schema.

**Straight port first:** column types stay as they are today (ISO-8601 `TEXT` timestamps, `INTEGER` 0/1 flags) so the Python code that reads them doesn't change. Converting to `TIMESTAMPTZ` and `BOOLEAN` is a follow-up (see Open questions).

| Table | Columns (changes from today in **bold**) |
|---|---|
| **`users`** (new; replaces `users.txt` and `data/accounts.json`) | `username TEXT PRIMARY KEY`, `email TEXT UNIQUE` (NULL when not given), `password_hash TEXT NOT NULL`, `app_state JSONB NOT NULL DEFAULT '{}'` (theme, telemetry_enabled, device_name), `created_at TEXT NOT NULL` |
| `health_profiles` | **`user_id`** (renamed from `profile_id`) `TEXT PRIMARY KEY`, gender, age, weight_lb, baseline_weight_lb, estimated_daily_calories, updated_at |
| `health_goals` | `id` **`BIGINT GENERATED ALWAYS AS IDENTITY`** `PRIMARY KEY`, user_id, goal_type, target, is_daily, reminders_enabled, reminder_25/50/75_enabled, deadline_at, created_at |
| `goal_progress` | goal_id `PRIMARY KEY` **`REFERENCES health_goals(id) ON DELETE CASCADE`**, steps, status, prompt, milestones_sent, reminders_sent |
| `health_alerts` | `id` **identity**, user_id, kind, severity, title, message, started_at, ended_at, peak_bpm, created_at, acknowledged, `UNIQUE (user_id, kind, started_at)` |
| `alert_settings` | user_id `PRIMARY KEY`, email |
| `report_preferences` | user_id `PRIMARY KEY`, frequency, email, updated_at |
| `health_reports` | `id` **identity**, user_id, period_start, period_end, generated_at, content, delivery_status, delivery_error |
| `oauth_pending` | state `PRIMARY KEY`, code_verifier, user_id, created_at |
| `google_connections` | user_id `PRIMARY KEY`, email, access_token, refresh_token, expires_at, scope, status, device_name, connected_at, last_sync_at |
| **`telemetry_snapshots`** (new; today this is an in-memory dict in `telemetry_emulator.py` that's lost on restart) | `user_id TEXT`, `source TEXT` (`google` or `emulator`), `data JSONB NOT NULL`, `synced_at TEXT NOT NULL`, `PRIMARY KEY (user_id, source)`. Latest sync only; history is S3-04. The UML class diagram's `TelemetryRecord` (one row per data point) is deferred to S3-04 along with history. |

Every `user_id` column is `TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE`.

**Row Level Security:** enable RLS on every table and add **no** policies. That shuts off Supabase's auto-generated public REST API for our tables. Our server connects as the `postgres` role, which owns the tables and so isn't affected. (Verify this when setting up.)

### SQLite → PostgreSQL changes in the code
| SQLite (today) | PostgreSQL |
|---|---|
| `?` placeholders | `%s` |
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY` |
| `INSERT OR IGNORE` | `INSERT ... ON CONFLICT DO NOTHING` |
| `cursor.lastrowid` | `INSERT ... RETURNING id` |
| `sqlite3.Row` (`row["x"]` or `row[0]`) | `dict_row` (`row["x"]` only; fix `row[0]` in `alerts.py`) |
| Writing a dict to a JSON column | wrap it in `psycopg.types.json.Jsonb(...)` |
| `ON CONFLICT(x) DO UPDATE SET y = excluded.y` | same syntax, no change |

### Signed-in user is per browser session
Today `auth_controller._active_user` is a module-level global, so every browser using the same server shares one signed-in user. Per-session state is also what US-03 Scenario 2 ("Session Expired, please re-login") needs; session expiry itself stays with US-03. It moves into Reflex state: `AuthState.username` is the source of truth, and other state classes get it with `(await self.get_state(AuthState)).username` instead of `auth_controller.get_active_user()`. `set_active_user` / `get_active_user` / `clear_active_user` are deleted. Backend functions already take `user_id` as a parameter, so only the frontend state classes change.

### Errors & edge cases
- Connection or query failures raise one app-level `DatabaseError` from `db.py`. State handlers catch it, show the message from the scenario, and log it (NFR-02). No silent fallback to SQLite or files, which would split a user's data between two places.
- Email is optional at registration and stored as NULL when blank (an empty string would collide with the `UNIQUE` constraint).
- Usernames can't be changed (there's no rename feature), which is what makes `username` safe as the primary key.

### Tests
- Tests that touch the database use `TEST_DATABASE_URL`, pointing at a separate Supabase project (`healthify-test`), never the shared dev database. They create the schema, then truncate tables before each test. If `TEST_DATABASE_URL` isn't set, those tests are skipped with a message instead of failing.
- Existing tests that patch `DATABASE_PATH` to a temp SQLite file (e.g. `test_goal_email.py`) are updated to use the test database.
- New tests: one per acceptance scenario. The two-users scenario is tested at the state level with two separate `AuthState` instances.

## Cleanup bundled with this work
Found while reviewing the code on 2026-11-05.

| # | Problem | Fix | In this spec? |
|---|---|---|---|
| C1 | `code/backend/users.txt` (accounts and password hashes) is committed to the public repo; `.gitignore` covers `*.db` but not this file. | Add it to `.gitignore` and `git rm --cached` it. Tell the team not to reuse any real password they typed into a test account. Rewriting git history to remove it is optional. | ✅ Yes |
| C2 | The signed-in user is one global variable shared by every session. | See "Signed-in user is per browser session". | ✅ Yes |
| C3 | Two account systems: the login page uses `auth_controller.py` → `users.txt`, while `/account` (US-02) uses `account_controller.py` → `data/accounts.json`. Accounts made on `/account` can't sign in. | Both move to the `users` table through one module. Decide with dilo427 whether `/account` is removed or reworked to call the same functions. | ✅ Yes |
| C4 | Gender, age, and weight are stored twice: in `users.txt` (`profile`) and in `health_profiles`. | `health_profiles` is the only copy; `auth_controller.save_profile` and the `profile` key are removed. | ✅ Yes |
| C5 | `code/backend/db/` and `code/backend/src/` are empty. | `db/` holds `schema.sql` and `init.py`; delete `src/`. | ✅ Yes |
| C6 | Board item #8 was closed as completed on 2026-11-05 but no cloud storage exists yet. | Reopen #8 and move it back to In progress. | ✅ Yes (board) |
| C7 | Passwords use unsalted SHA-256. | Switch to bcrypt (`bcrypt` library, as planned in Milestone 1). Cap password length at 72 bytes, since bcrypt only uses the first 72. | ❌ S3-02 |
| C8 | OAuth access and refresh tokens are stored in plain text, and will now sit in a hosted database. | Encrypt at rest with reversible encryption (Fernet from the `cryptography` library, key in `.env`). Hashing won't work here because the app needs the real token to call Google. | ❌ S3-02 |

## Tasks
1. Create the Supabase project under a team-owned account and invite all four members. Create `healthify-test` too.
2. Write `db/schema.sql`, `db/init.py`, and `db.py`; add `psycopg[binary]` and `DATABASE_URL` / `TEST_DATABASE_URL` to `requirements.txt` and `.env.example`.
3. Write failing tests from the scenarios.
4. Port `token_store`, `profile_controller`, `alerts`, `goals`, `reports` (one PR each is fine).
5. Move accounts to the `users` table and merge the two account systems (C3, C4).
6. Move the signed-in user into `AuthState` (C2).
7. Persist telemetry snapshots.
8. Cleanup C1, C5, C6. Update `tech-stack.md` (storage table, provider choice) and the README setup steps.

## Out of scope
- Moving existing local data. Everything in `healthtrack.db` and `users.txt` is test data; teammates re-register.
- Supabase Auth, Storage, Realtime, and the `supabase-py` SDK (see the provider rule above).
- Encryption and stronger password hashing (S3-02), connection pooling (S3-01), load testing (S3-03), telemetry history and day-over-day caching (S3-04).

## Open questions
- Convert `TEXT` timestamps to `TIMESTAMPTZ` and `INTEGER` flags to `BOOLEAN` now, or as a follow-up after the straight port works?
- Is one shared test project enough when four people run tests at the same time, or should tests use a local PostgreSQL container instead (tech-stack.md already plans a Docker Compose setup)?
- Should `username` stay the primary key, or should `users` get a numeric `id` that everything else references? (Simpler now vs. allowing username changes later.)
- Who owns the Supabase account so it doesn't disappear when one person leaves the class?
