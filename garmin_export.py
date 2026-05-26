"""
garmin_export.py — Garmin → health_snapshot.csv exporter
--------------------------------------------------------
Fetches today's Garmin metrics and appends one row to
Documents/trend-engine/health_snapshot.csv.

Run this AFTER garmin_daily.py finishes (sleep data needs time to sync).
Recommended: schedule 30–60 min after your morning garmin_daily task.

Requires: garminconnect   (pip install garminconnect)
Env vars:
  GARMIN_PASSWORD     — your Garmin Connect password
  GARMIN_EMAIL        — optional override (defaults to jamiemancuso5@gmail.com)
"""

import csv
import datetime
import os
import sys

# ── garminconnect import ────────────────────────────────────────────────────
try:
    from garminconnect import Garmin
except ImportError:
    sys.exit("garminconnect not installed. Run: pip install garminconnect")

# ── config ──────────────────────────────────────────────────────────────────
EMAIL       = os.environ.get("GARMIN_EMAIL", "jamiemancuso5@gmail.com")
PASSWORD    = os.environ.get("GARMIN_PASSWORD")
TOKEN_STORE = os.path.join(os.path.expanduser("~"), ".garmin_tokens")

# health_snapshot.csv lives in the same folder as this script
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
SNAPSHOT    = os.path.join(SCRIPT_DIR, "health_snapshot.csv")

COLUMNS = [
    "date",
    "sleep_hrs", "sleep_score", "sleep_deep_min", "sleep_rem_min", "sleep_awake_min",
    "hrv_last_night_avg", "hrv_weekly_avg", "hrv_baseline_low", "hrv_baseline_high", "hrv_status",
    "rhr_bpm",
    "body_battery_low", "body_battery_high",
    "training_readiness_score", "training_readiness_limiting_factor",
    "training_status", "acute_load", "chronic_load", "acwr", "recovery_hrs",
    "steps",
    "avg_stress", "max_stress",
]


# ── login ────────────────────────────────────────────────────────────────────
def login():
    if not PASSWORD:
        sys.exit("Set GARMIN_PASSWORD environment variable before running.")
    print("Connecting to Garmin Connect...")
    client = Garmin(EMAIL, PASSWORD)
    try:
        client.login(TOKEN_STORE)
        print("Logged in with saved tokens.")
    except Exception:
        client.login()
        client.garth.dump(TOKEN_STORE)
        print("Logged in fresh, tokens saved.")
    return client


