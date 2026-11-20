"""NFR-04: at least 10 concurrent users on one host, every action under 1 s.

Spec: code/specs/features/S3-03-multi-user-scalability.md.

Ten threads each play one signed-in user and repeat a realistic flow (sign in,
open the dashboard, save telemetry, add a goal, generate and open a
report) at the same time. Each step calls the same backend functions the
Reflex event handlers call, and Reflex runs those handlers in threads too, so
this is close to ten people clicking around one server.

The test checks three things:
- speed: 95% of actions under P95_LIMIT seconds and none over MAX_LIMIT,
- errors: none,
- isolation: every read returns only that user's rows.

Against the local Postgres in CI this mainly checks isolation and errors.
The NFR-04 numbers come from running it against healthify-test on Supabase
(see the spec). Run with `pytest -s code/backend/tests/test_concurrency.py`
to see the timing table.
"""

from __future__ import annotations

import math
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import pytest

from backend import (
    alerts,
    auth_controller,
    calories,
    db,
    goals,
    profile_controller,
    reports,
    telemetry_emulator,
    telemetry_store,
)

pytestmark = pytest.mark.usefixtures("test_db")

USERS = 10
ROUNDS = 3
P95_LIMIT = 1.0  # seconds (NFR-01 / NFR-04)
MAX_LIMIT = 2.0  # seconds; one slow outlier is tolerated, a slow pattern isn't
PASSWORD = "Loadtest1!"



def _telemetry(owner: str) -> dict:
    """A full emulator payload (~170 KB, what the app really saves), tagged
    with who it belongs to so a mix-up between users is visible."""
    data = telemetry_emulator.generate_fitbit_data("Medium")
    data["owner"] = owner
    return data


