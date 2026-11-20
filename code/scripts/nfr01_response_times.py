"""NFR-01 response-time check (S3-01): time every user interaction against a large account.

Spec: code/specs/features/S3-01-response-time-check.md

Run from the repo root with .venv active:

    python code/scripts/nfr01_response_times.py [--runs 20] [--budget-ms 1000]
        [--alerts 2000] [--goals 25] [--reports 52] [--json results.json]

This is a developer tool, not part of the web app: nothing in
code/frontend/healthify imports it, and it never starts the app. It seeds a
throwaway perf user with a lot of data in the TEST database, calls each page's
real Reflex event handlers on a headless state tree, and reports the cold time
plus the median, p95 and max of the timed runs. An interaction passes when its
p95 is under the budget (NFR-01: 1000 ms). The perf user is always deleted.

Exit codes: 0 all pass, 1 something failed or raised, 2 the check couldn't run.
"""

from __future__ import annotations

import argparse
import inspect
import json
import math
import os
import secrets
import statistics
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest import mock

CODE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = CODE_DIR.parent
for _path in (CODE_DIR, CODE_DIR / "frontend"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from dotenv import dotenv_values  # noqa: E402

from backend import (  # noqa: E402
    alerts,
    auth_controller,
    db,
    email_alerts,
    goals,
    profile_controller,
    reports,
    telemetry_store,
)
from backend.telemetry_emulator import generate_fitbit_data  # noqa: E402

DEFAULT_RUNS = 20
DEFAULT_BUDGET_MS = 1000.0  # NFR-01
PASSWORD = "Perf-check1!"
USERNAME_PREFIX = "perf_nfr01_"
REPORT_EMAIL = "perf-check@example.com"


class CheckRefused(Exception):
    """The check can't run safely (no test database, unsafe URL, bad seed)."""


class UnsafeDatabase(CheckRefused):
    """DATABASE_URL stopped pointing at the test database mid-run."""


# --- Measuring --------------------------------------------------------------


@dataclass
class Interaction:
    page: str
    kind: str  # "load" | "poll" | "action"
    name: str
    call: Callable[[], Any]
    setup: Callable[[], Any] | None = None  # runs untimed before every call


@dataclass
class Result:
    page: str
    kind: str
    name: str
    budget_ms: float
    cold_ms: float | None = None
    samples_ms: list[float] = field(default_factory=list)
    error: str | None = None

    @property
    def median_ms(self) -> float | None:
        return statistics.median(self.samples_ms) if self.samples_ms else None

    @property
    def p95_ms(self) -> float | None:
        """Nearest-rank 95th percentile of the timed runs (cold run excluded)."""
        if not self.samples_ms:
            return None
        ordered = sorted(self.samples_ms)
        return ordered[math.ceil(0.95 * len(ordered)) - 1]

    @property
    def max_ms(self) -> float | None:
        return max(self.samples_ms) if self.samples_ms else None

    @property
    def status(self) -> str:
        if self.error is not None or not self.samples_ms:
            return "ERROR"
        return "PASS" if self.p95_ms < self.budget_ms else "FAIL"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.update(median_ms=self.median_ms, p95_ms=self.p95_ms, max_ms=self.max_ms, status=self.status)
        return data


def _timed(interaction: Interaction, after_call: Callable[[], None] | None) -> float:
    if interaction.setup is not None:
        interaction.setup()
    start = time.perf_counter()
    outcome = interaction.call()
    if inspect.isgenerator(outcome):  # handlers that yield (e.g. show a spinner)
        for _ in outcome:
            pass
    elapsed_ms = (time.perf_counter() - start) * 1000
    if after_call is not None:
        after_call()
    return elapsed_ms


def measure(
    interaction: Interaction,
    runs: int,
    budget_ms: float,
    after_call: Callable[[], None] | None = None,
) -> Result:
    """One cold (warm-up) run, timed but kept apart, then `runs` timed runs."""
    result = Result(interaction.page, interaction.kind, interaction.name, budget_ms)
    try:
        result.cold_ms = _timed(interaction, after_call)
        for _ in range(runs):
            result.samples_ms.append(_timed(interaction, after_call))
    except CheckRefused:
        raise
    except Exception as exc:  # report it and keep measuring the others
        result.error = f"{type(exc).__name__}: {exc}"
    return result


def measure_all(
    interactions: list[Interaction],
    runs: int,
    budget_ms: float,
    after_call: Callable[[], None] | None = None,
    progress: Callable[[Result], None] | None = None,
) -> list[Result]:
    results = []
    for interaction in interactions:
        result = measure(interaction, runs, budget_ms, after_call)
        results.append(result)
        if progress is not None:
            progress(result)
    return results


def exit_code(results: list[Result]) -> int:
    return 0 if results and all(r.status == "PASS" for r in results) else 1


# --- Output -----------------------------------------------------------------


def _ms(value: float | None) -> str:
    return "-" if value is None else f"{value:.0f}"


def format_table(results: list[Result]) -> str:
    header = ("Page", "Kind", "Interaction", "Cold", "Median", "p95", "Max", "Result")
    rows = [
        (r.page, r.kind, r.name, _ms(r.cold_ms), _ms(r.median_ms), _ms(r.p95_ms), _ms(r.max_ms), r.status)
        for r in results
    ]
    widths = [max(len(str(row[i])) for row in [header, *rows]) for i in range(len(header))]
    numeric = {3, 4, 5, 6}

    def line(row) -> str:
        return "  ".join(
            str(cell).rjust(widths[i]) if i in numeric else str(cell).ljust(widths[i])
            for i, cell in enumerate(row)
        )

    out = [line(header), "  ".join("-" * w for w in widths)]
    out.extend(line(row) for row in rows)
    out.append("Times in ms. Cold = the first (warm-up) run, not counted in median, p95 or max. "
               "PASS = p95 under the budget.")
    for r in results:
        if r.error:
            out.append(f"ERROR {r.page} {r.name}: {r.error}")
    return "\n".join(out)


def format_slowest(results: list[Result], count: int = 3) -> str:
    timed = sorted((r for r in results if r.p95_ms is not None), key=lambda r: r.p95_ms, reverse=True)
    lines = [f"Slowest {min(count, len(timed))} by p95:"]
    lines.extend(f"  {r.p95_ms:.0f} ms  {r.page} {r.name} ({r.status})" for r in timed[:count])
    return "\n".join(lines)


# --- Database safety --------------------------------------------------------


def resolve_test_database_url(environ: dict[str, str] | None = None) -> str:
    """The test database URL, or CheckRefused if it's missing or is the live one.

    Same rule as code/backend/tests/conftest.py. The live URL is checked both in
    the environment and in .env, because reload_config() can load .env later.
    """
    environ = os.environ if environ is None else environ
    url = environ.get("TEST_DATABASE_URL", "").strip()
    if not url:
        raise CheckRefused("TEST_DATABASE_URL isn't set in .env. The check only runs against the test database.")
    live = {
        environ.get("DATABASE_URL", "").strip(),
        (dotenv_values(REPO_ROOT / ".env").get("DATABASE_URL") or "").strip(),
    }
    if url in live:
        raise CheckRefused(
            "TEST_DATABASE_URL is the same as DATABASE_URL. The check writes data, "
            "so point TEST_DATABASE_URL at the separate healthify-test project."
        )
    return url


@contextmanager
def _test_database(url: str) -> Iterator[Callable[[], None]]:
    """Point the app at the test database, keep it there, and send no email.

    Yields a check to run after every call; it raises UnsafeDatabase if
    DATABASE_URL has moved.
    """
    original = os.environ.get("DATABASE_URL")
    reload_config = email_alerts.reload_config

    def reload_config_keeping_test_db() -> None:
        # reload_config() reloads .env with override=True, which resets both
        # database variables; put them back. It still runs, so its cost is timed.
        test_url_before = os.environ.get("TEST_DATABASE_URL")
        reload_config()
        os.environ["DATABASE_URL"] = url
        if test_url_before is None:
            os.environ.pop("TEST_DATABASE_URL", None)
        else:
            os.environ["TEST_DATABASE_URL"] = test_url_before

    def still_test_database() -> None:
        if os.environ.get("DATABASE_URL") != url:
            raise UnsafeDatabase("DATABASE_URL changed during the run; stopped before touching another database.")

    os.environ["DATABASE_URL"] = url
    try:
        with mock.patch.object(email_alerts, "reload_config", reload_config_keeping_test_db), \
                mock.patch.object(email_alerts, "dispatch", lambda *args, **kwargs: None), \
                mock.patch.object(email_alerts, "send", lambda *args, **kwargs: None):
            yield still_test_database
    finally:
        if original is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original


# --- The large account ------------------------------------------------------


@dataclass
class SeedSizes:
    alerts: int = 2000
    goals: int = 25
    reports: int = 52


def seed_large_user(username: str, sizes: SeedSizes) -> None:
    ok, message, _ = auth_controller.register(username, "", PASSWORD)
    if not ok:
        raise CheckRefused(f"Couldn't create the perf user: {message}")
    auth_controller.update_user(username, app_state={"telemetry_enabled": True})
    profile_controller.save_profile(username, "Male", 29, 175.0)
    reports.save_preferences(username, "weekly", REPORT_EMAIL)
    telemetry_store.save(username, generate_fitbit_data("High"), source="emulator", force=True)

    for _ in range(sizes.goals):
        goals.add_goal(username, goals.GOAL_DAILY_STEPS, 10_000, True)

    now = datetime.now(timezone.utc)
    alert_rows = []
    for i in range(sizes.alerts):
        started = now - timedelta(minutes=30 * (i + 1))
        alert_rows.append((
            username, alerts.KIND_HIGH_HEART_RATE, alerts.SEVERITY_URGENT, "Abnormal heart rate spike",
            "Seeded by the NFR-01 response-time check.", started.isoformat(),
            (started + timedelta(minutes=6)).isoformat(), 135 + i % 20, 1 if i % 3 == 0 else 0,
        ))
    content = json.dumps(reports.generate_report(username, persist=False)["content"])
    report_rows = []
    for week in range(sizes.reports):
        end = now - timedelta(weeks=week)
        report_rows.append((username, (end - timedelta(days=7)).isoformat(), end.isoformat(), end.isoformat(), content))

    with db.connect("seed perf user") as conn:
        cursor = conn.cursor()
        if alert_rows:
            cursor.executemany(
                "INSERT INTO health_alerts (user_id, kind, severity, title, message, started_at,"
                " ended_at, peak_bpm, acknowledged) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                alert_rows,
            )
        if report_rows:
            cursor.executemany(
                "INSERT INTO health_reports (user_id, period_start, period_end, generated_at, content)"
                " VALUES (%s, %s, %s, %s, %s)",
                report_rows,
            )
        # A realistic mix: every third goal already finished.
        conn.execute(
            "UPDATE goal_progress SET status = 'complete' WHERE goal_id IN ("
            " SELECT id FROM health_goals WHERE user_id = %s AND id %% 3 = 0)",
            (username,),
        )


def seed_counts(username: str) -> dict[str, int]:
    with db.connect("check perf seed") as conn:
        return dict(conn.execute(
            """
            SELECT
                (SELECT count(*) FROM health_alerts WHERE user_id = %(u)s) AS alerts,
                (SELECT count(*) FROM health_goals WHERE user_id = %(u)s) AS goals,
                (SELECT count(*) FROM goal_progress p JOIN health_goals g ON g.id = p.goal_id
                    WHERE g.user_id = %(u)s) AS progress,
                (SELECT count(*) FROM health_reports WHERE user_id = %(u)s) AS reports,
                (SELECT count(*) FROM health_profiles WHERE user_id = %(u)s) AS profiles,
                (SELECT count(*) FROM report_preferences WHERE user_id = %(u)s) AS preferences,
                (SELECT count(*) FROM telemetry_snapshots WHERE user_id = %(u)s) AS snapshots
            """,
            {"u": username},
        ).fetchone())


def verify_seed(username: str, sizes: SeedSizes) -> dict[str, int]:
    counts = seed_counts(username)
    expected = {
        "alerts": sizes.alerts, "goals": sizes.goals, "progress": sizes.goals, "reports": sizes.reports,
        "profiles": 1, "preferences": 1, "snapshots": 1,
    }
    wrong = {key: (counts[key], want) for key, want in expected.items() if counts[key] != want}
    if wrong:
        detail = ", ".join(f"{key} {got} (wanted {want})" for key, (got, want) in wrong.items())
        raise CheckRefused(f"The seed didn't verify: {detail}.")
    return counts


def delete_user(username: str) -> None:
    with db.connect("delete perf user") as conn:
        conn.execute("DELETE FROM users WHERE username = %s", (username,))  # cascades to every table
    telemetry_store._reset_cache()


# --- The interactions -------------------------------------------------------


@dataclass
class Context:
    """What build_interactions needs: who to sign in as."""

    username: str
    password: str = PASSWORD


def _states():
    import reflex as rx

    from healthify.state.alerts import AlertState
    from healthify.state.auth import AuthState
    from healthify.state.devices import DeviceState
    from healthify.state.goals import GoalsState
    from healthify.state.reports import ReportsState
    from healthify.state.telemetry import TelemetryState

    browser = rx.State(_reflex_internal_init=True)  # a fresh tab, no web server

    def state(cls):
        return browser.get_substate(cls.get_full_name().split(".")[1:])

    return {cls.__name__: (cls, state(cls)) for cls in
            (AuthState, AlertState, DeviceState, GoalsState, ReportsState, TelemetryState)}


def _no_error(state, attribute: str) -> None:
    message = getattr(state, attribute)
    if message:
        raise RuntimeError(message)


def build_interactions(context: Context) -> list[Interaction]:
    """Every measured interaction from the spec, in an order that keeps them valid."""
    s = _states()
    Auth, auth = s["AuthState"]
    Alert, alert = s["AlertState"]
    Device, device = s["DeviceState"]
    Goals, goal = s["GoalsState"]
    Reports, report = s["ReportsState"]
    Telemetry, telemetry = s["TelemetryState"]
    user = context.username

    def fill_sign_in():
        auth.mode, auth.identifier, auth.password = "login", user, context.password

    def sign_in():
        Auth.submit.fn(auth)
        _no_error(auth, "error")
        if auth.username != user:
            raise RuntimeError("Sign-in didn't sign the perf user in.")

    fill_sign_in()
    sign_in()  # every other handler needs a signed-in browser
    telemetry.enabled = True

    in_progress = next(g for g in goals.list_goals(user) if g["status"] == "in_progress")
    newest_alert = alerts.list_alerts(user)[0]
    deletable: list[str] = []

    def fill_profile():
        auth.gender, auth.age, auth.weight_lb = "Male", "29", "175"

    def save_profile():
        Auth.save_profile.fn(auth)
        _no_error(auth, "profile_error")

    def fill_goal():
        goal.target_input, goal.is_daily, goal.reminders_enabled = "10000", True, True

    def add_goal():
        Goals.add_goal.fn(goal)
        _no_error(goal, "goal_error")

    def fill_steps():
        # Steps add up, so start each run from an empty, in-progress goal;
        # 2,500 of 10,000 crosses the 25% milestone (toast + notification path).
        with db.connect("reset perf goal") as conn:
            conn.execute(
                "UPDATE goal_progress SET steps = 0, status = 'in_progress', milestones_sent = ''"
                " WHERE goal_id = %s",
                (in_progress["id"],),
            )
        goal.today_steps_input = "2500"

    def record_steps():
        Goals.record_steps.fn(goal, str(in_progress["id"]))
        _no_error(goal, "progress_error")

    def create_goal_to_delete():
        deletable.append(str(goals.add_goal(user, goals.GOAL_DAILY_STEPS, 10_000, False)["id"]))

    def fill_preferences():
        report.frequency, report.email = "weekly", REPORT_EMAIL

    def save_preferences():
        Reports.save_preferences.fn(report)
        _no_error(report, "error")

    def refresh_report():
        Reports.refresh_report.fn(report)
        _no_error(report, "error")

    def load_devices():
        Device.load.fn(device)
        _no_error(device, "error")

    return [
        Interaction("/login", "action", "Sign in", sign_in, setup=fill_sign_in),
        Interaction("/", "load", "Unread alert count (header badge)", lambda: Alert.load_unread.fn(alert)),
        Interaction("/", "load", "Telemetry page load", lambda: Telemetry.load_page.fn(telemetry)),
        Interaction("/profile", "load", "Load profile", lambda: Auth.load_profile.fn(auth)),
        Interaction("/profile", "action", "Save profile", save_profile, setup=fill_profile),
        Interaction("/goals", "load", "Goals page load", lambda: Goals.load_page.fn(goal)),
        Interaction("/goals", "poll", "Refresh goals (every 1 s)", lambda: Goals.refresh_goals.fn(goal)),
        Interaction("/goals", "action", "Add goal", add_goal, setup=fill_goal),
        Interaction("/goals", "action", "Record steps", record_steps, setup=fill_steps),
        Interaction("/goals", "action", "Delete goal", lambda: Goals.delete_goal.fn(goal, deletable.pop()),
                    setup=create_goal_to_delete),
        Interaction("/alerts", "load", "Alerts page load", lambda: Alert.load_page.fn(alert)),
        Interaction("/alerts", "action", "Acknowledge one alert",
                    lambda: Alert.acknowledge.fn(alert, str(newest_alert["id"]))),
        Interaction("/alerts", "action", "Acknowledge all alerts", lambda: Alert.acknowledge_all.fn(alert)),
        Interaction("/reports", "load", "Reports page load", lambda: Reports.load_page.fn(report)),
        Interaction("/reports", "poll", "Refresh report (every 1 s)", refresh_report),
        Interaction("/reports", "action", "Save report preferences", save_preferences, setup=fill_preferences),
        Interaction("/devices", "load", "Devices page load", load_devices),
        Interaction("/emulator", "action", "Turn emulator on", lambda: Telemetry.enable.fn(telemetry)),
        Interaction("/emulator", "action", "Change activity level",
                    lambda: Telemetry.set_level.fn(telemetry, "High")),
        Interaction("/emulator", "action", "Refresh telemetry", lambda: Telemetry.refresh.fn(telemetry)),
        Interaction("/emulator", "poll", "Auto-refresh telemetry (every 1 s)",
                    lambda: Telemetry.auto_refresh.fn(telemetry)),
        Interaction("/emulator", "action", "Turn emulator off", lambda: Telemetry.disable.fn(telemetry)),
    ]


# --- Running ----------------------------------------------------------------


@dataclass
class Report:
    username: str
    seeded: dict[str, int]
    results: list[Result]


def run(
    runs: int = DEFAULT_RUNS,
    budget_ms: float = DEFAULT_BUDGET_MS,
    sizes: SeedSizes | None = None,
    build: Callable[[Context], list[Interaction]] = build_interactions,
    progress: Callable[[Result], None] | None = None,
) -> Report:
    """Seed, measure and clean up. Raises CheckRefused if it can't run safely."""
    sizes = sizes or SeedSizes()
    url = resolve_test_database_url()
    username = USERNAME_PREFIX + secrets.token_hex(4)
    with _test_database(url) as still_test_database:
        seeded_user = False
        try:
            try:
                db.create_schema()  # idempotent; the test project may be fresh
                seeded_user = True  # from here on there may be rows to remove
                seed_large_user(username, sizes)
                seeded = verify_seed(username, sizes)
            except db.DatabaseError as exc:
                raise CheckRefused(f"Couldn't prepare the test database: {exc}") from exc
            interactions = build(Context(username))
            results = measure_all(interactions, runs, budget_ms, still_test_database, progress)
            return Report(username, seeded, results)
        finally:
            if seeded_user:
                os.environ["DATABASE_URL"] = url  # even after UnsafeDatabase: delete from the test DB only
                delete_user(username)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NFR-01 response-time check (S3-01). Uses TEST_DATABASE_URL only.")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS, help="timed runs per interaction (default 20)")
    parser.add_argument("--budget-ms", type=float, default=DEFAULT_BUDGET_MS, help="p95 budget in ms (default 1000)")
    parser.add_argument("--alerts", type=int, default=SeedSizes.alerts, help="alerts to seed (default 2000)")
    parser.add_argument("--goals", type=int, default=SeedSizes.goals, help="goals to seed (default 25)")
    parser.add_argument("--reports", type=int, default=SeedSizes.reports, help="saved reports to seed (default 52)")
    parser.add_argument("--json", type=Path, help="also write the results to this JSON file")
    args = parser.parse_args(argv)
    if args.runs < 1 or args.goals < 1 or args.alerts < 1 or args.reports < 0:
        parser.error("--runs, --goals and --alerts must be at least 1, --reports at least 0")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    sizes = SeedSizes(alerts=args.alerts, goals=args.goals, reports=args.reports)
    try:
        resolve_test_database_url()  # refuse before printing anything about seeding
    except CheckRefused as exc:
        print(f"Check refused: {exc}", file=sys.stderr)
        return 2
    print(f"NFR-01 check: {args.runs} timed runs per interaction, p95 budget {args.budget_ms:.0f} ms.")
    print(f"Seeding a perf user with {sizes.alerts} alerts, {sizes.goals} goals and {sizes.reports} reports...")

    def progress(result: Result) -> None:
        print(f"  {result.status:<5} {result.page} {result.name}", flush=True)

    try:
        report = run(args.runs, args.budget_ms, sizes, progress=progress)
    except CheckRefused as exc:
        print(f"Check refused: {exc}", file=sys.stderr)
        return 2
    print()
    print(format_table(report.results))
    code = exit_code(report.results)
    if code:
        print()
        print(format_slowest(report.results))
    if args.json:
        args.json.write_text(json.dumps({
            "budget_ms": args.budget_ms, "runs": args.runs, "seeded": report.seeded,
            "results": [r.to_dict() for r in report.results],
        }, indent=2), encoding="utf-8")
        print(f"Results written to {args.json}")
    print("PASS: every interaction met the budget." if code == 0 else "FAIL: see the table above.")
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        db.close_pools()
