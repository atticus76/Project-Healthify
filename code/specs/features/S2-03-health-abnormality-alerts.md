# S2-03: Health Abnormality Alerts

**Requirements:** FR-02, FR-03, NFR-02  ·  **User story:** US-04
**Owner:** Gem811  ·  **Status:** In review

## User story
As a user, I want to receive immediate alerts when my wearable metrics show sudden abnormalities, so that I can take prompt medical or preventative action.

## Acceptance scenarios
```gherkin
Feature: Health abnormality alerts

  Scenario: Positive flow: sustained high heart rate
    Given the user has active telemetry monitoring enabled on their wearable device
    When the wearable detects a resting heart rate exceeding 130 BPM for over 5 minutes
    Then the system sends an urgent alert about an abnormal heart rate spike
    And the alert appears as an in-app toast, in the header badge, and on the Alerts page
    And, if the user allowed browser notifications, as a browser/OS notification
    And, if an alert email address is saved, as an email to that address

  Scenario: Negative/edge case: spike during a disconnection
    Given the user's wearable loses connection while transferring telemetry data
    When an abnormal metric spike occurs during the disconnection period
    Then the system logs the data gap upon reconnection
    And prompts the user to check their device placement
    And does not raise a heart-rate alarm
```

Tests: `code/backend/tests/test_alerts.py` (detection, storage, emulator scenarios), `code/backend/tests/test_email_alerts.py` (email, with SMTP mocked) and `code/frontend/tests/test_alert_delivery.py` (delivery events).

## Design

### Alert delivery (decided 2026-10-30)
We compared six channels: in-app, the browser Notifications API, Web Push, Firebase/OneSignal, email, and ntfy/Pushover. SMS was already out of scope. We chose:

| Channel | When it reaches the user | Cost |
|---|---|---|
| **In-app** (Reflex `rx.toast`, header bell badge, `/alerts` page) | Whenever the app is open. This is the system of record. | Free |
| **Browser Notifications API** (`new Notification(...)` via `rx.call_script`) | OS pop-up while a Healthify tab is open, even in the background; only after the user clicks "Enable browser notifications" | Free |
| **Email** (`smtplib` over SMTP + STARTTLS, `code/backend/email_alerts.py`), added 2026-11-02 | Any time, even with the app closed, once the next sync finds the alert | Free with a Gmail app password (about 500 emails/day) |

**Stretch:** Web Push (service worker + VAPID + `pywebpush`) would also deliver when the tab is closed. Only the delivery code (`notify()` in `state/alerts.py`) would change.

### Email alerts
- **Server setup (`.env`):** `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD` (Gmail app password), optional `SMTP_FROM`, `ALERT_EMAIL_TO` (default recipient), `HEALTHIFY_URL` (link in the email). Email is off unless the username and password are set.
- **Recipient:** saved on the `/alerts` page (table `alert_settings`). If nothing has been saved, `ALERT_EMAIL_TO` is used. Choosing *Turn off* saves an empty address, which turns email off even if `ALERT_EMAIL_TO` is set.
- **What's sent:** one email per new alert. Urgent alerts get the subject prefix `URGENT:` and high-priority headers. The body has the alert text, a link to `/alerts`, and the disclaimer (FR-03).
- **Sending:** on a background thread with a 15 s timeout, so a slow mail server never blocks the page. Failures are logged and never stop the in-app or browser alert. *Send test email* on `/alerts` sends right away and shows the result.
- **Privacy (NFR-03):** emails travel encrypted to the mail server (STARTTLS) but then sit in an ordinary inbox. The body is kept to the alert summary.

### Detection rules (`code/backend/alerts.py`)
| Rule | Value | Constant |
|---|---|---|
| High heart rate | strictly above 130 BPM | `HIGH_HEART_RATE_BPM` |
| Sustained | first to last high sample spans ≥ 5 min with no reading at or below threshold | `SUSTAINED_FOR` |
| At rest | samples inside an `exercise` session are ignored | — |
| Data gap | two consecutive heart-rate samples more than 2 min apart | `MAX_SAMPLE_GAP` |

- A high-heart-rate run that crosses a data gap is **cut at the gap**, so a spike we only partly saw never becomes an alarm (Scenario 2).
- Severity is `urgent` for high heart rate and `info` for data gaps.

### When checks run
After every telemetry load: emulator Enable / Refresh / level or scenario change, and the Google Health sync on `/devices` (heart-rate `pageSize` raised from 1 to 50). Checks only happen as often as the app syncs, so "immediate" means "on the next sync".

### Data model
SQLite table `health_alerts` in `healthtrack.db`: `id, user_id, kind, severity, title, message, started_at, ended_at, peak_bpm, created_at, acknowledged`.
- **De-duplication:** `UNIQUE(user_id, kind, started_at)`. Re-syncing overlapping data doesn't alert twice.
- Alerts are per user (currently `DEMO_USER_ID` until FR-05 accounts land).

### UI states
- `/alerts`: disclaimer callout (FR-03); notification permission state (default → button, granted, denied, unsupported); alert history newest first with *Mark as seen* / *Mark all as seen*; an empty state that links to the emulator.
- Header: bell icon linking to `/alerts`, with a red count badge when there are unseen alerts.
- `/emulator`: an **Alert scenario** selector with Normal readings, Heart-rate spike, and Connection drop.

### Errors & edge cases
- Malformed data points are skipped, not fatal.
- Browser without the Notifications API, or permission denied: in-app delivery still works and the page explains why pop-ups won't appear.
- Every alert, including browser notifications, carries the "not a medical device" disclaimer (FR-03).

## Out of scope
- SMS and Web Push delivery (see above)
- Metrics other than heart rate (HRV, SpO2, sleep). FR-02 thresholds for those are still an open decision.
- Personal-baseline thresholds; this version uses the fixed 130 BPM reference
- Contacting emergency services (FR-03)

## Open questions
- Real Google Health heart-rate sampling can be sparser or denser than the emulator's 30 s. Check whether 50 samples cover 5 minutes, and whether 2 min is the right gap tolerance for real devices.
- Should the 130 BPM threshold become age- or baseline-adjusted once profiles (S2-01) are richer?
- Should the app sync on a schedule (e.g. every few minutes) so alerts don't wait for a manual sync?
