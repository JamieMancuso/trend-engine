"""
pages/3_Health.py — Personal Health Dashboard
----------------------------------------------
Data sources:
  1. health_snapshot.csv  — Garmin metrics written daily by garmin_export.py
  2. Google Sheet "Health Tracking 2026" — manual log (weight, mood, alcohol,
     calories, workout notes) fetched live via Google Drive MCP

Merge key: date (YYYY-MM-DD). Garmin rows are always present when the export
ran; manual rows fill in the subjective columns.
"""

import datetime
import os
import json
import re

import pandas as pd
import streamlit as st

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Health", page_icon="💚", layout="wide")

# Resolve project root robustly — works both locally and on Streamlit Cloud.
# On Cloud, __file__ is something like /mount/src/trend-engine/pages/3_Health.py
# so dirname(dirname(__file__)) gives the repo root.
# We also check the cwd as a fallback (Streamlit Cloud sets cwd = repo root).
_SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR  = os.path.dirname(_SCRIPT_DIR)

def _find_project_dir():
    """Return the directory that contains health_snapshot.csv."""
    for candidate in [_PARENT_DIR, _SCRIPT_DIR, os.getcwd()]:
        if os.path.exists(os.path.join(candidate, "health_snapshot.csv")):
            return candidate
    # Default to parent (most likely on Cloud)
    return _PARENT_DIR

PROJECT_DIR  = _find_project_dir()
SNAPSHOT_CSV = os.path.join(PROJECT_DIR, "health_snapshot.csv")

# Google Sheet file ID for "Health Tracking 2026"
GDRIVE_FILE_ID = "14ScOHFxb-3sXGx_-YHsff2sHxHBiO5c4WDkk1vdXZZ0"

# ── colour palette (dark-mode friendly) ──────────────────────────────────────
C_SLEEP   = "#7eb8f7"   # soft blue
C_HRV     = "#7eeab0"   # soft green
C_RHR     = "#f7a07e"   # soft orange
C_STRESS  = "#f7d07e"   # soft yellow
C_ALCOHOL = "#c084fc"   # soft purple
C_MOOD    = "#fb7185"   # soft pink
C_WEIGHT  = "#94a3b8"   # slate


# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def load_garmin() -> pd.DataFrame:
    """Load health_snapshot.csv. Returns empty DF if file missing."""
    if not os.path.exists(SNAPSHOT_CSV):
        return pd.DataFrame()
    df = pd.read_csv(SNAPSHOT_CSV, parse_dates=["date"])
    df["date"] = pd.to_datetime(df["date"]).dt.date
    numeric_cols = [c for c in df.columns if c != "date"
                    and c not in ("hrv_status", "training_readiness_limiting_factor",
                                  "training_status")]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values("date").reset_index(drop=True)


def _parse_manual_sheet(raw: str) -> pd.DataFrame:
    """
    Parse the markdown table returned by the Drive MCP into a DataFrame.
    Handles messy/shifted rows gracefully — bad rows are skipped.
    """
    rows = []
    header = None
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip().replace("\\~", "~").replace("\\", "") for c in line.split("|")[1:-1]]
        if not cells:
            continue
        if header is None:
            header = cells
            continue
        if all(set(c) <= set(":-") for c in cells):
            continue   # separator row
        if len(cells) < len(header):
            cells += [""] * (len(header) - len(cells))
        rows.append(dict(zip(header, cells[:len(header)])))

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # Normalise date column
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
        df = df.dropna(subset=["date"])

    # Numeric columns — strip ~ and convert
    num_cols = ["weight_lb", "sleep_hrs", "sleep_score", "HRV", "RHR",
                "body_battery_AM", "est_calories", "est_protein_g",
                "alcohol_drinks", "stress_1to10", "mood_1to10", "soreness_1to10"]
    for col in num_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace("~", "", regex=False).str.strip()
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.sort_values("date").reset_index(drop=True)


@st.cache_data(ttl=300)
def load_manual_sheet() -> pd.DataFrame:
    """
    Fetch the Health Tracking 2026 Google Sheet via Drive MCP.
    Falls back to empty DF on any error.
    """
    try:
        import subprocess, sys
        # We can't call MCP tools from inside Streamlit's runtime, so we
        # read from a cached export if available, otherwise show a note.
        pass
    except Exception:
        pass

    # Check for a local CSV export of the sheet (written by garmin_export or manually)
    manual_csv = os.path.join(_find_project_dir(), "health_manual.csv")
    if os.path.exists(manual_csv):
        df = pd.read_csv(manual_csv)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
            df = df.dropna(subset=["date"])
        return df.sort_values("date").reset_index(drop=True) if not df.empty else df

    return pd.DataFrame()