# ── safe fetch helpers ───────────────────────────────────────────────────────
def safe(fn, *args, default=None, **kwargs):
    """Call fn(*args, **kwargs); return default on any exception."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        print(f"  [warn] {fn.__name__}: {e}")
        return default


# ── metric extractors ────────────────────────────────────────────────────────
def get_sleep(client, today_str):
    data = safe(client.get_sleep_data, today_str, default={})
    s = (data or {}).get("dailySleepDTO", {})
    hrs   = round(s.get("sleepTimeSeconds", 0) / 3600, 2) or None
    score = s.get("sleepScores", {}).get("overall", {}).get("value") or None
    deep  = round(s.get("deepSleepSeconds", 0) / 60) or None
    rem   = round(s.get("remSleepSeconds",  0) / 60) or None
    awake = round(s.get("awakeSleepSeconds",0) / 60) or None
    return hrs, score, deep, rem, awake


def get_hrv(client, today_str):
    data = safe(client.get_hrv_data, today_str, default={})
    h = (data or {}).get("hrvSummary", {})
    b = h.get("baseline", {})
    return (
        h.get("lastNightAvg"),
        h.get("weeklyAvg"),
        b.get("balancedLow"),
        b.get("balancedHigh"),
        h.get("status"),
    )


def get_rhr(client, today_str):
    data = safe(client.get_rhr_day, today_str, default={})
    val = (
        (data or {})
        .get("allMetrics", {})
        .get("metricsMap", {})
        .get("WELLNESS_RESTING_HEART_RATE", [{}])[0]
        .get("value")
    )
    return val


def get_body_battery(client, yest_str):
    data = safe(client.get_body_battery, yest_str, default=[])
    vals = []
    for entry in (data or []):
        for point in entry.get("bodyBatteryValuesArray", []):
            if len(point) >= 2 and point[1] is not None:
                vals.append(point[1])
    if not vals:
        return None, None
    return min(vals), max(vals)


def get_training_readiness(client, today_str):
    data = safe(client.get_training_readiness, today_str, default=None)
    r = data[0] if isinstance(data, list) and data else (data or {})
    return r.get("score"), r.get("primaryLimitingFactor")


def get_training_status(client, today_str):
    data = safe(client.get_training_status, today_str, default=None)
    ts = data[0] if isinstance(data, list) and data else (data or {})
    acute   = ts.get("acuteLoad")
    chronic = ts.get("chronicLoad")
    acwr    = None
    if isinstance(acute, (int, float)) and isinstance(chronic, (int, float)) and chronic:
        acwr = round(acute / chronic, 2)
    return ts.get("trainingStatus"), acute, chronic, acwr, ts.get("recoveryTime")


def get_steps(client, today_str):
    data = safe(client.get_steps_data, today_str, default=[])
    return sum(s.get("steps", 0) for s in (data or []))


def get_stress(client, today_str):
    data = safe(client.get_stress_data, today_str, default={})
    return (data or {}).get("avgStressLevel"), (data or {}).get("maxStressLevel")


# ── CSV helpers ──────────────────────────────────────────────────────────────
def load_existing_dates():
    if not os.path.exists(SNAPSHOT):
        return set()
    with open(SNAPSHOT, newline="", encoding="utf-8") as f:
        return {row["date"] for row in csv.DictReader(f) if row.get("date")}


def append_row(row: dict):
    file_exists = os.path.exists(SNAPSHOT)
    with open(SNAPSHOT, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerow({col: row.get(col, "") for col in COLUMNS})


# ── main ─────────────────────────────────────────────────────────────────────
def main():
    today     = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    today_str = today.isoformat()
    yest_str  = yesterday.isoformat()

    existing = load_existing_dates()
    if today_str in existing:
        print(f"Row for {today_str} already exists in health_snapshot.csv — skipping.")
        print("(Re-run with --force to overwrite today's row.)")
        if "--force" not in sys.argv:
            return

    print(f"\nFetching Garmin data for {today_str}...")
    client = login()

    print("  sleep...")
    sleep_hrs, sleep_score, deep, rem, awake = get_sleep(client, today_str)

    print("  HRV...")
    hrv_avg, hrv_weekly, hrv_low, hrv_high, hrv_status = get_hrv(client, today_str)

    print("  RHR...")
    rhr = get_rhr(client, today_str)

    print("  body battery (yesterday's arc)...")
    bb_low, bb_high = get_body_battery(client, yest_str)

    print("  training readiness...")
    tr_score, tr_limit = get_training_readiness(client, today_str)

    print("  training status & load...")
    ts_status, acute, chronic, acwr, recovery = get_training_status(client, today_str)

    print("  steps...")
    steps = get_steps(client, today_str)

    print("  stress...")
    avg_stress, max_stress = get_stress(client, today_str)

    row = {
        "date":                             today_str,
        "sleep_hrs":                        sleep_hrs,
        "sleep_score":                      sleep_score,
        "sleep_deep_min":                   deep,
        "sleep_rem_min":                    rem,
        "sleep_awake_min":                  awake,
        "hrv_last_night_avg":               hrv_avg,
        "hrv_weekly_avg":                   hrv_weekly,
        "hrv_baseline_low":                 hrv_low,
        "hrv_baseline_high":                hrv_high,
        "hrv_status":                       hrv_status,
        "rhr_bpm":                          rhr,
        "body_battery_low":                 bb_low,
        "body_battery_high":                bb_high,
        "training_readiness_score":         tr_score,
        "training_readiness_limiting_factor": tr_limit,
        "training_status":                  ts_status,
        "acute_load":                       acute,
        "chronic_load":                     chronic,
        "acwr":                             acwr,
        "recovery_hrs":                     recovery,
        "steps":                            steps,
        "avg_stress":                       avg_stress,
        "max_stress":                       max_stress,
    }

    # --force: remove today's existing row before appending
    if "--force" in sys.argv and today_str in existing:
        rows = []
        with open(SNAPSHOT, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("date") != today_str:
                    rows.append(r)
        with open(SNAPSHOT, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

    append_row(row)
    print(f"\nWrote row to health_snapshot.csv:")
    for k, v in row.items():
        if v not in (None, "", 0):
            print(f"  {k}: {v}")
    print("\nDone.")


if __name__ == "__main__":
    main()
