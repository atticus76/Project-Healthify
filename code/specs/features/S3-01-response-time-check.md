# S3-01: Response-time check (NFR-01)

**Requirements:** NFR-01  ·  **Board item:** NFR-01: Fast, reliable user interface (<1 s UI response times)
**Owner:** Gem811  ·  **Status:** Draft (2026-11-14); implemented before approval at the owner's request

S3-01 on the roadmap covers NFR-01 and NFR-02. This spec covers **NFR-01 only**. NFR-02 (logging, retry with backoff, surfacing failed syncs) is already done for Google syncs in [S1-03](S1-03-scheduled-device-sync.md). Any NFR-02 work beyond that gets its own spec.

## User story
As a member of the Healthify team, I want a script that times every user interaction against an account with a lot of data, so that we can show NFR-01 (<1 s responses) holds, and find the pages that need optimising or preloading before users notice.

This is a developer tool, not a user feature. It has no UI and no route in the app, and it adds no US-xx story, so the Traceability table in `01_Requirements.md` doesn't change.

## Acceptance scenarios
```gherkin
Feature: NFR-01 response-time check

  Scenario: Every interaction meets the budget with a large account
    Given TEST_DATABASE_URL points at the test database
    And a perf user is seeded with a large amount of data
    When I run the response-time check
    Then every measured interaction is reported with its cold, median, p95 and max time
    And every interaction whose p95 is under 1000 ms is marked PASS
    And the script exits with code 0

  Scenario: An interaction is over budget
    Given an interaction whose p95 is 1000 ms or more
    When I run the response-time check
    Then that interaction is marked FAIL
    And the slowest interactions are listed after the table
    And the script exits with code 1

  Scenario: An interaction raises an error
    Given an interaction that raises an exception
    When I run the response-time check
    Then that interaction is marked ERROR with the error message
    And the other interactions are still measured
    And the script exits with code 1

  Scenario: Unsafe or missing test database
    Given TEST_DATABASE_URL is not set, or is the same as DATABASE_URL
    When I run the response-time check
    Then it refuses to run and explains why
    And it writes nothing to any database
    And the script exits with code 2

  Scenario: The perf user is always removed
    Given the check has seeded its perf user
    When the run finishes, whether interactions pass, fail or raise
    Then the perf user and all of its rows are deleted from the test database

  Scenario: Cold loads are reported separately
    Given an interaction has run once untimed to warm the connection pool and caches
    When its result is reported
    Then the cold time is shown on its own
    And the cold time is not counted in the median, p95 or max

  Scenario: The seed is checked before timing
    Given the perf user has been seeded
    When the check verifies the seed
    Then the alert, goal, report, profile and telemetry counts match what was requested
    And if they don't, the check stops with code 2 before timing anything

  Scenario: The check isn't reachable from the web app
    Given the Healthify web app
    When I look for the check in the app's code
    Then no module under code/frontend/healthify imports it

  Scenario: Report refresh reads only the alerts in the report period
    Given a user with alerts from the last 7 days and alerts from earlier
    When the report is generated or refreshed
    Then only the alerts that started inside the report period are read from the database
    And the report lists the same alerts as before this change

  Scenario: The dashboard reads the unread alert count, not the alert list
    Given a user with many alerts, some unread
    When the dashboard loads
    Then the header badge shows the unread count
    And the full alert list is not loaded (the Alerts page still loads it)
```

## Design (decided 2026-11-14)

### Where it lives and how to run it
- `code/scripts/nfr01_response_times.py` is a standalone script. Run it from the repo root with `.venv` active:
  ```
  python code/scripts/nfr01_response_times.py [--runs 20] [--budget-ms 1000] [--alerts 2000] [--goals 25] [--reports 52] [--json results.json]
  ```
- It imports `backend.*` and `healthify.state.*`, never `healthify.healthify`, so no schedulers start and the web app isn't involved.
- It uses the standard library only (`time.perf_counter`, `statistics`, `argparse`, `json`), so there's no new dependency.