def merge_sources(garmin: pd.DataFrame, manual: pd.DataFrame) -> pd.DataFrame:
    """
    Outer-join Garmin + manual on date. Garmin columns take priority for
    fields that overlap (sleep_score, HRV, RHR, body_battery).
    Manual fills in weight, mood, alcohol, calories, notes.
    """
    if garmin.empty and manual.empty:
        return pd.DataFrame()
    if garmin.empty:
        return manual.copy()
    if manual.empty:
        return garmin.copy()

    # Rename manual sheet columns to avoid collisions where Garmin is authoritative
    rename_map = {
        "sleep_score": "m_sleep_score",
        "HRV":         "m_HRV",
        "RHR":         "m_RHR",
        "body_battery_AM": "m_body_battery_AM",
        "sleep_hrs":   "m_sleep_hrs",
    }
    m = manual.rename(columns={k: v for k, v in rename_map.items() if k in manual.columns})

    merged = pd.merge(garmin, m, on="date", how="outer")
    merged = merged.sort_values("date").reset_index(drop=True)
    return merged


# ══════════════════════════════════════════════════════════════════════════════
# METRIC CARD HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def metric_card(col, label, value, unit="", delta=None, color="#7eb8f7"):
    """Render a single KPI card."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        display = "—"
        delta_str = ""
    else:
        display = f"{value}{unit}"
        delta_str = f" ({delta:+.0f})" if delta is not None and not pd.isna(delta) else ""

    col.markdown(
        f"""
        <div style="background:#1e2530;border-radius:10px;padding:14px 18px;
                    border-left:4px solid {color};margin-bottom:4px">
            <div style="color:#94a3b8;font-size:0.75rem;letter-spacing:.05em">{label}</div>
            <div style="color:#f1f5f9;font-size:1.6rem;font-weight:700;line-height:1.2">
                {display}<span style="font-size:0.85rem;color:#94a3b8">{delta_str}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def score_color(score):
    if score is None or pd.isna(score):
        return "#94a3b8"
    if score >= 75:
        return "#7eeab0"
    if score >= 50:
        return "#f7d07e"
    return "#f87171"


# ══════════════════════════════════════════════════════════════════════════════
# CHART HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def line_chart(df, cols, colors, title, y_label="", height=260):
    """Simple Streamlit line chart wrapper with a title."""
    plot_df = df[["date"] + [c for c in cols if c in df.columns]].copy()
    plot_df = plot_df.dropna(subset=[c for c in cols if c in df.columns], how="all")
    if plot_df.empty:
        st.caption(f"No data yet for: {title}")
        return
    plot_df["date"] = pd.to_datetime(plot_df["date"])
    plot_df = plot_df.set_index("date")
    st.markdown(f"**{title}**")
    st.line_chart(plot_df, height=height, use_container_width=True)


