# HealthTrack Roadmap

This roadmap drives **spec-driven development** for HealthTrack. Every feature gets a written spec before any code is written, and the spec stays the source of truth for implementation, tests, and review.

Requirement IDs (FR-xx / NFR-xx) refer to [docs/Reports/01_Requirements.md](../../docs/Reports/01_Requirements.md). Related specs: [mission.md](mission.md), [tech-stack.md](tech-stack.md).

Work is tracked on the [HealthTrack project board](https://github.com/users/atticus76/projects/4/views/1). The **Board item**, **Status**, **Owner**, and **Priority** columns below mirror the board. The **Spec** and **Tests** checkboxes track the spec-driven stages, which the board doesn't track.

> **ID mismatch:** some board items use older FR numbers than the requirements doc. Board FR-07 (cloud storage) = doc **FR-06**, board FR-08 (reporting) = doc **FR-07**, board FR-09 (emulator) = doc **FR-08**. This roadmap uses the requirements-doc IDs; rename the board items to match.

---

## Status Snapshot (from project board, 2026-10-29)

| Board status | Count | Items |
|--------------|:-----:|-------|
| Done | 1 | Connect Fitbit API |
| Testing | 1 | FR-09 Wearable telemetry emulator |
| Code Review | 3 | US-01 Device Connection, US-03 Dashboard, FR-01 Take telemetry data |
| In progress | 6 | US-02 Sign-in screen, US-05 User Profile Parameters, US-06 Goal Setting & Reminders, US-04 Health Abnormality Alerts, FR-07 Cloud data storage, FR-08 Reporting & analytics |
| To Do | 4 | NFR-01, NFR-03, NFR-04, NFR-05 |

**Where each sprint stands:**
- **Sprint 1:** 1 done, 1 in testing, 3 in code review, 1 in progress (sign-in screen).
- **Sprint 2:** all 5 items in progress, running alongside Sprint 1.
- **Sprint 3:** not started; all 4 items are unassigned.

---

## Workflow

Each roadmap item goes through these stages in order:

1. **Specify:** Write `code/specs/features/<feature-id>.md` using the [spec template](#spec-template). Include the user story, Gherkin acceptance scenarios, data contracts, and out-of-scope notes.
2. **Review:** At least one other team member approves the spec in a PR. Nothing gets implemented from an unmerged spec.
3. **Plan:** Break the spec into tasks (GitHub issues using `.github/ISSUE_TEMPLATE/user-story.md`) and link each issue back to the spec.
4. **Test first:** Turn each acceptance scenario into a failing test under `code/backend/tests/` or `code/frontend/tests/`.
5. **Implement:** Write code until the tests pass. If the spec turns out to be wrong, update the spec in the same PR and say why.
6. **Verify:** Demo against the acceptance scenarios, then tick the item off below.

**Definition of done (every item):** spec merged · tests written from the spec and passing · code reviewed and merged to `main` · acceptance scenarios demoed · requirement traceability updated.

---

## Sprint 1: Device Data Foundation

**Goal:** A user can sign in, connect a Fitbit (real or emulated), pull telemetry, and see it on a dashboard.

| ID | Feature | Requirements | Board item | Status | Owner | Priority | Spec | Tests |
|----|---------|--------------|------------|--------|-------|:--------:|:----:|:-----:|
| S1-01 | Fitbit emulator | FR-08, NFR-02 | FR-09 [Added after GenAI]: Wearable telemetry emulator | Testing | Gem811 | — | ☐ | ☐ |
| S1-02 | Fitbit API connection | FR-01, NFR-02 | Connect Fitbit API | ✅ Done | atticus76 | — | ☐ | ☐ |
| S1-03 | Device connection | FR-01, FR-08 | US-01: Device Connection (sub-issues 1/1) | Code Review | atticus76 | P0 | ☐ | ☐ |
| S1-04 | Telemetry ingestion | FR-01 | FR-01: Take telemetry data from things | Code Review | atticus76 | — | ☐ | ☐ |
| S1-05 | Dashboard | FR-07, FR-03 | US-03: Dashboard | Code Review | Mohammad1789 | P0 | ☐ | ☐ |
| S1-06 | Sign-in screen | FR-05 | US-02: Sign-in screen | In progress | dilo427 | P1 | ☐ | ☐ |

### S1-01: Fitbit emulator
- Generates Fitbit-shaped telemetry (steps, heart rate, resting HR, HRV, sleep, exercise, active zone minutes, calories, distance, SpO2) with the same JSON shape as `data/samples/`.
- Low / Medium / High activity profiles.
- Emulated data is clearly labelled as simulated everywhere it appears (NFR-02).
- **Spec must define:** output schema per data type, value ranges per profile, record limits, and how the emulator is chosen over the live API.

### S1-02: Fitbit API connection
- OAuth 2.0 (PKCE) authorization against the provider API (Google Health API, which replaces the deprecated Fitbit Web API).
- Token storage, refresh before expiry, and a "reconnect required" state when refresh fails.
- **Spec must define:** scopes requested, token lifecycle, error states, and retry/backoff behaviour (NFR-02).

### S1-03: Device connection
- Devices page: connect, disconnect, and view the connection status of a real or emulated Fitbit.
- Falls back to the emulator when the live connection is unavailable.
- **Spec must define:** connection states (disconnected / connecting / connected / reconnect required / emulated), the transitions between them, and what the UI shows for each.

### S1-04: Telemetry ingestion
- Pulls telemetry from the connected source (API or emulator) and normalises it into one internal model.
- Logs failed syncs and shows them to the user.
- **Spec must define:** the internal telemetry model, sync trigger (manual / on load / scheduled), page sizes per data type, and deduplication rules.

### S1-05: Dashboard
- Cards for the latest values of each metric, with a source label (live vs. emulated).
- Shows the medical disclaimer (FR-03).
- **Spec must define:** which metrics appear, layout, empty/loading/error states, and the refresh behaviour.

### S1-06: Sign-in screen
- Email + password sign-in with an error message on invalid credentials; failed attempts are tracked.
- Redirects to the dashboard on success.
- **Spec must define:** validation rules, session handling, lockout policy (if any), and the scenarios from the README user story.

**Sprint 1 exit criteria:** a new user can sign in → connect a device (or choose the emulator) → sync → see their telemetry on the dashboard, with every step covered by passing acceptance tests.

---

## Sprint 2: Personalisation & Insights

**Goal:** Make the data personal. Profiles, goals, alerts, cloud persistence, and reports.

| ID | Feature | Requirements | Board item | Status | Owner | Priority | Spec | Tests |
|----|---------|--------------|------------|--------|-------|:--------:|:----:|:-----:|
| S2-01 | User profile parameters | FR-04 | US-05: User Profile Parameters | In progress | Mohammad1789 | P1 | ☐ | ☐ |
| S2-02 | Goal setting & reminders | FR-09 | US-06: Goal Setting & Reminders | In progress | Mohammad1789 | P2 | ☐ | ☐ |
| S2-03 | Health abnormality alerts | FR-02, FR-03 | US-04: Health Abnormality Alerts | In progress | Gem811 | P2 | ☐ | ☐ |
| S2-04 | Cloud data storage & retrieval | FR-06 | FR-07: Data Storage and Retrieval for the user (Cloud) | In progress | atticus76 | — | ☐ | ☐ |
| S2-05 | Reporting & analytics | FR-07 | FR-08: Reporting and Analytics for the user (Daily or weekly recap) | In progress | Mohammad1789, atticus76 | — | ☐ | ☐ |

### S2-01: User profile parameters
- User enters and edits gender, age, height, and weight; these feed baseline calculations.
- **Spec must define:** fields, units, validation ranges, required vs. optional fields, and which metrics use each parameter.

### S2-02: Goal setting & reminders
- Create, edit, and delete goals (e.g. daily steps, sleep hours, active minutes) and track progress against telemetry.
- In-app reminders when a goal is at risk.
- **Spec must define:** supported goal types, progress calculation, reminder triggers and frequency, and how reminders are dismissed.

### S2-03: Health abnormality alerts
- In-app alert when a metric deviates from the user's personal baseline or a general reference range.
- Every alert carries the "not medical advice" disclaimer (FR-03).
- **Spec must define:** which metrics are monitored, thresholds and baseline window for each (open decision in the requirements doc), alert severity, and de-duplication so the same alert doesn't repeat.

### S2-04: Cloud data storage & retrieval
- Move user, profile, goal, and telemetry data from local SQLite to a cloud database.
- Data is scoped per user and survives sign-out and switching devices.
- **Spec must define:** cloud provider and DB choice (update [tech-stack.md](tech-stack.md)), schema, migration from the local DB, and retrieval APIs.

### S2-05: Reporting & analytics
- Daily and weekly recaps with charts for short- and long-term trends.
- **Spec must define:** report contents per metric, aggregation rules (avg/min/max/total), chart types, and date-range controls.

**Sprint 2 exit criteria:** a user's profile, goals, alerts, and history persist in the cloud and are reflected in personalised reports and alerts.

---

## Sprint 3: Quality, Security & Scale

**Goal:** Harden the app. Make it fast, secure, able to handle multiple users, and aware of day-to-day changes.

| ID | Feature | Requirements | Board item | Status | Owner | Priority | Spec | Tests |
|----|---------|--------------|------------|--------|-------|:--------:|:----:|:-----:|
| S3-01 | Fast & reliable UI | NFR-01, NFR-02 | NFR-01: Fast, reliable user interface (<1 s UI response times) | To Do | Unassigned | — | ☐ | ☐ |
| S3-02 | Encryption of personal & account data | NFR-03, FR-05 | NFR-03: Personal health and account information is encrypted | To Do | Unassigned | — | ☐ | ☐ |
| S3-03 | Multi-user scalability | NFR-04 | NFR-04: Scalability; handle multiple users simultaneously | To Do | Unassigned | — | ☐ | ☐ |
| S3-04 | Telemetry caching for day-to-day change | NFR-05 | NFR-05: Cache user data to measure day-to-day changes in telemetry | To Do | Unassigned | — | ☐ | ☐ |

### S3-01: Fast & reliable UI
- Page interactions respond in under 1 second (NFR-01).
- Third-party failures are handled gracefully: logged, retried with exponential backoff, and shown to the user (NFR-02).
- **Spec must define:** measured interactions, performance budget per page, how response time is measured, and the error/retry UX.

### S3-02: Encryption of personal & account data
- Passwords hashed with a modern algorithm (e.g. bcrypt/argon2).
- HTTPS in transit; OAuth refresh tokens and personal health data encrypted at rest (resolves the TODO in `token_store.py`).
- **Spec must define:** what "encrypted" means for each data class (open decision in the requirements doc), algorithms, key management, and how existing plaintext data is migrated.

### S3-03: Multi-user scalability
- At least 10 concurrent users on a single host while keeping response times under 1 s (NFR-04).
- No data leaks between users.
- **Spec must define:** load test scenarios (e.g. Locust), target throughput, pass/fail thresholds, and per-user isolation checks.

### S3-04: Telemetry caching for day-to-day change
- Cache daily telemetry snapshots so the app can compute and show day-over-day changes without re-fetching from the provider.
- **Spec must define:** cache contents and granularity, invalidation/refresh rules, retention period, and how deltas appear on the dashboard and in reports. (NFR-05 is still marked "under review"; settle its scope in this spec.)

**Sprint 3 exit criteria:** load test passes at 10 concurrent users under 1 s, sensitive data is encrypted at rest and in transit, and day-over-day changes appear from cached data.

---

## Spec Template

Copy into `code/specs/features/<feature-id>.md`:

```markdown
# <ID>: <Feature name>

**Requirements:** FR-xx, NFR-xx
**Owner:** <name>  ·  **Status:** Draft | In review | Approved | Implemented

## User story
As a <user>, I want <goal> so that <value>.

## Acceptance scenarios
Feature: <Feature name>
  Scenario: <Successful scenario>
    Given ...
    When ...
    Then ...

  Scenario: <Failure / boundary scenario>
    Given ...
    When ...
    Then ...

## Design
- Data model / contracts:
- UI states:
- Errors & edge cases:

## Out of scope

## Open questions
```

---

## Dependencies

```
Sprint 1                     Sprint 2                         Sprint 3
S1-01 Emulator ─┐
S1-02 API ──────┼─► S1-04 Telemetry ─► S1-05 Dashboard ─► S2-05 Reports ─► S3-04 Caching
S1-03 Device ───┘          │                 │
S1-06 Sign-in ─────────────┼──► S2-04 Cloud storage ──────► S3-02 Encryption
                           │         │                     S3-03 Scalability
S2-01 Profile ─────────────┴─► S2-03 Alerts                S3-01 Fast UI (all pages)
S2-02 Goals ◄── S1-04
```