### What is measured
The check calls each page's real Reflex event handlers directly, on a headless state tree (`rx.State(_reflex_internal_init=True)`, the pattern from `code/frontend/tests/test_signed_in_user.py`). It uses the real backend and a real database. This measures the server-side work of each interaction, which is where the database round trips to Supabase happen.

| Page | Kind | Interactions (handlers) |
|---|---|---|
| `/login` | action | Sign in (`AuthState.submit`) |
| `/` and `/emulator` | page load | `AlertState.load_unread`, `TelemetryState.load_page` |
| `/profile` | page load, action | `AuthState.load_profile`; `AuthState.save_profile` |
| `/goals` | page load, 1 s poll, actions | `GoalsState.load_page`; `GoalsState.refresh_goals`; `add_goal`, `record_steps`, `delete_goal` |
| `/alerts` | page load, actions | `AlertState.load_page`; `acknowledge`, `acknowledge_all` |
| `/reports` | page load, 1 s poll, action | `ReportsState.load_page`; `ReportsState.refresh_report`; `save_preferences` |
| `/devices` | page load | `DeviceState.load` |
| `/emulator` | 1 s poll, actions | `TelemetryState.auto_refresh`; `enable`, `set_level`, `refresh`, `disable` |

**Not measured:**
- Anything that calls Google or an SMTP server: `start_connect`, `handle_callback`, `sync_now`, `send_test_email`. Their time depends on a third party.
- Setters that only change a field (`set_email` and so on). They don't touch the database.

### How time is measured
- Each interaction runs once untimed first. This is the **cold** run, and it warms ("preloads") the connection pool and caches. The cold time is reported on its own.
- Then it runs `--runs` times (default 20), each timed with `time.perf_counter()`.
- **p95** is the nearest-rank 95th percentile of those timed runs (the 19th of 20 when sorted).
- An interaction **passes when its p95 is under `--budget-ms` (default 1000 ms)**. The median and max are reported for information.
- Any per-run setup runs untimed before each call. For example, it creates the goal that `delete_goal` will delete, and it resets the goal that `record_steps` adds to, because steps add up and would otherwise finish the goal.

### Large account (the seed)
The perf user is named `perf_nfr01_<random hex>`, so it can't collide with a real account. It gets:
- a profile,
- `--alerts` alerts (default **2,000**), one every 30 minutes going back about 6 weeks, with every third one acknowledged,
- `--goals` daily step goals (default **25**), each with its progress row, with about a third of them already complete,
- `--reports` saved reports (default **52**, one per week for a year),
- report preferences (weekly),
- an emulator telemetry snapshot with "High" activity (about 176 KB), with the emulator turned on.

Alerts and reports are bulk-inserted with plain SQL. The check verifies the counts before timing anything.

### Database safety
- The check refuses to run (exit 2) unless `TEST_DATABASE_URL` is set and differs from `DATABASE_URL`, the same rule `code/backend/tests/conftest.py` uses. It then points `DATABASE_URL` at the test database for the whole run.
- `email_alerts.reload_config()` reloads `.env` with `override=True`, which would put the real `DATABASE_URL` back in the middle of a run. The check wraps it so it still runs, and its cost is still timed, and then restores the test URL. After every call the check confirms the database is still the test one, and aborts if it isn't.
- Email sending (`email_alerts.dispatch` and `send`) is replaced with a no-op, so a seeded alert never emails anyone.
- The perf user is deleted in a `finally` block. `ON DELETE CASCADE` removes all of its rows.

### Output and exit codes
- A table with page, kind, interaction, cold, median, p95, max and PASS / FAIL / ERROR. On failure, the three slowest interactions are listed after it. `--json` also writes the results to a file.
- Exit codes:
  - `0`: every interaction passed.
  - `1`: at least one interaction is FAIL or ERROR.
  - `2`: the check couldn't run, because the test database was missing, unsafe or unreachable, or the seed didn't verify.

