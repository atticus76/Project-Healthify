-- Healthify database schema (S2-04).
--
-- Apply with `python -m backend.db.init` from the code/ folder. Safe to re-run:
-- every statement is IF NOT EXISTS or idempotent. To change a table that
-- already exists, write the ALTER TABLE by hand (there is no migration tool).
--
-- Straight port from SQLite: timestamps stay ISO-8601 TEXT and flags stay
-- INTEGER 0/1, so the Python code that reads them doesn't change. Epoch-second
-- columns are BIGINT, and SQLite REAL (8 bytes) becomes DOUBLE PRECISION
-- (PostgreSQL's REAL is only 4 bytes).
--
-- Columns that SQLite filled with CURRENT_TIMESTAMP use the same
-- 'YYYY-MM-DD HH:MM:SS' UTC text format here.

-- Accounts. Replaces code/backend/users.txt and data/accounts.json.
-- username is case-sensitive; the app lowercases email before saving it.
CREATE TABLE IF NOT EXISTS users (
    username      TEXT PRIMARY KEY,
    email         TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    app_state     JSONB NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS health_profiles (
    user_id                  TEXT PRIMARY KEY REFERENCES users (username) ON DELETE CASCADE,
    gender                   TEXT NOT NULL,
    age                      INTEGER NOT NULL,
    weight_lb                DOUBLE PRECISION NOT NULL,
    baseline_weight_lb       DOUBLE PRECISION NOT NULL,
    estimated_daily_calories INTEGER NOT NULL,
    updated_at               TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS health_goals (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id             TEXT NOT NULL REFERENCES users (username) ON DELETE CASCADE,
    goal_type           TEXT NOT NULL,
    target              INTEGER NOT NULL,
    is_daily            INTEGER NOT NULL DEFAULT 1,
    reminders_enabled   INTEGER NOT NULL DEFAULT 0,
    reminder_25_enabled INTEGER NOT NULL DEFAULT 1,
    reminder_50_enabled INTEGER NOT NULL DEFAULT 1,
    reminder_75_enabled INTEGER NOT NULL DEFAULT 1,
    deadline_at         TEXT NOT NULL,
    created_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS health_goals_user_id_idx ON health_goals (user_id);

CREATE TABLE IF NOT EXISTS goal_progress (
    goal_id         BIGINT PRIMARY KEY REFERENCES health_goals (id) ON DELETE CASCADE,
    steps           INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'in_progress',
    prompt          TEXT NOT NULL DEFAULT '',
    milestones_sent TEXT NOT NULL DEFAULT '',
    reminders_sent  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS health_alerts (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES users (username) ON DELETE CASCADE,
    kind         TEXT NOT NULL,
    severity     TEXT NOT NULL,
    title        TEXT NOT NULL,
    message      TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    ended_at     TEXT NOT NULL,
    peak_bpm     INTEGER,
    created_at   TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS'),
    acknowledged INTEGER NOT NULL DEFAULT 0,
    UNIQUE (user_id, kind, started_at)
);

CREATE TABLE IF NOT EXISTS alert_settings (
    user_id TEXT PRIMARY KEY REFERENCES users (username) ON DELETE CASCADE,
    email   TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS report_preferences (
    user_id    TEXT PRIMARY KEY REFERENCES users (username) ON DELETE CASCADE,
    frequency  TEXT NOT NULL,
    email      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS health_reports (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users (username) ON DELETE CASCADE,
    period_start    TEXT NOT NULL,
    period_end      TEXT NOT NULL,
    generated_at    TEXT NOT NULL,
    content         TEXT NOT NULL,
    delivery_status TEXT NOT NULL DEFAULT 'not_sent',
    delivery_error  TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS health_reports_user_id_idx ON health_reports (user_id);

-- Google OAuth. created_at, expires_at, connected_at and last_sync_at are epoch seconds.
CREATE TABLE IF NOT EXISTS oauth_pending (
    state         TEXT PRIMARY KEY,
    code_verifier TEXT NOT NULL,
    user_id       TEXT NOT NULL REFERENCES users (username) ON DELETE CASCADE,
    created_at    BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS google_connections (
    user_id       TEXT PRIMARY KEY REFERENCES users (username) ON DELETE CASCADE,
    email         TEXT,
    access_token  TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at    BIGINT NOT NULL,
    scope         TEXT,
    status        TEXT NOT NULL,
    device_name   TEXT,
    connected_at  BIGINT NOT NULL,
    last_sync_at  BIGINT
);

-- Latest synced telemetry per user and source (history is S3-04).
-- Today this is an in-memory dict in telemetry_emulator.py.
CREATE TABLE IF NOT EXISTS telemetry_snapshots (
    user_id   TEXT NOT NULL REFERENCES users (username) ON DELETE CASCADE,
    source    TEXT NOT NULL CHECK (source IN ('google', 'emulator')),
    data      JSONB NOT NULL,
    synced_at TEXT NOT NULL,
    PRIMARY KEY (user_id, source)
);

-- Row Level Security on, with no policies: this blocks Supabase's
-- auto-generated REST API from reading these tables. The app connects as the
-- table owner (postgres), which RLS doesn't apply to.
ALTER TABLE users               ENABLE ROW LEVEL SECURITY;
ALTER TABLE health_profiles     ENABLE ROW LEVEL SECURITY;
ALTER TABLE health_goals        ENABLE ROW LEVEL SECURITY;
ALTER TABLE goal_progress       ENABLE ROW LEVEL SECURITY;
ALTER TABLE health_alerts       ENABLE ROW LEVEL SECURITY;
ALTER TABLE alert_settings      ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_preferences  ENABLE ROW LEVEL SECURITY;
ALTER TABLE health_reports      ENABLE ROW LEVEL SECURITY;
ALTER TABLE oauth_pending       ENABLE ROW LEVEL SECURITY;
ALTER TABLE google_connections  ENABLE ROW LEVEL SECURITY;
ALTER TABLE telemetry_snapshots ENABLE ROW LEVEL SECURITY;