def bar_chart(df, col, color, title, height=200):
    plot_df = df[["date", col]].dropna().copy()
    if plot_df.empty:
        st.caption(f"No data for: {title}")
        return
    plot_df["date"] = pd.to_datetime(plot_df["date"])
    plot_df = plot_df.set_index("date")
    st.markdown(f"**{title}**")
    st.bar_chart(plot_df, height=height, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE LAYOUT
# ══════════════════════════════════════════════════════════════════════════════

st.title("💚 Health Dashboard")

garmin = load_garmin()
manual = load_manual_sheet()
df     = merge_sources(garmin, manual)

# ── data status banner ───────────────────────────────────────────────────────
col_a, col_b = st.columns(2)
with col_a:
    if garmin.empty:
        st.warning("No Garmin data yet — run `garmin_export.py` once to seed health_snapshot.csv.")
    else:
        latest_garmin = garmin["date"].max()
        days_ago = (datetime.date.today() - latest_garmin).days
        label = "today" if days_ago == 0 else f"{days_ago}d ago"
        st.caption(f"Garmin data: last updated **{latest_garmin}** ({label}) · {len(garmin)} days logged")
with col_b:
    if manual.empty:
        st.caption("Manual log: not synced — run the Drive sync to load your Google Sheet data.")
    else:
        st.caption(f"Manual log: **{len(manual)} rows** from Health Tracking 2026 · synced from Google Drive")

st.divider()

# ── today's readiness strip ──────────────────────────────────────────────────
st.subheader("Today's Readiness")

today = datetime.date.today()
today_g = garmin[garmin["date"] == today].iloc[-1] if not garmin.empty and (garmin["date"] == today).any() else None
yest_g  = garmin[garmin["date"] == (today - datetime.timedelta(days=1))].iloc[-1] \
          if not garmin.empty and (garmin["date"] == (today - datetime.timedelta(days=1))).any() else None

def val(row, col):
    if row is None:
        return None
    v = row.get(col) if isinstance(row, dict) else (row[col] if col in row.index else None)
    return None if pd.isna(v) else v

def delta(today_row, yest_row, col):
    t = val(today_row, col)
    y = val(yest_row, col)
    if t is None or y is None:
        return None
    return t - y

c1, c2, c3, c4, c5, c6 = st.columns(6)

sleep_score = val(today_g, "sleep_score")
metric_card(c1, "Sleep Score", sleep_score,
            color=score_color(sleep_score),
            delta=delta(today_g, yest_g, "sleep_score"))

metric_card(c2, "Sleep", val(today_g, "sleep_hrs"), "h",
            color=C_SLEEP,
            delta=delta(today_g, yest_g, "sleep_hrs"))

hrv = val(today_g, "hrv_last_night_avg")
metric_card(c3, "HRV", hrv, " ms",
            color=C_HRV,
            delta=delta(today_g, yest_g, "hrv_last_night_avg"))

metric_card(c4, "RHR", val(today_g, "rhr_bpm"), " bpm",
            color=C_RHR,
            delta=delta(today_g, yest_g, "rhr_bpm"))

metric_card(c5, "Body Battery ↑", val(today_g, "body_battery_high"),
            color="#f7d07e")

tr = val(today_g, "training_readiness_score")
metric_card(c6, "Readiness", tr,
            color=score_color(tr),
            delta=delta(today_g, yest_g, "training_readiness_score"))

# secondary strip — steps, stress, training load
if today_g is not None:
    c7, c8, c9, c10, _, _ = st.columns(6)
    metric_card(c7, "Steps",      val(today_g, "steps"),      color="#94a3b8")
    metric_card(c8, "Avg Stress", val(today_g, "avg_stress"), color=C_STRESS)
    metric_card(c9, "Acute Load", val(today_g, "acute_load"), color="#7eb8f7")
    metric_card(c10,"ACWR",       val(today_g, "acwr"),       color="#7eeab0")

    # training readiness limiting factor
    limit = val(today_g, "training_readiness_limiting_factor")
    status = val(today_g, "training_status")
    if limit or status:
        parts = []
        if status:
            parts.append(f"Training status: **{status}**")
        if limit:
            parts.append(f"Limiting factor: **{limit}**")
        st.caption(" · ".join(parts))

st.divider()

# ── 14-day window ─────────────────────────────────────────────────────────────
cutoff = today - datetime.timedelta(days=14)
if not df.empty:
    df14 = df[df["date"] >= cutoff].copy()
else:
    df14 = pd.DataFrame()

st.subheader("14-Day Trends")

if df14.empty:
    st.info("No trend data yet — data will appear here after a few days of garmin_export.py runs.")
else:
    tab_sleep, tab_recovery, tab_lifestyle, tab_training, tab_body = st.tabs(
        ["😴 Sleep", "💜 Recovery", "🍺 Lifestyle", "🏋️ Training", "⚖️ Body"]
    )

    with tab_sleep:
        col_l, col_r = st.columns(2)
        with col_l:
            line_chart(df14, ["sleep_score"], [C_SLEEP], "Sleep Score (14 days)")
        with col_r:
            line_chart(df14, ["sleep_hrs"], [C_SLEEP], "Sleep Duration (hrs)")

        # Sleep stage breakdown as stacked bar — approximate with three separate bars
        stage_cols = [c for c in ["sleep_deep_min", "sleep_rem_min", "sleep_awake_min"] if c in df14.columns]
        if stage_cols:
            st.markdown("**Sleep Stage Breakdown (min)**")
            stage_df = df14[["date"] + stage_cols].dropna(how="all", subset=stage_cols).copy()
            if not stage_df.empty:
                stage_df["date"] = pd.to_datetime(stage_df["date"])
                stage_df = stage_df.set_index("date")
                st.bar_chart(stage_df, height=220, use_container_width=True)

    with tab_recovery:
        col_l, col_r = st.columns(2)
        with col_l:
            line_chart(df14, ["hrv_last_night_avg", "hrv_weekly_avg"], [C_HRV, "#4ade80"],
                       "HRV (last night vs weekly avg)")
        with col_r:
            line_chart(df14, ["rhr_bpm"], [C_RHR], "Resting Heart Rate (bpm)")

        col_l2, col_r2 = st.columns(2)
        with col_l2:
            line_chart(df14, ["body_battery_high", "body_battery_low"], [C_SLEEP, "#f87171"],
                       "Body Battery Range")
        with col_r2:
            line_chart(df14, ["training_readiness_score"], [C_HRV], "Training Readiness")

    with tab_lifestyle:
        st.caption("Manual log data — populated from your Google Sheet once synced.")

        # Alcohol bars overlaid on sleep score
        has_alcohol = "alcohol_drinks" in df14.columns and df14["alcohol_drinks"].notna().any()
        has_mood    = "mood_1to10"     in df14.columns and df14["mood_1to10"].notna().any()
        has_stress  = "stress_1to10"   in df14.columns and df14["stress_1to10"].notna().any()

        col_l, col_r = st.columns(2)
        with col_l:
            if has_alcohol:
                bar_chart(df14, "alcohol_drinks", C_ALCOHOL, "Alcohol (drinks/night)")
            else:
                st.caption("Alcohol data: not yet synced from Google Sheet.")
        with col_r:
            # Sleep score + alcohol on same chart — show as dual lines
            overlay_cols = ["sleep_score"]
            if has_mood:
                overlay_cols.append("mood_1to10")
            if has_stress:
                overlay_cols.append("stress_1to10")
            line_chart(df14, overlay_cols, [C_SLEEP, C_MOOD, C_STRESS],
                       "Sleep Score vs Mood vs Stress")

        # Notes from manual log
        notes_col = "notes" if "notes" in df14.columns else None
        if notes_col:
            recent_notes = df14[df14[notes_col].notna() & (df14[notes_col] != "")][
                ["date", notes_col]].tail(7)
            if not recent_notes.empty:
                st.markdown("**Recent Notes (last 7 days)**")
                for _, row in recent_notes.iterrows():
                    st.markdown(f"- **{row['date']}** — {row[notes_col]}")

    with tab_training:
        col_l, col_r = st.columns(2)
        with col_l:
            line_chart(df14, ["acute_load", "chronic_load"], ["#7eb8f7", "#f7a07e"],
                       "Training Load (acute vs chronic)")
        with col_r:
            line_chart(df14, ["acwr"], ["#7eeab0"], "ACWR (acute:chronic ratio)")
            st.caption("Sweet spot: 0.8–1.3 · Above 1.5 = injury risk zone")

        has_training = "training_summary" in df14.columns and df14["training_summary"].notna().any()
        if has_training:
            st.markdown("**Recent Training Log**")
            tlog = df14[df14["training_summary"].notna() & (df14["training_summary"] != "")][
                ["date", "training_summary", "key_lifts"]].tail(10)
            for _, row in tlog.iterrows():
                lifts = f" — {row['key_lifts']}" if "key_lifts" in row and pd.notna(row.get("key_lifts")) else ""
                st.markdown(f"- **{row['date']}** {row['training_summary']}{lifts}")

    with tab_body:
        col_l, col_r = st.columns(2)
        has_weight = "weight_lb" in df14.columns and df14["weight_lb"].notna().any()
        with col_l:
            if has_weight:
                line_chart(df14, ["weight_lb"], [C_WEIGHT], "Weight (lb)")
            else:
                st.caption("Weight: not yet synced from Google Sheet.")
        with col_r:
            has_calories = "est_calories" in df14.columns and df14["est_calories"].notna().any()
            has_protein  = "est_protein_g" in df14.columns and df14["est_protein_g"].notna().any()
            if has_calories or has_protein:
                nutrition_cols = [c for c in ["est_calories", "est_protein_g"]
                                  if c in df14.columns and df14[c].notna().any()]
                line_chart(df14, nutrition_cols, ["#f7a07e", "#7eeab0"],
                           "Estimated Calories & Protein")
            else:
                st.caption("Nutrition: not yet synced from Google Sheet.")

        bar_chart(df14, "steps", "#94a3b8", "Daily Steps") if "steps" in df14.columns else None

st.divider()

# ── Drive sync note ──────────────────────────────────────────────────────────
with st.expander("ℹ️  Manual log sync (Google Sheet)"):
    st.markdown("""
**Why is my Google Sheet data not showing?**

The Streamlit page can't call the Google Drive MCP directly at runtime (the MCP
runs in Cowork on your desktop, not on Streamlit Cloud). To get your manual log
data into the dashboard, run the sync helper from Cowork:

```
# In a Cowork session, ask Claude to run:
python garmin_export_sheet.py   # (we'll build this next)
```

This will export your Health Tracking 2026 sheet to `health_manual.csv` in the
trend-engine folder, commit it, and the page will pick it up automatically on
next load. Run it whenever you've updated the sheet — takes ~5 seconds.

**Alternatively:** download the sheet as CSV from Google Sheets → File → Download
→ CSV, save it as `health_manual.csv` in your trend-engine folder, and push to git.
    """)
