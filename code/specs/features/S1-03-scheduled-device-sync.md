# S1-03: Scheduled device sync and backoff (US-01, scenario 2)

**Requirements:** FR-01, NFR-02  ·  **Board item:** US-01: Device Connection (#1)
**Owner:** atticus76  ·  **Status:** Implemented (2026-11-05); written alongside the code, not approved before it

Scenario 1 (connect through Google, store the token, show "Device Connected", sync) was already done. This spec covers scenario 2.

## Acceptance scenario
```gherkin
Scenario: Scheduled sync fails
  Given my wearable account is connected
  When the system's scheduled sync makes a request to the provider's API and the
    request fails (expired authorization, provider outage, or rate limit reached)
  Then the system logs the failure, displays a "Reconnect Required" or "Sync Failed"
    indicator, and retries on a backoff schedule rather than repeatedly hammering the API
```

## Design (decided 2026-11-05)

### Connection states
| Status | Meaning | Devices page shows | Scheduled sync |
|---|---|---|---|
| `connected` | Last sync worked (or none yet) | "Device Connected" | Every 30 minutes |
| `sync_failed` | Last sync failed for a temporary reason (outage, rate limit, network) | "Sync failed", the reason, and the next retry time | Retries with backoff |
| `reconnect_required` | Access expired or was revoked (Google `invalid_grant`) | "Reconnect required" | **Never retried** until the user reconnects |

A successful sync (scheduled or "Sync Now") returns the connection to `connected` and resets the failure count. Reconnecting starts fresh.

### Schedule and backoff
- A background thread (`google_health.start_scheduler()`, started in `healthify.py` like the goals and reports schedulers) checks every minute for connections whose `next_sync_at` has passed.
- Healthy connections sync every **30 minutes** (`SYNC_EVERY_S`).
- After a failure the next attempt waits **5 minutes, doubling each time it fails in a row (5, 10, 20, 40 minutes...), capped at 6 hours** (`RETRY_FIRST_S`, `RETRY_MAX_S`). If Google sends `Retry-After` on a rate limit (429) and it's longer, that wins.
- One user's failure doesn't stop the others.
- Manual "Sync Now" failures are recorded the same way, so the page and the scheduler agree.

### What a scheduled sync does
The same as "Sync Now": fetch the data types in `SYNC_DATA_TYPES`, save a Google telemetry snapshot, and run the heart-rate alert check. New alerts are saved (shown on the Alerts page and bell) and **emailed**, since nobody may be on the page to see a toast.

### Logging
Every failure is logged with the user and reason (`google_health` logger, `WARNING`); `last_sync_error` keeps the user-facing reason.

### Schema
`google_connections` gets `next_sync_at BIGINT`, `sync_failures INTEGER NOT NULL DEFAULT 0` and `last_sync_error TEXT NOT NULL DEFAULT ''`, added with `ADD COLUMN IF NOT EXISTS` in `schema.sql` so re-running `python -m backend.db.init` upgrades existing databases.

## Out of scope
- Syncing more often, or only while the user is online.
- Showing sync failures anywhere other than the devices page.
