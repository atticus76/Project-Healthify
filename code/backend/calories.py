"""Account calorie counters. Emulator sessions integrate their sampled kcal/min
rate over elapsed time, even while the browser is closed. Device intervals
contribute only outside those sessions, including when sync is delayed.
"""
from datetime import datetime
from math import isfinite

from backend.db import connect


def emulator_rate(user, rate, *, change=False, enabled=None):
    with connect("update emulator calorie rate") as conn:
        account = conn.execute("SELECT app_state FROM users WHERE username=%s FOR UPDATE",
                               (user,)).fetchone()
        if not account:
            return
        if enabled is None and not (account["app_state"] or {}).get("telemetry_enabled"):
            return
        if enabled is not None:
            conn.execute("""UPDATE users SET app_state=jsonb_set(app_state,'{telemetry_enabled}',
                            to_jsonb(%s::boolean)) WHERE username=%s""", (enabled, user))
        if change or rate is None:
            conn.execute("""UPDATE calorie_emulator_sessions SET stopped=statement_timestamp()
                            WHERE user_id=%s AND stopped IS NULL""", (user,))
        if rate is not None:
            conn.execute("""INSERT INTO calorie_emulator_sessions(user_id,started,kcal_per_min)
                            VALUES (%s,statement_timestamp(),%s) ON CONFLICT DO NOTHING""",
                         (user, rate))


def record_device_samples(conn, user, points, connected_at):
    rows = []
    for point in points:
        try:
            start = datetime.fromisoformat(point["startTime"])
            end = datetime.fromisoformat(point["endTime"])
            kcal = float(point["totalCalories"]["kcalSum"])
            effective_start = max(connected_at, start.timestamp())
            if end.timestamp() <= effective_start or not isfinite(kcal) or kcal < 0:
                continue
            fraction = (end.timestamp()-effective_start) / (end-start).total_seconds()
            rows.append((user, effective_start, end, kcal*fraction))
        except (KeyError, ValueError, TypeError, OverflowError):
            continue
    if rows:
        with conn.cursor() as cursor:
            cursor.executemany("""INSERT INTO calorie_device_samples VALUES (%s,to_timestamp(%s),%s,%s)
                                  ON CONFLICT (user_id,started,stopped) DO UPDATE SET kcal=excluded.kcal""", rows)


def period_summary(conn, user, start=None, end=None):
    return conn.execute("""
            WITH period AS (
                SELECT coalesce(%(start)s::timestamptz, (SELECT reset_at FROM calorie_counters WHERE user_id=%(u)s),
                                '-infinity'::timestamptz) AS since, coalesce(%(end)s::timestamptz,now()) AS until
            ), sessions AS (
                SELECT greatest(started,since) AS a, least(coalesce(stopped,until),until) AS b, kcal_per_min
                FROM calorie_emulator_sessions,period
                WHERE user_id=%(u)s AND started < until AND coalesce(stopped,until) > since
            ), device AS (
                SELECT greatest(started,since) AS a, least(stopped,until) AS b,
                       kcal / extract(epoch FROM stopped-started) AS rate
                FROM calorie_device_samples,period WHERE user_id=%(u)s AND stopped>since AND started<until
            )
            SELECT coalesce((SELECT sum(kcal_per_min * extract(epoch FROM b-a)/60) FROM sessions),0)
                 + coalesce((SELECT sum(rate * (extract(epoch FROM d.b-d.a) -
                     coalesce((SELECT sum(extract(epoch FROM least(s.b,d.b)-greatest(s.a,d.a)))
                               FROM sessions s WHERE s.b>d.a AND s.a<d.b),0))) FROM device d),0) AS burned,
                   CASE WHEN %(start)s::timestamptz IS NULL THEN
                       coalesce((SELECT consumed FROM calorie_counters WHERE user_id=%(u)s),0)
                   ELSE (SELECT coalesce(sum(kcal),0) FROM meal_entries,period
                         WHERE user_id=%(u)s AND logged_at>=since AND logged_at<until) END AS consumed,
                   (SELECT calorie_target FROM health_profiles WHERE user_id=%(u)s) AS target,
                   NOT EXISTS (SELECT 1 FROM health_profiles WHERE user_id=%(u)s
                               AND height_cm IS NOT NULL AND activity_level IS NOT NULL) AS incomplete
            """, {"u": user, "start": start, "end": end}).fetchone()


def summary(user):
    with connect("load calories") as conn:
        return period_summary(conn, user)


def daily_budget(user, midnight):
    with connect("load recipe calorie budget") as conn:
        return conn.execute("""SELECT p.calorie_target AS target, coalesce(sum(m.kcal),0) AS eaten,
                               max(m.id) AS last_meal
                               FROM health_profiles p LEFT JOIN meal_entries m ON
                               m.user_id=p.user_id AND m.logged_at >= %s
                               WHERE p.user_id=%s GROUP BY p.calorie_target""", (midnight,user)).fetchone()


def reset(user):
    with connect("reset calories") as conn:
        conn.execute("""INSERT INTO calorie_counters(user_id,reset_at) VALUES (%s,now())
                        ON CONFLICT(user_id) DO UPDATE SET reset_at=excluded.reset_at, consumed=0""",(user,))


def add_food(user, kcal):
    with connect("log consumed calories") as conn:
        conn.execute("INSERT INTO meal_entries(user_id,kcal) VALUES (%s,%s)", (user,kcal))
        conn.execute("""INSERT INTO calorie_counters(user_id,consumed) VALUES (%s,%s)
                        ON CONFLICT(user_id) DO UPDATE SET consumed=calorie_counters.consumed+excluded.consumed""",
                     (user,kcal))