class Run:
    """Timings, errors, and isolation problems collected from all threads."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.timings: dict[str, list[float]] = defaultdict(list)
        self.errors: list[str] = []
        self.leaks: list[str] = []

    def timed(self, user: str, action: str, func):
        start = time.perf_counter()
        try:
            result = func()
        except Exception as exc:  # noqa: BLE001 - every failure is a test failure
            with self.lock:
                self.errors.append(f"{user} {action}: {type(exc).__name__}: {exc}")
            return None
        elapsed = time.perf_counter() - start
        with self.lock:
            self.timings[action].append(elapsed)
        return result

    def check(self, ok: bool, message: str) -> None:
        if not ok:
            with self.lock:
                self.leaks.append(message)


def _set_up_user(index: int) -> str:
    """Create the account and profile (not timed: this is before the load)."""
    username = f"load_user_{index:02d}"
    ok, message, _ = auth_controller.sign_up(username, f"{username}@example.com", PASSWORD)
    assert ok, message
    profile_controller.save_profile(username, "male", 20 + index, 150.0 + index)
    return username


def _user_flow(index: int, user: str, start: threading.Barrier, run: Run) -> None:
    my_targets: set[int] = set()
    telemetry = _telemetry(user)
    start.wait()  # every user starts at the same moment

    for round_ in range(ROUNDS):
        # Sign in (login page).
        _, _, account = run.timed(
            user, "sign in", lambda: auth_controller.sign_in(user, PASSWORD)
        ) or (None, None, None)
        run.check(account is not None and account["username"] == user,
                  f"{user} signed in as {account and account['username']}")

        # Open the dashboard: what its on_load handlers read.
        def open_dashboard():
            return (
                profile_controller.get_profile(user),
                alerts.list_alerts(user),
                telemetry_store.get_snapshot(user, "emulator"),
                calories.summary(user),
            )

        dashboard = run.timed(user, "open dashboard", open_dashboard)
        if dashboard:
            profile, user_alerts, snapshot, _ = dashboard
            run.check(profile is not None and profile["user_id"] == user
                      and profile["age"] == 20 + index,
                      f"{user} got profile {profile and profile['user_id']}")
            run.check(all(a["user_id"] == user for a in user_alerts),
                      f"{user} saw another user's alerts")
            run.check(snapshot is None or snapshot.get("owner") == user,
                      f"{user} saw telemetry owned by {snapshot and snapshot.get('owner')}")

        # Saving telemetry to the cloud right away (what a finished sync or
        # turning the emulator off does). Emulator-shaped data, because report
        # generation can't yet handle Google-sync data (see the spec).
        run.timed(user, "save telemetry", lambda: telemetry_store.save(user, telemetry, "emulator", force=True))
        latest = telemetry_store.get_latest(user)
        run.check(latest is not None and latest.get("owner") == user,
                  f"{user}'s latest telemetry is owned by {latest and latest.get('owner')}")

        # Goals page: add a goal, then the list reloads.
        target = 1000 + index * 10 + round_  # unique per user and round
        my_targets.add(target)

        def add_goal():
            goals.add_goal(user, goals.GOAL_DAILY_STEPS, target, reminders_enabled=False)
            return goals.list_goals(user)

        user_goals = run.timed(user, "add goal", add_goal)
        if user_goals is not None:
            run.check({g["target"] for g in user_goals} == my_targets,
                      f"{user} expected goals {sorted(my_targets)}, "
                      f"got {sorted(g['target'] for g in user_goals)}")

        # Reports page: generate one, then open it.
        report = run.timed(user, "generate report", lambda: reports.generate_report(user))
        if report:
            run.check(report["user_id"] == user, f"{user} generated a report for {report['user_id']}")
            targets = {g["target"] for g in report["content"]["goals"]}
            run.check(targets <= my_targets, f"{user}'s report includes goals {sorted(targets - my_targets)}")
            opened = run.timed(user, "open report", lambda: reports.get_report(user, report["id"]))
            run.check(opened is not None and opened["user_id"] == user,
                      f"{user} opened report {report['id']} and got {opened and opened['user_id']}")


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(pct * len(ordered)) - 1)]


def _print_table(run: Run, wall_seconds: float, stats: dict) -> None:
    every = [t for times in run.timings.values() for t in times]
    print(f"\n\nNFR-04 load test: {USERS} users x {ROUNDS} rounds in {wall_seconds:.1f} s")
    print(f"{'action':<18}{'count':>6}{'median':>9}{'p95':>9}{'max':>9}   (ms)")
    for action, times in [*run.timings.items(), ("ALL", every)]:
        print(f"{action:<18}{len(times):>6}{_percentile(times, 0.5) * 1000:>9.0f}"
              f"{_percentile(times, 0.95) * 1000:>9.0f}{max(times) * 1000:>9.0f}")
    print(f"pool: max {stats.get('pool_max')} connections, "
          f"{stats.get('requests_num', 0)} borrowed, "
          f"{stats.get('requests_queued', 0)} had to wait, "
          f"{stats.get('requests_wait_ms', 0)} ms waiting in total, "
          f"{stats.get('requests_errors', 0)} timed out")


def test_ten_concurrent_users_stay_fast_and_isolated():
    users = [_set_up_user(i) for i in range(USERS)]
    telemetry_store._reset_cache()  # start like a fresh server process
    pool = db._pool(db.database_url())
    pool.pop_stats()  # count only the load below

    run = Run()
    start = threading.Barrier(USERS)
    began = time.perf_counter()
    with ThreadPoolExecutor(max_workers=USERS) as executor:
        futures = [executor.submit(_user_flow, i, user, start, run) for i, user in enumerate(users)]
        for future in futures:
            future.result()
    wall = time.perf_counter() - began
    stats = pool.get_stats()
    _print_table(run, wall, stats)

    assert not run.errors, "Errors under load:\n" + "\n".join(run.errors)
    assert not run.leaks, "Data crossed between users:\n" + "\n".join(run.leaks)

    every = [t for times in run.timings.values() for t in times]
    assert len(every) == USERS * ROUNDS * 6
    slowest = max(every)
    p95 = _percentile(every, 0.95)
    assert p95 < P95_LIMIT, f"95th percentile {p95:.2f} s is over {P95_LIMIT} s"
    assert slowest < MAX_LIMIT, f"Slowest action {slowest:.2f} s is over {MAX_LIMIT} s"
