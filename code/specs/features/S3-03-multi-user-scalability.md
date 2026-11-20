# S3-03: Multi-user scalability

**Requirements:** NFR-04, NFR-01  ·  **Board item:** NFR-04: Scalability; handle multiple users simultaneously
**Owner:** atticus76  ·  **Status:** Test written (2026-11-19); waiting on the Supabase run below

## Requirement
NFR-04: the system supports at least 10 concurrent users on a single host while meeting NFR-01's <1 s response time. The roadmap adds: no data leaks between users.

## Acceptance scenario
```gherkin
Scenario: Ten users use the app at the same time
  Given 10 registered users, each with a profile
  And one Healthify server process connected to the database
  When all 10 at once repeat: sign in, open the dashboard, save telemetry,
    add a goal, generate a report, open the report (3 times each)
  Then 95% of those actions finish in under 1 second
  And no action takes 2 seconds or more
  And no action fails
  And every user only ever sees their own account, profile, alerts,
    telemetry, goals, and reports
```

## How it's tested (decided 2026-11-19)

`code/backend/tests/test_concurrency.py`: 10 Python threads, one per user, released at the same moment by a barrier. Each "action" is the set of backend calls one page or button makes (taken from the pages' `on_load` handlers and the state event handlers), timed as one unit because that's what the user waits for.

**Why threads and not Locust or browsers:** Reflex doesn't expose an HTTP endpoint per action. After the page loads, every event goes over one WebSocket. HTTP-based Locust would only time static files, and speaking Reflex's WebSocket protocol is undocumented and changes between versions. Reflex runs synchronous event handlers in a thread pool, so threads calling the same backend functions are close to what the server does. The work is almost all waiting on the database, which releases Python's GIL, so the 10 threads really do overlap.

**What it leaves out:** Reflex's own WebSocket and state-serialization overhead, and the browser. Accepted for this sprint. A Playwright run with 10 browsers could cover that later.

**Isolation checks:** each user's telemetry is tagged with their username, each goal target is unique per user, and each profile age is unique. Every read checks that it got only the caller's rows.

**Pool stats:** the test prints how many connection borrows had to wait and for how long (`psycopg_pool` stats), so a too-small pool shows up as a number, not a guess.

### Where it runs
| Where | Database | What it proves |
|---|---|---|
| CI (GitHub Actions) | local Postgres service | isolation and no errors under concurrency; timing passes trivially |
| A teammate's machine | `TEST_DATABASE_URL` (healthify-test on Supabase) | **the NFR-04 numbers.** Run: `pytest -s code/backend/tests/test_concurrency.py` |

## Findings so far

### 1. The 4-connection pool is too small once there's network delay
Measured locally with a proxy that adds a fixed delay in front of Postgres (Supabase itself not reachable from that environment):

| Round trip | Pool | p95 | Slowest | Result | Borrows that waited |
|---|---|---|---|---|---|
| ~0 ms | 4 | 0.05 s | 0.07 s | pass | 416 / 420 |
| 25 ms | 4 | 1.33 s | 1.33 s | **fail** | 418 / 420 |
| 50 ms | 4 | 2.65 s | 2.69 s | **fail** | 418 / 420 |
| 25 ms | 10 | 0.63 s | 0.92 s | pass | 69 / 420 |
| 50 ms | 10 | 1.29 s | 1.83 s | **fail** | 68 / 420 |

With 4 connections almost every request queues behind the others. A pool of 10 removes most of the queueing. At 50 ms it still fails, because the slow actions make many sequential round trips: generating a report opens about five separate connections, and each borrow also pays one round trip for the pool's health check (`check=ConnectionPool.check_connection`).

**Why the pool is 4:** `DATABASE_URL` uses Supabase's session pooler (port 5432). On the free plan, that caps each project at 15 clients by default, shared by every teammate running the app against it. So 4 per app is right for development. A single deployed server is the only client, so it can use 10.

**Change made:** `POOL_MAX_SIZE` now reads `DB_POOL_MAX_SIZE` from the environment (default 4), so the deployed server, or a load-test run, can raise it without code changes.

### 2. Reports crash on Google-synced telemetry (not a load issue)
`google_health.sync()` saves 6 data types (`SYNC_DATA_TYPES`). `reports.generate_report()` → `telemetry_emulator.summarize_fitbit_data()` expects all 11 emulator types, so it raises `KeyError` for any user whose latest telemetry came from a Google sync. The load test uses emulator data so it can run. This needs its own fix in the reports code (skip missing or empty types in `summarize_fitbit_data`).

## Tasks
- [x] Write the threaded load test with isolation checks and pool stats
- [x] Make the pool size configurable (`DB_POOL_MAX_SIZE`)
- [ ] Run against Supabase healthify-test with pool 4 and pool 10; record the table below
- [ ] Decide the deployed pool size from that run
- [ ] If pool 10 still fails on Supabase: remove the per-borrow health check, or combine the dashboard/report reads into fewer connections
- [ ] Fix finding 2 (whoever owns reports), then switch the test back to Google-shaped data

## Supabase results
_Fill in after running `pytest -s code/backend/tests/test_concurrency.py` (and with `DB_POOL_MAX_SIZE=10`)._

| Date | Pool | p95 | Slowest | Result | Borrows that waited |
|---|---|---|---|---|---|
| | 4 | | | | |
| | 10 | | | | |

## Out of scope
- More than one server process or host (NFR-04 says a single host).
- Browser and WebSocket timing (see "What it leaves out").
- Bcrypt (S3-02) will make sign-in slower on purpose, by roughly 0.1–0.3 s of CPU per login. Rerun this test once it lands.