### Optimisations (decided 2026-11-14)
No baseline could be measured when this was written, because the dev machine had no `TEST_DATABASE_URL`. So only changes that don't alter behaviour and that obviously cut data transferred per interaction were made:

1. **Reports read only the alerts in the period.** `reports.generate_report` used to load every alert the user has and filter in Python. `/reports` refreshes once a second, so that meant 2,000 rows a second for the seeded user. It now calls a new `alerts.list_alerts_since(user_id, since)`, which filters in SQL. The comparison uses `COLLATE "C"` so it matches the old Python string comparison exactly.
2. **The dashboard loads the unread count, not the alert list.** The dashboard's `on_load` called `AlertState.load`, which fetches every alert just to show the header badge. It now calls a new `AlertState.load_unread`, which uses the existing `alerts.unacknowledged_count`. The Alerts page still loads the full list, and new alerts still reload it (`notify`).

**Applied only if a measured run shows a miss.** Each one gets a scenario here before it's built:
- Preload the dashboard's data during sign-in, so the first dashboard paint is quicker.
- Page the alert history on `/alerts` (latest N, then "show more"). This changes S2-03 behaviour.
- An index on `health_alerts (user_id, started_at DESC, id DESC)`.
- Re-reading `.env` in `email_alerts.reload_config` only when the file has changed.

## Measured results

### 2026-11-14, local PostgreSQL 18 (not Supabase)
This run proves the check works end to end. **It is not the NFR-01 result**, because a local database has no network latency. The check ran at the default seed (2,000 alerts, 25 goals, 52 reports) with 20 timed runs. All 22 interactions passed, it exited 0, and no perf user was left behind.

Times are in ms.

| Page | Interaction | Cold | Median | p95 | Max |
|---|---|---:|---:|---:|---:|
| `/alerts` | Acknowledge all alerts | 44 | 45 | 51 | 90 |
| `/emulator` | Auto-refresh telemetry (every 1 s) | 16 | 16 | 26 | 28 |
| `/alerts` | Alerts page load | 23 | 22 | 25 | 26 |
| `/alerts` | Acknowledge one alert | 23 | 22 | 24 | 25 |
| `/emulator` | Change activity level, Refresh telemetry, Turn emulator on | 15–18 | 16–17 | 20–21 | 22–43 |
| `/reports` | Refresh report (every 1 s) | 7 | 7 | 8 | 8 |
| everything else | | ≤ 11 | ≤ 3 | ≤ 4 | ≤ 4 |

The slowest interactions are the ones that read the whole alert history: the Alerts page, and the two acknowledge actions, which reload it. If the Supabase run shows a miss, start with paging the alert history (a conditional optimisation above).

### Supabase test project
*To do (task 5): run `python code/scripts/nfr01_response_times.py --json results.json` with `TEST_DATABASE_URL` set to the healthify-test project, and record the table here with its date.*

## Out of scope
- Browser rendering, React hydration, and websocket transport time. The check measures server-side handler time only.
- Concurrent users and load testing, which is NFR-04 (S3-03, Locust).
- NFR-02 retry and backoff UX (see S1-03).
- Running the check in CI. It needs a reachable test database.

## Open questions
- Should the check run in CI once the team has a shared test database secret?
- Is 2,000 alerts the right "large account"? The seed sizes are flags, so this can change without a code change.

## Tasks
1. ✅ Write this spec, and link it from the roadmap, the requirements (NFR-01 note and Change Log) and the tech stack.
2. ✅ Tests from the scenarios: `code/backend/tests/test_nfr01_response_times.py` and `code/frontend/tests/test_dashboard_alert_count.py`. Watch them fail.
3. ✅ The check: `code/scripts/nfr01_response_times.py`.
4. ✅ Optimisations 1 and 2.
5. ☐ Run the check against the Supabase test project, record the results above, and decide on the conditional optimisations. A local run is already recorded.
