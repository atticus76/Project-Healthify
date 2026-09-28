# Requirements — Project Healthify

> **Source of truth** for what we're building. If something here disagrees with a Google Doc, Discord message, or someone's memory, this file wins — or open a PR to change it.
>
> Originally derived from *Project Assignment 1* (Sep 17–20, 2026). The full assignment write-up, including the GenAI reflection, is in [`Project Healthify_Assignment1_Requirements.pdf`](../../Project%20Healthify_Assignment1_Requirements.pdf).

**Team:** Hans Anstey, Yogi Chopra, Atticus Crook, Mohamed Dawoud
**Course:** CPTS 322 — Software Engineering Principles

---

## Overview

Healthify is a web app that pulls telemetry from a user's wearable (heart rate, HRV, steps, sleep, calories), compares it against the user's personal baseline, and surfaces trends, goals, and in-app alerts. It is a **student project, not a medical device** — it gives no medical advice and does not detect emergencies.

## Scope

**In scope**

- Wearable data via a provider's web API (OAuth 2.0), **not** Bluetooth
- A telemetry emulator so development never blocks on a real device or API access
- Accounts, user profiles, baselines, goals, alerts, and daily/weekly summaries

**Out of scope** (decided — see [Change log](#change-log))

- Food/nutrition tracking or third-party food or exercise databases
- Emergency detection (falls, AFib, etc.) and contacting emergency services
- SMS notifications (would require a paid API like Twilio)

**Wearable provider:** Google Health API or Whoop. Apple Watch (paid developer program + hardware) and Oura (partner application) are ruled out, and Fitbit's Web API is being deprecated. Given how much this space churns, the emulator (FR-08) is the baseline we can always fall back on.

---

## Rules for editing this file

1. **IDs never change.** Once something is FR-05, it stays FR-05. A merged or dropped requirement is marked **[Retired]**, not deleted or renumbered.
2. New requirements get the next unused number.
3. Every requirement should be **testable** — if you can't describe a pass/fail check for it, it isn't done being written.
4. Changes go through a PR so the whole team sees them.

---

## Functional Requirements

| ID | Requirement | Notes |
|---|---|---|
| FR-01 | Connect to a supported wearable provider account (Google Health API or Whoop) via OAuth 2.0 and import telemetry: heart rate, HRV, step count, sleep, and calories burned. | Merged original FR-01 + FR-02 |
| FR-02 | Notify the user in-app when a telemetry metric deviates from their personal baseline or from a general reference range for that metric. | |
| FR-03 | Display a disclaimer that the app does not provide medical advice, is not a substitute for a doctor, and cannot detect medical emergencies. | Replaced original EMS auto-detection |
| FR-04 | Allow the user to enter profile information (gender, age, weight) used to calculate their health metrics and baseline. | |
| FR-05 | Allow the user to register an account with email and password, with credentials stored securely. | |
| FR-06 | Store and retrieve user data in a cloud database. | |
| FR-07 | Provide daily and weekly recaps of the user's health data, potentially charted on a short-/long-term summary page. | |
| FR-08 | Provide a wearable telemetry emulator for use when live integration fails or provider access can't be obtained. | Added after GenAI review |
| FR-09 | Allow the user to create health goals and receive reminders/notifications that help them meet those goals. | Moved from NFRs |

## Non-Functional Requirements

| ID | Requirement | Notes |
|---|---|---|
| NFR-01 | The UI is fast and reliable, with response times under 1 second. | |
| NFR-02 | Third-party data failures and lost connections are handled gracefully: failed syncs are logged, retried with exponential backoff, and surfaced to the user, and the emulator (FR-08) can stand in for live data with a disclaimer. | Added after GenAI review |
| NFR-03 | Personal health and account information is encrypted. | |
| NFR-04 | The system handles multiple users simultaneously. | Needs a concrete number — see open decisions |
| NFR-05 | Cache user data to measure day-to-day changes in telemetry. | Under review — see open decisions |

---

## User Stories

### US-01: Device Connection

**As a** registered user, **I want** to connect my wearable provider account **so that** my telemetry automatically syncs to my health profile.

```gherkin
Scenario: Connect a wearable account
  Given I am on the settings page and select "Connect Device"
  When I am redirected to my wearable provider's login page and authorize access
  Then the system stores my authorization token
  And displays a "Device Connected" status
  And syncs my available telemetry data

Scenario: Scheduled sync fails
  Given my wearable account is connected
  When a scheduled sync request to the provider's API fails (expired authorization, outage, or rate limit)
  Then the system logs the failure
  And displays a "Reconnect Required" or "Sync Failed" indicator
  And retries on a backoff schedule rather than repeatedly hitting the API
```

### US-02: Account Registration

**As an** unregistered user, **I want** to create an account with my email and password **so that** my data is stored securely in the cloud.

```gherkin
Scenario: Register with valid credentials
  Given I am on the registration page
  When I enter a valid email and a password with at least one capital letter, one number, and one special character
  Then my account is created
  And I am redirected to the dashboard

Scenario: Email already registered
  Given I am on the registration page
  When I try to register with an email that already has an account
  Then an error message asks me to use different credentials
```

### US-03: Dashboard

**As a** user, **I want** a main page with my key information **so that** I can reach the app's features and see my data at a glance.

```gherkin
Scenario: Log in and see the dashboard
  Given I am a registered user on the login page
  When I log in with valid credentials
  Then I see the dashboard with my key information and features

Scenario: Session expires
  Given I am a registered user viewing the dashboard
  When my session token expires due to inactivity
  Then the system blocks access to the dashboard
  And redirects me to the login page with the message "Session expired, please log in again."
```

### US-04: Health Abnormality Alerts

**As a** user, **I want** to be alerted when my wearable metrics show sudden abnormalities **so that** I can take preventative action.

```gherkin
Scenario: Abnormal heart rate
  Given I have telemetry monitoring enabled
  When my resting heart rate exceeds 130 BPM for over 5 minutes
  Then the system sends an alert about the abnormal heart rate

Scenario: Spike during a disconnection
  Given my wearable loses connection while transferring data
  When an abnormal spike occurs during the disconnection
  Then the system logs the data gap on reconnection
  And prompts me to check my device placement without raising a false alarm
```

### US-05: User Profile Parameters

**As a** new user, **I want** to enter my personal information (gender, age, weight) **so that** the app can calculate my baseline metrics and health targets.

```gherkin
Scenario: Save a valid profile
  Given I am on the Profile Setup screen
  When I enter valid details (e.g., age 29, male, 175 lb) and click "Save Profile"
  Then the system saves my profile
  And updates my personalized baseline metrics

Scenario: Invalid weight
  Given I am on the Profile Setup screen
  When I leave weight blank or enter an invalid value (e.g., "-10") and click "Save Profile"
  Then the form is not submitted
  And an inline error asks for a valid number
```

### US-06: Goal Setting & Reminders

**As a** user, **I want** to set fitness goals and progress reminders **so that** I can track measurable improvement over time.

```gherkin
Scenario: Create a step goal
  Given I am on the Goal Management screen
  When I select "Daily Step Count", enter a target of 10,000, and enable reminders
  Then the system saves the goal
  And schedules progress notifications as I hit milestones

Scenario: Goal missed
  Given I have a daily step goal of 10,000
  When the day ends with fewer than 5,000 steps
  Then the system logs the goal as incomplete
  And shows a supportive motivational prompt the next morning
```

---

## Traceability

| Story | Requirements |
|---|---|
| US-01 Device Connection | FR-01, FR-08, NFR-02 |
| US-02 Account Registration | FR-05, FR-06, NFR-03 |
| US-03 Dashboard | FR-05, FR-07 — *no FR yet for the dashboard itself or session expiry* |
| US-04 Abnormality Alerts | FR-02, FR-03, NFR-02 |
| US-05 Profile Parameters | FR-04, FR-06 |
| US-06 Goals & Reminders | FR-09 |

---

## Open Decisions

Things the team still needs to agree on. Resolve these in a meeting or PR, then update the tables above.

- [ ] **NFR-05 (caching):** Keep, rewrite, or retire? It was originally for a food logger, which is now out of scope, and day-to-day tracking is arguably covered by FR-06/FR-07.
- [ ] **NFR-04:** Pick a concrete concurrent-user target so it's testable.
- [ ] **NFR-03:** Spell out what "encrypted" means: hashed passwords, HTTPS in transit, encryption at rest?
- [ ] **Dashboard / login / session expiry:** Add FRs so US-03 traces back to a requirement.
- [ ] **Wearable provider:** Google Health API or Whoop?
- [ ] **FR-02 thresholds:** Which metrics get alerts, and what counts as abnormal for each?

---

## Change Log

| Date | Change | Why |
|---|---|---|
| 2026-09-20 | Merged original FR-01 (telemetry) and FR-02 (device connection) into FR-01 | Same feature; GenAI review |
| 2026-09-20 | Replaced EMS auto-detection with a disclaimer (FR-03) | Over-scoped: fall/AFib detection is a hard problem and SMS needs a paid API |
| 2026-09-20 | Added telemetry emulator (FR-08) | Wearable API access is uncertain and changes often (Fitbit deprecation) |
| 2026-09-20 | US-01 changed from Bluetooth pairing to OAuth account connection | Provider web APIs use OAuth, not Bluetooth |
| 2026-09-20 | Goal setting moved from NFRs to FR-09 | It describes a feature, not a quality attribute |
| 2026-09-20 | Added failure-handling NFR-02 | Replaces part of the caching rationale; GenAI review |

---

*This document was compiled from the team's own Project Assignment 1 requirements with the help of generative AI (Anthropic's Claude), which organized and edited the material. All requirements, user stories, and decisions are the team's own and were reviewed by the team.*
