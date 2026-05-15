"""
Week 4 Digest — Streamlit UI for scored arXiv papers
-----------------------------------------------------
Reads a results_*.csv produced by week2_run_scoring.py and renders a
filterable, sortable card view of scored papers.

DESIGN PHILOSOPHY:
- Refined-minimal, not maximalist. This is a 15-30 min/day personal tool;
  the score and the translation are the heroes, everything else is chrome.
- Cards, not tables. Translations are 400-1000 chars and need to breathe.
- Server-side filtering via pandas — fast even on 200+ rows, will scale to
  thousands before we'd need to add pagination or virtual scrolling.
- No state persistence across sessions. The only "state" is the CSV; if you
  want different defaults, edit the constants at top.

RUN:
    py -3.14 -m pip install streamlit pandas --user      # one-time
    py -3.14 -m streamlit run week4_digest.py

The browser will open automatically at http://localhost:8501.
To kill it: Ctrl-C in the terminal where streamlit is running.

WHAT IT EXPECTS:
- A CSV in the current directory matching results_*.csv (most recent picked
  by default), OR pass an explicit path via the sidebar override.
- Schema must match week2_run_scoring.py's OUTPUT_COLUMNS — specifically:
  id, domain, title, abstract, url, published, llm_*, prompt_version, model.

MULTI-RUN MODE (sidebar toggle):
- Merges all results_*.csv files in the current directory.
- Deduplicates on paper ID, keeping the most recently scored row per paper.
- Useful once you have several runs and want a unified best-of view.

NOT IN THIS VERSION (deferred to post-MVP per Week 4 spec):
- Pagination (renders fine at 200-300 rows)
- URL-based filter state (Streamlit's query_params API is fiddly)
- "Why this scored X" expandable explainers (rationale field already shows it)
- Citation velocity column (Semantic Scholar work, deferred indefinitely)
"""

from __future__ import annotations

import glob
import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st


# ---- CONFIG (edit defaults here) -------------------------------------------

RESULTS_GLOB = "results_*.csv"   # which files to find
DEFAULT_MIN_FINAL = 0.0          # show everything by default; user filters up
DEFAULT_SORT = "Final score (high → low)"

# Color tiers for the final-score badge. Refined editorial palette —
# warm amber for thesis, slate for watchlist, faded gray for skip.
FLAG_COLORS = {
    "thesis":    {"bg": "#7c2d12", "fg": "#fed7aa"},   # deep amber
    "watchlist": {"bg": "#1e293b", "fg": "#cbd5e1"},   # slate
    "longshot":  {"bg": "#1e3a2f", "fg": "#6ee7b7"},   # deep green — long horizon
    "skip":      {"bg": "#27272a", "fg": "#71717a"},   # muted graphite
}


# ---- DATA LOADING ----------------------------------------------------------

import re as _re   # local-scoped re; we only need it in the sort key

# Match YYYY-MM-DD anywhere in the filename. Captures the date string.
_DATE_IN_NAME = _re.compile(r"(\d{4}-\d{2}-\d{2})")


def _sort_key(path: str) -> tuple:
    """Sort key for results-CSV ordering.

    Original attempt used os.path.getmtime, which works locally but FAILS on
    Streamlit Cloud — a fresh `git clone` gives every file the same mtime,
    so mtime sort becomes effectively random. Pure alphabetical sort fails
    too: `results_top11_rescore.csv` sorts AFTER `results_2026-05-12_*.csv`
    because `t` > digits.

    The reliable signal is the date inside the filename. Extract it when
    present; fall back to alpha-by-name for files without a date so the
    order is deterministic. Undated files (e.g. `results_top11_rescore.csv`)
    sort BEFORE dated files — treating them as "older than any timestamped
    run" — so the latest dated file always wins as "latest run."
    Returns (has_date_flag, date_or_name, name) for stable ordering.
    """
    basename = os.path.basename(path)
    m = _DATE_IN_NAME.search(basename)
    if m:
        # has_date=1 → sorts after has_date=0 (undated)
        return (1, m.group(1), basename)
    return (0, basename, basename)


def _sort_by_mtime(paths: list[str]) -> list[str]:
    """Sort paths oldest → newest. Name-misleading wrapper kept for back-compat
    with any callers; actual sort uses _sort_key (date-in-filename + alpha)."""
    return sorted(paths, key=_sort_key)


def find_latest_results() -> str | None:
    """Find the most recent results_*.csv in the current directory (by mtime)."""
    matches = _sort_by_mtime(glob.glob(RESULTS_GLOB))
    return matches[-1] if matches else None


def find_all_results() -> list[str]:
    """Return all results_*.csv files sorted oldest → newest by mtime."""
    return _sort_by_mtime(glob.glob(RESULTS_GLOB))


# News pipeline produces news_results_*.csv. Schema is documented in
# week7_news_scoring.py (OUTPUT_COLUMNS) — different shape from research,
# so it gets its own loaders and renderers below.
NEWS_RESULTS_GLOB = "news_results_*.csv"


def find_all_news_results() -> list[str]:
    """Return all news_results_*.csv files sorted oldest → newest by mtime."""
    return _sort_by_mtime(glob.glob(NEWS_RESULTS_GLOB))


@st.cache_data(show_spinner=False)
def load_all_results(file_tuple: tuple[str, ...]) -> tuple[pd.DataFrame, int]:
    """
    Merge all results CSVs into one DataFrame, deduplicated by paper ID.
    Keeps the most recently scored row per paper (by run_timestamp).
    Returns (merged_df, num_runs).

    Cache key is a tuple of filenames — invalidates automatically when new
    results files appear (Streamlit re-hashes the tuple on each run).
    """
    frames = []
    for path in file_tuple:
        try:
            frames.append(pd.read_csv(path))
        except Exception:
            pass   # skip unreadable files silently

    if not frames:
        return pd.DataFrame(), 0

    combined = pd.concat(frames, ignore_index=True)

    # Sort by run_timestamp so the last row per ID is the most recent score.
    if "run_timestamp" in combined.columns:
        combined = combined.sort_values("run_timestamp", ascending=True)

    # Keep last occurrence of each ID (most recent score).
    combined = combined.drop_duplicates(subset=["id"], keep="last").reset_index(drop=True)

    return _normalize(combined), len(file_tuple)


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """
    Shared normalization applied to any loaded DataFrame — whether single-file
    or merged multi-run. Coerces types, parses vehicles list, parses dates.
    """
    # Coerce numeric columns — pandas reads them as int/float automatically
    # but we guard against the occasional cell that comes through as string.
    for col in ("llm_maturation", "llm_profit_mechanism", "llm_retail_accessibility",
                "llm_specificity", "llm_horizon", "llm_final"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Parse public_vehicles: stored as JSON-stringified list. Decode to list.
    # Defensive: empty string and "[]" both → empty list.
    def parse_vehicles(v):
        if not isinstance(v, str) or not v.strip():
            return []
        try:
            parsed = json.loads(v)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, ValueError):
            return []
    df["vehicles_list"] = df["llm_public_vehicles"].apply(parse_vehicles)

    # Parse published as datetime — ISO format with Z suffix.
    # errors="coerce" → NaT for malformed entries, which we'll display blank.
    df["published_dt"] = pd.to_datetime(df["published"], errors="coerce", utc=True)
    df["published_date"] = df["published_dt"].dt.strftime("%Y-%m-%d").fillna("")

    return df


@st.cache_data(show_spinner=False)
def load_results(path: str) -> pd.DataFrame:
    """
    Load and normalize a single results CSV. Cached so filter changes
    don't re-read the file. The cache invalidates if `path` changes.
    """
    return _normalize(pd.read_csv(path))


# ---- UI HELPERS ------------------------------------------------------------

def render_score_badge(final: float, flag: str) -> str:
    """Big colored final-score badge. Returned as inline HTML for st.markdown."""
    colors = FLAG_COLORS.get(flag, FLAG_COLORS["skip"])
    return f"""
    <div style="
        background: {colors['bg']};
        color: {colors['fg']};
        border-radius: 12px;
        padding: 14px 18px;
        text-align: center;
        font-family: 'Georgia', serif;
        min-width: 92px;
    ">
        <div style="font-size: 32px; font-weight: 700; line-height: 1;">{final:g}</div>
        <div style="font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase;
                    opacity: 0.85; margin-top: 4px;">{flag}</div>
    </div>
    """


SUBSCORE_TOOLTIPS = {
    "MAT": (
        "Maturation — Does this read like consolidating work (high) or first-discovery novelty (low)? "
        "Low (1-3): 'We introduce / propose a novel framework.' "
        "Mid (4-6): Solid incremental result, trend unclear. "
        "High (7-10): 'We confirm / extend prior work' — explicitly the Nth result on an established line."
    ),
    "PROF": (
        "Profit Mechanism — Is there an identifiable someone who makes money, and how? "
        "Low (1-3): Pure theory, OR benefit diffuses across the industry with no pricing power for any single player. "
        "Mid (4-6): Plausible path but speculative, or benefit captured only by diversified giants. "
        "High (7-10): Explicit value-capture mechanism — a process sold, a device with a moat, a named beneficiary. "
        "Note: 'used by lots of companies' scores LOW — commodity enablers don't create pricing power."
    ),
    "RET": (
        "Retail Accessibility — Can a retail investor actually bet on this via a public vehicle? "
        "Low (1-3): Benefits only private companies, labs, or conglomerates where the signal is swamped (e.g. GOOGL). "
        "Mid (4-6): Sector ETF or crowded mid-caps — signal is real but diluted. "
        "High (7-10): Clean pure-play — one or two public names where this paper's mechanism is load-bearing. "
        "HARD RULE: If this score is under 4, final score caps at 5 and flag cannot be 'thesis'."
    ),
    "SPEC": (
        "Specificity — Is the claim concrete enough to be load-bearing? "
        "Low (1-3): Vague direction, no numbers, survey-like. "
        "Mid (4-6): Some benchmarks but claims are hedged or limited. "
        "High (7-10): Specific quantitative improvements against named baselines, reproducible methodology."
    ),
    "HRZ": (
        "Horizon — Long-term transformative ceiling of the TOPIC AREA, not this specific paper. "
        "Score the domain's potential if it fully succeeds over 10-20 years. "
        "Low (1-3): Narrow improvement to an existing tool — even full success doesn't move the needle at scale. "
        "Mid (4-6): Meaningful but bounded — improves a large industry without restructuring it. "
        "High (7-8): Reshapes a major sector or creates a large new one. E.g. humanoid robotics, solid-state batteries, fusion. "
        "Max (9-10): Civilizational-scale. E.g. AGI, asteroid mining, longevity escape velocity, brain-computer interfaces. "
        "A high score here with low near-term actionability = 'longshot' flag, not skip."
    ),
}


def render_subscores(row) -> str:
    """Compact row of sub-scores below the title. Hover each pill for the scoring definition."""
    parts = [
        ("MAT",  int(row["llm_maturation"]),  False),
        ("PROF", int(row["llm_profit_mechanism"]), False),
        ("RET",  int(row["llm_retail_accessibility"]), False),
        ("SPEC", int(row["llm_specificity"]), False),
        # HRZ is horizon — rendered with green tint to signal it's a different axis
        ("HRZ",  int(row["llm_horizon"]) if "llm_horizon" in row and pd.notna(row.get("llm_horizon")) else None, True),
    ]
    pills = []
    for label, val, is_horizon in parts:
        if val is None:
            continue   # skip HRZ for older scored rows that predate v0.3
        opacity = "0.45" if val < 4 else "0.95"
        tooltip = SUBSCORE_TOOLTIPS.get(label, "").replace('"', "&quot;")
        # Horizon pill gets a subtle green background to distinguish it visually
        bg = "rgba(52,120,80,0.18)" if is_horizon else "rgba(120,120,140,0.12)"
        pills.append(f"""
            <span title="{tooltip}" style="
                display: inline-block;
                padding: 3px 10px;
                margin-right: 6px;
                background: {bg};
                border-radius: 999px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 12px;
                opacity: {opacity};
                cursor: help;
            "><b>{label}</b> {val}</span>""")
    return f'<div style="margin: 6px 0 14px 0;">{"".join(pills)}</div>'


def render_footer(row) -> str:
    """Small footer with vehicles, arxiv link, date, time-to-thesis."""
    vehicles = row["vehicles_list"]
    vehicles_html = ""
    if vehicles:
        chips = " ".join(
            f'<span style="background: rgba(124,45,18,0.18); color: #fdba74; '
            f'padding: 2px 8px; border-radius: 4px; font-family: monospace; '
            f'font-size: 12px; margin-right: 4px;">{v}</span>'
            for v in vehicles
        )
        vehicles_html = f'<span style="margin-right: 16px;">{chips}</span>'

    ttt = row["llm_time_to_thesis"]
    date_str = row["published_date"]
    url = row["url"]

    return f"""
    <div style="
        margin-top: 12px;
        padding-top: 10px;
        border-top: 1px solid rgba(120,120,140,0.18);
        font-size: 12px;
        color: #94a3b8;
        display: flex;
        flex-wrap: wrap;
        gap: 6px 0;
        align-items: center;
    ">
        {vehicles_html}
        <span style="margin-right: 16px;">⏱ {ttt}</span>
        <span style="margin-right: 16px;">📅 {date_str}</span>
        <a href="{url}" target="_blank" style="color: #94a3b8; text-decoration: underline;">
            arxiv ↗
        </a>
    </div>
    """


SCORE_LABELS = {
    "maturation":          ("MAT",  "Maturation"),
    "profit_mechanism":    ("PROF", "Profit Mechanism"),
    "retail_accessibility":("RET",  "Retail Accessibility"),
    "specificity":         ("SPEC", "Specificity"),
    "horizon":             ("HRZ",  "Horizon"),
}


def get_score_explanations(row) -> dict:
    """Parse llm_score_explanations from JSON string. Returns {} if missing/malformed."""
    raw = row.get("llm_score_explanations", "")
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, ValueError):
        return {}


def render_detail(row) -> None:
    """Full detail page for a single paper, shown when title is clicked."""

    # Back button
    if st.button("← Back to digest", key="back"):
        st.session_state.selected_id = None
        st.rerun()

    st.markdown('<div style="margin-top: 24px;"></div>', unsafe_allow_html=True)

    # Header: domain + title + badge
    col_title, col_badge = st.columns([8, 1.2])
    with col_badge:
        st.markdown(render_score_badge(row["llm_final"], row["llm_flag"]),
                    unsafe_allow_html=True)
    with col_title:
        st.markdown(
            f'<div style="font-family: monospace; font-size: 11px; letter-spacing: 0.15em; '
            f'color: #64748b; text-transform: uppercase; margin-bottom: 6px;">{row["domain"]}</div>'
            f'<div style="font-family: Georgia, serif; font-size: 24px; line-height: 1.3; '
            f'font-weight: 600; color: #e2e8f0;">{row["title"]}</div>',
            unsafe_allow_html=True,
        )

    st.markdown(render_footer(row), unsafe_allow_html=True)
    st.markdown('<div style="margin-top: 28px;"></div>', unsafe_allow_html=True)

    # Translation
    st.markdown(
        f'<div style="font-size: 15px; line-height: 1.6; color: #cbd5e1; '
        f'margin-bottom: 32px;">{row["llm_translation"]}</div>',
        unsafe_allow_html=True,
    )

    # Score breakdown — definition + paper-specific explanation per axis
    st.markdown(
        '<div style="font-family: Georgia, serif; font-size: 18px; '
        'color: #e2e8f0; margin-bottom: 16px;">Score Breakdown</div>',
        unsafe_allow_html=True,
    )

    explanations = get_score_explanations(row)
    score_keys = [
        ("maturation",           "llm_maturation"),
        ("profit_mechanism",     "llm_profit_mechanism"),
        ("retail_accessibility", "llm_retail_accessibility"),
        ("specificity",          "llm_specificity"),
        ("horizon",              "llm_horizon"),
    ]

    for key, col in score_keys:
        val = row.get(col)
        if val is None or (isinstance(val, float) and pd.isna(val)):
            continue   # skip axes not present in older scored rows

        abbr, label = SCORE_LABELS[key]
        tooltip = SUBSCORE_TOOLTIPS.get(abbr, "")
        explanation = explanations.get(key, "")
        is_horizon = key == "horizon"
        bg = "rgba(52,120,80,0.10)" if is_horizon else "rgba(120,120,140,0.07)"
        border = "rgba(52,120,80,0.3)" if is_horizon else "rgba(120,120,140,0.2)"

        st.markdown(f"""
        <div style="
            background: {bg};
            border: 1px solid {border};
            border-radius: 10px;
            padding: 14px 18px;
            margin-bottom: 12px;
        ">
            <div style="display: flex; align-items: baseline; gap: 12px; margin-bottom: 6px;">
                <span style="font-family: 'JetBrains Mono', monospace; font-size: 11px;
                             letter-spacing: 0.12em; color: #64748b;">{abbr}</span>
                <span style="font-family: Georgia, serif; font-size: 16px;
                             color: #e2e8f0; font-weight: 600;">{label}</span>
                <span style="font-family: 'JetBrains Mono', monospace; font-size: 22px;
                             color: #e2e8f0; font-weight: 700; margin-left: auto;">{int(val)}</span>
            </div>
            <div style="font-size: 12px; color: #64748b; margin-bottom: {"8px" if explanation else "0"};">
                {tooltip}
            </div>
            {"" if not explanation else f'<div style="font-size: 13px; color: #94a3b8; font-style: italic; border-top: 1px solid rgba(120,120,140,0.15); padding-top: 8px;">{explanation}</div>'}
        </div>
        """, unsafe_allow_html=True)

    # Rationale + metadata
    st.markdown('<div style="margin-top: 24px;"></div>', unsafe_allow_html=True)
    st.markdown(f"**Rationale:** *{row.get('llm_rationale', '')}*")
    st.caption(
        f"Prompt {row.get('prompt_version', '?')} · "
        f"{row.get('model', '?')} · "
        f"id `{row['id']}`"
    )


def render_card(row) -> None:
    """Render a single paper as a card. Uses two columns: text + score badge."""
    with st.container():
        st.markdown('<div style="margin-top: 24px;"></div>', unsafe_allow_html=True)
        col_text, col_score = st.columns([8, 1.2])

        with col_score:
            st.markdown(render_score_badge(row["llm_final"], row["llm_flag"]),
                        unsafe_allow_html=True)

        with col_text:
            # Domain tag
            st.markdown(
                f'<div style="font-family: monospace; font-size: 11px; '
                f'letter-spacing: 0.15em; color: #64748b; '
                f'text-transform: uppercase; margin-bottom: 4px;">{row["domain"]}</div>',
                unsafe_allow_html=True,
            )

            # Title as a clickable button — opens detail page
            if st.button(row["title"], key=f"title_{row['id']}",
                         help="Click to see full score breakdown"):
                st.session_state.selected_id = row["id"]
                st.rerun()

            # Sub-scores
            st.markdown(render_subscores(row), unsafe_allow_html=True)

            # Translation — the most important field
            st.markdown(
                f'<div style="font-size: 14px; line-height: 1.55; color: #cbd5e1;">'
                f'{row["llm_translation"]}</div>',
                unsafe_allow_html=True,
            )

        # Footer rendered outside the column so unsafe_allow_html is always honoured.
        # Some Streamlit versions silently ignore it inside st.columns contexts.
        st.markdown(render_footer(row), unsafe_allow_html=True)

        # Soft separator between cards
        st.markdown(
            '<div style="margin-top: 24px; '
            'border-bottom: 1px solid rgba(120,120,140,0.12);"></div>',
            unsafe_allow_html=True,
        )


# ---- NEWS DATA + RENDERING -------------------------------------------------

# Source-key labels and color tints for the source pill on news cards.
# Keys must match what the fetchers write to the `source` column.
NEWS_SOURCE_LABELS = {
    "hackernews":         "HN",
    "npr":                "NPR",
    "reuters_via_google": "Reuters",
    "fed":                "Fed",
    # Legacy keys (in case earlier runs landed before the source rename)
    "reuters":            "Reuters (legacy)",
    "ap":                 "AP (legacy)",
}

# Flag colors for news cards. Different palette from research flags so the
# eye doesn't conflate "thesis" with "read" (different action implications).
NEWS_FLAG_COLORS = {
    "read": {"bg": "#1e3a5f", "fg": "#bfdbfe"},   # deep blue — primary action
    "skim": {"bg": "#1e293b", "fg": "#cbd5e1"},   # slate
    "skip": {"bg": "#27272a", "fg": "#71717a"},   # graphite
}


def _normalize_news(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce types + parse dates for news_results_*.csv. Mirrors _normalize for research."""
    for col in ("llm_signal_strength", "llm_investment_relevance", "llm_market_impact",
                "hn_score", "hn_comments"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    # posted_at is ISO with timezone; coerce to NaT on bad values
    df["posted_dt"] = pd.to_datetime(df.get("posted_at", ""), errors="coerce", utc=True)
    df["posted_date"] = df["posted_dt"].dt.strftime("%Y-%m-%d %H:%M").fillna("")
    # market_impact may be missing on v0.1 rows — fill with 0 so filters don't NaN-blow-up
    if "llm_market_impact" not in df.columns:
        df["llm_market_impact"] = 0
    return df


@st.cache_data(show_spinner=False)
def load_news_results(path: str) -> pd.DataFrame:
    """Load + normalize a single news_results_*.csv."""
    return _normalize_news(pd.read_csv(path))


@st.cache_data(show_spinner=False)
def load_all_news_results(file_tuple: tuple[str, ...]) -> tuple[pd.DataFrame, int]:
    """Merge all news CSVs, dedupe by ID (latest score wins). Returns (df, num_runs)."""
    frames = []
    for path in file_tuple:
        try:
            frames.append(pd.read_csv(path))
        except Exception:
            pass
    if not frames:
        return pd.DataFrame(), 0
    combined = pd.concat(frames, ignore_index=True)
    if "run_timestamp" in combined.columns:
        combined = combined.sort_values("run_timestamp", ascending=True)
    combined = combined.drop_duplicates(subset=["id"], keep="last").reset_index(drop=True)
    return _normalize_news(combined), len(file_tuple)


def render_news_score_badge(market_impact: int | float, flag: str) -> str:
    """Big colored badge for news cards. The HEADLINE number is market_impact,
    not signal_strength — that's the axis the operator added to catch macro
    news that's easy to overlook."""
    colors = NEWS_FLAG_COLORS.get(flag, NEWS_FLAG_COLORS["skip"])
    val = int(market_impact) if pd.notna(market_impact) else 0
    return f"""
    <div style="
        background: {colors['bg']};
        color: {colors['fg']};
        border-radius: 12px;
        padding: 14px 18px;
        text-align: center;
        font-family: 'Georgia', serif;
        min-width: 92px;
    ">
        <div style="font-size: 32px; font-weight: 700; line-height: 1;">{val}</div>
        <div style="font-size: 9px; letter-spacing: 0.1em; text-transform: uppercase;
                    opacity: 0.85; margin-top: 4px;">market</div>
        <div style="font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase;
                    opacity: 0.85; margin-top: 2px;">{flag}</div>
    </div>
    """


def render_news_subscores(row) -> str:
    """Compact pills for the news axes: SIG / REL / MKT.
    MKT also appears as the badge headline; showing it here too gives quick
    cross-axis comparison without scanning back to the badge."""
    parts = [
        ("SIG", row.get("llm_signal_strength"),
         "Signal Strength — quality of the story itself, regardless of fit. "
         "1-3 noise/PR · 4-6 incremental · 7-8 substantive primary source · 9-10 paradigm shift"),
        ("REL", row.get("llm_investment_relevance"),
         "Investment Relevance — fit to operator's thesis space (AI/EV/batteries/semis/robotics). "
         "1-3 unrelated · 4-6 sector-context · 7-8 named-name impact · 9-10 hard catalyst"),
        ("MKT", row.get("llm_market_impact"),
         "Market Impact — broad-market consequence regardless of personal fit. "
         "Catches macro/political news where chain-of-reasoning to the portfolio is non-obvious."),
    ]
    pills = []
    for label, val, tip in parts:
        if val is None or pd.isna(val):
            continue
        v = int(val)
        opacity = "0.45" if v < 4 else "0.95"
        bg = "rgba(40,80,140,0.18)" if label == "MKT" else "rgba(120,120,140,0.12)"
        tip_safe = tip.replace('"', "&quot;")
        pills.append(f"""
            <span title="{tip_safe}" style="
                display: inline-block;
                padding: 3px 10px;
                margin-right: 6px;
                background: {bg};
                border-radius: 999px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 12px;
                opacity: {opacity};
                cursor: help;
            "><b>{label}</b> {v}</span>""")
    return f'<div style="margin: 6px 0 14px 0;">{"".join(pills)}</div>'


def render_news_footer(row) -> str:
    """Source pill, posted timestamp, link out."""
    src_key = row.get("source", "")
    src_label = NEWS_SOURCE_LABELS.get(src_key, src_key)
    posted = row.get("posted_date", "")
    url = row.get("url", "")
    tag = row.get("llm_tag", "")
    return f"""
    <div style="
        margin-top: 12px;
        padding-top: 10px;
        border-top: 1px solid rgba(120,120,140,0.18);
        font-size: 12px;
        color: #94a3b8;
        display: flex;
        flex-wrap: wrap;
        gap: 6px 0;
        align-items: center;
    ">
        <span style="background: rgba(40,80,140,0.18); color: #93c5fd;
                     padding: 2px 8px; border-radius: 4px; font-family: monospace;
                     font-size: 11px; margin-right: 12px;">{src_label}</span>
        <span style="background: rgba(120,120,140,0.12); color: #cbd5e1;
                     padding: 2px 8px; border-radius: 4px; font-family: monospace;
                     font-size: 11px; margin-right: 12px;">#{tag}</span>
        <span style="margin-right: 16px;">📅 {posted}</span>
        <a href="{url}" target="_blank" style="color: #94a3b8; text-decoration: underline;">
            open ↗
        </a>
    </div>
    """


def render_news_card(row) -> None:
    """Render a single news item as a card. Mirrors the research card layout."""
    with st.container():
        st.markdown('<div style="margin-top: 24px;"></div>', unsafe_allow_html=True)
        col_text, col_score = st.columns([8, 1.2])

        with col_score:
            st.markdown(
                render_news_score_badge(row.get("llm_market_impact", 0), row.get("llm_flag", "skip")),
                unsafe_allow_html=True,
            )

        with col_text:
            # Tag/source row above the title — quick visual filter cue
            st.markdown(
                f'<div style="font-family: monospace; font-size: 11px; '
                f'letter-spacing: 0.15em; color: #64748b; '
                f'text-transform: uppercase; margin-bottom: 4px;">'
                f'{NEWS_SOURCE_LABELS.get(row.get("source", ""), row.get("source", ""))}'
                f' · {row.get("llm_tag", "")}'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Title — plain link straight to source. No detail page yet
            # for news (deferred); keeping it simple beats half-built.
            url = row.get("url", "")
            title = row.get("title", "")
            st.markdown(
                f'<div style="font-family: Georgia, serif; font-size: 18px; '
                f'line-height: 1.35; font-weight: 600; margin-bottom: 4px;">'
                f'<a href="{url}" target="_blank" style="color: #e2e8f0; text-decoration: none;">'
                f'{title}</a></div>',
                unsafe_allow_html=True,
            )

            st.markdown(render_news_subscores(row), unsafe_allow_html=True)

            # Translation — the LLM's "why this matters" sentence
            translation = row.get("llm_translation", "")
            st.markdown(
                f'<div style="font-size: 14px; line-height: 1.55; color: #cbd5e1;">'
                f'{translation}</div>',
                unsafe_allow_html=True,
            )

        st.markdown(render_news_footer(row), unsafe_allow_html=True)
        st.markdown(
            '<div style="margin-top: 24px; '
            'border-bottom: 1px solid rgba(120,120,140,0.12);"></div>',
            unsafe_allow_html=True,
        )


# ---- MAIN APP --------------------------------------------------------------

def render_research_tab() -> None:
    """The original digest body — research papers from results_*.csv.
    Sidebar widgets are scoped here; the News tab has its own."""

    st.sidebar.header("Source")

    all_result_files = find_all_results()
    if not all_result_files:
        st.error("No results_*.csv found in the current directory. "
                 "Run week2_run_scoring.py first.")
        st.stop()

    # Run-scope selector — three mutually exclusive views:
    #   "Single file"      — pick any results_*.csv via the text box below
    #   "Latest run only"  — pinned to the newest results_*.csv (what shipped today)
    #   "All runs merged"  — every CSV combined, deduped by paper ID (latest score wins)
    run_scope = st.sidebar.radio(
        "Run scope",
        options=["Single file", "Latest run only", "All runs merged"],
        index=1,   # default: latest run — most common "what's new" use case
        help=(
            "Single file: choose any one CSV. "
            "Latest run only: just the most recent scoring run. "
            "All runs merged: cross-run best-of view, deduped by paper ID."
        ),
        key="research_run_scope",
    )

    num_runs = 1
    multi_run = run_scope == "All runs merged"

    if multi_run:
        df, num_runs = load_all_results(tuple(all_result_files))
        if df.empty:
            st.error("Could not load any results files.")
            st.stop()
        st.sidebar.caption(f"Merged **{num_runs}** run(s) · **{len(df)}** unique papers")
    elif run_scope == "Latest run only":
        latest_path = all_result_files[-1]
        df = load_results(latest_path)
        st.sidebar.caption(f"Loaded **{len(df)}** papers from `{Path(latest_path).name}`")
        if "run_timestamp" in df.columns and len(df) > 0:
            st.sidebar.caption(f"Scored: {df['run_timestamp'].iloc[0]}")
    else:
        default_path = all_result_files[-1]
        csv_path = st.sidebar.text_input("Results CSV", value=default_path,
                                         help="Path to a results_*.csv file.",
                                         key="research_csv_path")
        if not Path(csv_path).exists():
            st.error(f"File not found: {csv_path}")
            st.stop()
        df = load_results(csv_path)
        st.sidebar.caption(f"Loaded **{len(df)}** papers from `{Path(csv_path).name}`")
        if "run_timestamp" in df.columns and len(df) > 0:
            st.sidebar.caption(f"Scored: {df['run_timestamp'].iloc[0]}")

    # ---- Filters ----
    st.sidebar.markdown("---")
    st.sidebar.header("Filters")

    all_domains = sorted(df["domain"].unique().tolist())
    selected_domains = st.sidebar.multiselect(
        "Domains", all_domains, default=all_domains, key="research_domains",
    )

    all_flags = ["thesis", "watchlist", "longshot", "skip"]
    selected_flags = st.sidebar.multiselect(
        "Flags", all_flags, default=["thesis", "watchlist", "longshot"],
        help="thesis = act today · watchlist = revisit in 3-6 months · longshot = high horizon, 5-20yr hold · skip = noise",
        key="research_flags",
    )

    min_final = st.sidebar.slider(
        "Min final score", min_value=0.0, max_value=10.0,
        value=DEFAULT_MIN_FINAL, step=0.5, key="research_min_final",
    )

    require_vehicle = st.sidebar.checkbox(
        "Only papers with named public vehicle(s)", value=False,
        help="Hides papers where the LLM couldn't name a public-equity exposure.",
        key="research_require_vehicle",
    )

    sort_options = {
        "Final score (high → low)": ("llm_final", False),
        "Final score (low → high)": ("llm_final", True),
        "Date (newest → oldest)":   ("published_dt", False),
        "Date (oldest → newest)":   ("published_dt", True),
        "Domain (A → Z)":           ("domain", True),
    }
    sort_choice = st.sidebar.selectbox("Sort by", list(sort_options.keys()),
                                       index=0, key="research_sort")
    sort_col, sort_asc = sort_options[sort_choice]

    # ---- Apply filters ----
    filtered = df[
        df["domain"].isin(selected_domains)
        & df["llm_flag"].isin(selected_flags)
        & (df["llm_final"] >= min_final)
    ].copy()

    if require_vehicle:
        filtered = filtered[filtered["vehicles_list"].apply(lambda v: len(v) > 0)]

    filtered = filtered.sort_values(by=sort_col, ascending=sort_asc, kind="stable")

    # ---- Detail page ----
    # If a paper title was clicked, show the detail view INSIDE the research tab.
    # The detail page short-circuits the card list but stays within this tab so
    # the user doesn't get yanked out of context.
    if st.session_state.selected_id:
        match = df[df["id"] == st.session_state.selected_id]
        if not match.empty:
            render_detail(match.iloc[0])
            return
        else:
            st.session_state.selected_id = None

    # ---- Counts header ----
    flag_counts = filtered["llm_flag"].value_counts()
    run_label = f" across {num_runs} runs" if multi_run and num_runs > 1 else ""
    counts_text = (
        f"**{len(filtered)}** papers{run_label} · "
        f"thesis: {flag_counts.get('thesis', 0)} · "
        f"watchlist: {flag_counts.get('watchlist', 0)} · "
        f"longshot: {flag_counts.get('longshot', 0)} · "
        f"skip: {flag_counts.get('skip', 0)}"
    )
    st.markdown(counts_text)

    if len(filtered) == 0:
        st.info("No papers match the current filters. Loosen the filters in the sidebar.")
        return

    for _, row in filtered.iterrows():
        render_card(row)


def render_news_tab() -> None:
    """News tab — items from news_results_*.csv.
    Smaller filter set than research; news items have fewer axes worth filtering on."""

    st.sidebar.header("Source")

    all_news_files = find_all_news_results()
    if not all_news_files:
        st.info(
            "No news_results_*.csv found yet. Run the news pipeline:\n\n"
            "```\npy -3.14 week7_news_fetcher.py\n"
            "py -3.14 week7_news_fetcher_rss.py\n"
            "py -3.14 week7_news_scoring.py --input <news_*.csv>\n```"
        )
        return

    run_scope = st.sidebar.radio(
        "Run scope",
        options=["Single file", "Latest run only", "All runs merged"],
        index=1,
        help=(
            "Single file: choose any one news CSV. "
            "Latest run only: most recent news scoring run. "
            "All runs merged: cross-run view, deduped by item ID."
        ),
        key="news_run_scope",
    )

    multi_run = run_scope == "All runs merged"
    num_runs = 1
    if multi_run:
        df, num_runs = load_all_news_results(tuple(all_news_files))
        if df.empty:
            st.error("Could not load any news_results files.")
            return
        st.sidebar.caption(f"Merged **{num_runs}** run(s) · **{len(df)}** unique items")
    elif run_scope == "Latest run only":
        latest_path = all_news_files[-1]
        df = load_news_results(latest_path)
        st.sidebar.caption(f"Loaded **{len(df)}** items from `{Path(latest_path).name}`")
    else:
        default_path = all_news_files[-1]
        csv_path = st.sidebar.text_input("News CSV", value=default_path,
                                         help="Path to a news_results_*.csv file.",
                                         key="news_csv_path")
        if not Path(csv_path).exists():
            st.error(f"File not found: {csv_path}")
            return
        df = load_news_results(csv_path)
        st.sidebar.caption(f"Loaded **{len(df)}** items from `{Path(csv_path).name}`")

    st.sidebar.markdown("---")
    st.sidebar.header("Filters")

    all_sources = sorted(df["source"].dropna().unique().tolist())
    selected_sources = st.sidebar.multiselect(
        "Sources", all_sources, default=all_sources,
        format_func=lambda s: NEWS_SOURCE_LABELS.get(s, s),
        key="news_sources",
    )

    all_news_tags = sorted(df["llm_tag"].dropna().unique().tolist())
    selected_tags = st.sidebar.multiselect(
        "Tags", all_news_tags, default=all_news_tags, key="news_tags",
    )

    all_news_flags = ["read", "skim", "skip"]
    selected_news_flags = st.sidebar.multiselect(
        "Flags", all_news_flags, default=["read", "skim"],
        help="read = open the link · skim = quick glance · skip = noise",
        key="news_flag_filter",
    )

    min_market = st.sidebar.slider(
        "Min market_impact", min_value=0, max_value=10, value=0, step=1,
        help="Filter out items with low broad-market consequence. "
             "Useful for surfacing the macro/political stories the new axis was added to catch.",
        key="news_min_market",
    )

    news_sort_options = {
        "Market impact (high → low)":     ("llm_market_impact", False),
        "Investment relevance (high → low)": ("llm_investment_relevance", False),
        "Signal strength (high → low)":   ("llm_signal_strength", False),
        "Posted (newest → oldest)":       ("posted_dt", False),
    }
    news_sort_choice = st.sidebar.selectbox(
        "Sort by", list(news_sort_options.keys()), index=0, key="news_sort",
    )
    n_sort_col, n_sort_asc = news_sort_options[news_sort_choice]

    # ---- Apply filters ----
    filtered = df[
        df["source"].isin(selected_sources)
        & df["llm_tag"].isin(selected_tags)
        & df["llm_flag"].isin(selected_news_flags)
        & (df["llm_market_impact"].fillna(0) >= min_market)
    ].copy()

    filtered = filtered.sort_values(by=n_sort_col, ascending=n_sort_asc, kind="stable")

    # ---- Counts header ----
    flag_counts = filtered["llm_flag"].value_counts()
    run_label = f" across {num_runs} runs" if multi_run and num_runs > 1 else ""
    st.markdown(
        f"**{len(filtered)}** news items{run_label} · "
        f"read: {flag_counts.get('read', 0)} · "
        f"skim: {flag_counts.get('skim', 0)} · "
        f"skip: {flag_counts.get('skip', 0)}"
    )

    if len(filtered) == 0:
        st.info("No news items match the current filters. Loosen the filters in the sidebar.")
        return

    for _, row in filtered.iterrows():
        render_news_card(row)


# ---- PORTFOLIO TAB (Week 8) ------------------------------------------------

# yfinance wrapper guarded the same way the analytics page guards shadow_portfolio —
# Portfolio tab renders an install hint instead of crashing if yfinance is missing.
try:
    from yfinance_wrapper import (
        get_current_price as _yf_current,
        get_history as _yf_history,
        yfinance_available as _yf_available,
    )
    _PORTFOLIO_AVAILABLE = True
except Exception as _pf_exc:
    _PORTFOLIO_AVAILABLE = False
    _PORTFOLIO_IMPORT_ERR = str(_pf_exc)

HOLDINGS_PATH = "holdings.csv"
HOLDINGS_COLUMNS = [
    "ticker", "broker", "shares", "cost_basis_per_share", "purchase_date", "notes",
]


def _load_holdings() -> pd.DataFrame:
    """Read holdings.csv; return empty-with-schema if missing."""
    p = Path(HOLDINGS_PATH)
    if not p.exists():
        return pd.DataFrame(columns=HOLDINGS_COLUMNS)
    try:
        df = pd.read_csv(p)
    except Exception:
        return pd.DataFrame(columns=HOLDINGS_COLUMNS)
    for col in HOLDINGS_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df["shares"] = pd.to_numeric(df["shares"], errors="coerce").fillna(0.0)
    df["cost_basis_per_share"] = pd.to_numeric(
        df["cost_basis_per_share"], errors="coerce"
    ).fillna(0.0)
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df["broker"] = df["broker"].astype(str).str.strip()
    return df[df["ticker"].str.len() > 0].reset_index(drop=True)


@st.cache_data(ttl=3600, show_spinner=False)
def _portfolio_prices(tickers_tuple: tuple) -> dict:
    """Cached batch lookup — keyed on the sorted ticker tuple."""
    return {t: _yf_current(t) for t in tickers_tuple}


@st.cache_data(ttl=3600, show_spinner=False)
def _portfolio_history(ticker: str, period: str) -> pd.DataFrame:
    """Cached per-ticker historical pull for the chart."""
    return _yf_history(ticker, period=period)


def render_portfolio_tab() -> None:
    """
    Manual-holdings view: Webull + ETrade positions driven by holdings.csv.
    Top: table with computed market value + gain/loss. Bottom: per-ticker
    historical chart with period toggle. Refresh button clears price cache.

    Strict scope: no real-time tick, no options, no crypto, no dividends,
    no tax lots, no broker auto-sync. See charter section 10 item 9 plus
    2026-05-15 decision log entry.
    """
    st.markdown(
        '<h2 style="margin-top: 0;">Portfolio</h2>'
        '<div style="color:#64748b; font-size:13px; margin-bottom:16px;">'
        'Manual holdings - yfinance prices (delayed, not real-time) - '
        'edit <code>holdings.csv</code> to update positions.'
        '</div>',
        unsafe_allow_html=True,
    )

    if not _PORTFOLIO_AVAILABLE:
        st.info(
            "yfinance wrapper not available. "
            f"Import error: `{_PORTFOLIO_IMPORT_ERR}`. "
            "Install yfinance: `py -3.14 -m pip install yfinance --user`"
        )
        return

    holdings = _load_holdings()

    if holdings.empty:
        st.info(
            "No holdings yet - add rows to **`holdings.csv`** with columns:  \n"
            "`ticker, broker, shares, cost_basis_per_share, purchase_date, notes`.\n\n"
            "Then click **Refresh prices** below."
        )
        if st.button("Refresh prices", key="portfolio_refresh_empty"):
            _portfolio_prices.clear()
            _portfolio_history.clear()
            st.rerun()
        return

    st.sidebar.header("Portfolio filters")
    brokers = sorted(holdings["broker"].dropna().unique().tolist())
    broker_filter = st.sidebar.selectbox(
        "Broker",
        options=["All"] + brokers,
        index=0,
        key="portfolio_broker_filter",
    )
    if broker_filter != "All":
        holdings = holdings[holdings["broker"] == broker_filter].reset_index(drop=True)
        if holdings.empty:
            st.info(f"No holdings under broker '{broker_filter}'.")
            return

    # Cross-broker rollup toggle. Default rolled up so a ticker held at
    # both brokers appears as one position; "By broker" splits them out.
    # Hidden / disabled when a specific broker is already selected.
    rollup_mode = st.sidebar.radio(
        "View",
        options=["Rolled up", "By broker"],
        index=0,
        key="portfolio_rollup_mode",
        help="Rolled up: one row per ticker, shares summed across brokers, "
             "cost basis weighted-averaged. By broker: one row per (ticker, broker).",
        disabled=(broker_filter != "All"),
    )

    col_btn, col_caption = st.columns([1, 4])
    with col_btn:
        if st.button("Refresh prices", key="portfolio_refresh"):
            _portfolio_prices.clear()
            _portfolio_history.clear()
            st.rerun()
    with col_caption:
        st.caption(
            f"{len(holdings)} position(s) - prices cached for 1h - "
            f"yfinance available: {_yf_available()}"
        )

    # Apply rollup if requested. Rolled up = aggregate by ticker:
    #   shares = sum
    #   cost_basis_per_share = weighted average
    #   broker = single broker if all-same else "BrokerA + BrokerB"
    #   purchase_date = earliest non-blank
    #   notes = pipe-joined distinct non-blank
    if rollup_mode == "Rolled up" and broker_filter == "All":
        def _rollup(g):
            total_shares = g["shares"].sum()
            total_cost = (g["shares"] * g["cost_basis_per_share"]).sum()
            avg_cost = (total_cost / total_shares) if total_shares else 0.0
            brokers_in_group = sorted(set(g["broker"].dropna().astype(str)) - {""})
            broker_str = brokers_in_group[0] if len(brokers_in_group) == 1 else " + ".join(brokers_in_group)
            dates = sorted(set(d for d in g["purchase_date"].astype(str) if d.strip()))
            notes = " | ".join(sorted(set(n for n in g["notes"].astype(str) if n.strip())))
            return pd.Series({
                "broker": broker_str,
                "shares": total_shares,
                "cost_basis_per_share": avg_cost,
                "purchase_date": dates[0] if dates else "",
                "notes": notes,
            })
        # include_groups=False introduced in pandas 2.2; fall back if older.
        try:
            holdings = (
                holdings.groupby("ticker", as_index=False)
                .apply(_rollup, include_groups=False)
                .reset_index(drop=True)
            )
        except TypeError:
            holdings = (
                holdings.groupby("ticker", as_index=False)
                .apply(_rollup)
                .reset_index(drop=True)
            )
        if "ticker" not in holdings.columns:
            holdings = holdings.reset_index()

    tickers = tuple(sorted(holdings["ticker"].unique().tolist()))
    prices = _portfolio_prices(tickers)
    holdings["current_price"] = holdings["ticker"].map(prices)
    holdings["market_value"] = holdings["shares"] * holdings["current_price"]
    holdings["cost_basis_total"] = holdings["shares"] * holdings["cost_basis_per_share"]
    holdings["gain_loss_$"] = holdings["market_value"] - holdings["cost_basis_total"]

    def _gl_pct(row):
        cbt = row["cost_basis_total"]
        if not isinstance(cbt, (int, float)) or cbt == 0 or pd.isna(cbt):
            return None
        gl = row["gain_loss_$"]
        if not isinstance(gl, (int, float)) or pd.isna(gl):
            return None
        return (gl / cbt) * 100.0

    holdings["gain_loss_pct"] = holdings.apply(_gl_pct, axis=1)

    total_mv = holdings["market_value"].sum(skipna=True)
    if total_mv and not pd.isna(total_mv) and total_mv > 0:
        holdings["pct_of_total"] = holdings["market_value"] / total_mv * 100.0
    else:
        holdings["pct_of_total"] = 0.0

    total_cost = holdings["cost_basis_total"].sum(skipna=True)
    total_gl = total_mv - total_cost if pd.notna(total_mv) and pd.notna(total_cost) else 0.0
    total_gl_pct = (total_gl / total_cost * 100.0) if total_cost else 0.0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Market value", f"${total_mv:,.0f}" if pd.notna(total_mv) else "-")
    m2.metric("Cost basis", f"${total_cost:,.0f}" if pd.notna(total_cost) else "-")
    m3.metric("Gain/Loss $", f"${total_gl:,.0f}", f"{total_gl_pct:+.1f}%")
    m4.metric("Positions", f"{len(holdings)}")

    show = holdings[[
        "ticker", "broker", "shares", "cost_basis_per_share", "current_price",
        "market_value", "gain_loss_$", "gain_loss_pct", "pct_of_total", "purchase_date", "notes",
    ]].rename(columns={
        "cost_basis_per_share": "avg cost",
        "current_price":        "current $",
        "market_value":         "value",
        "gain_loss_$":          "GL $",
        "gain_loss_pct":        "GL %",
        "pct_of_total":         "% portfolio",
        "purchase_date":        "purchased",
    }).sort_values("value", ascending=False, na_position="last")

    st.dataframe(
        show,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ticker":      st.column_config.TextColumn("ticker"),
            "broker":      st.column_config.TextColumn("broker"),
            "shares":      st.column_config.NumberColumn("shares", format="%.4g"),
            "avg cost":    st.column_config.NumberColumn("avg cost", format="$%.2f"),
            "current $":   st.column_config.NumberColumn("current $", format="$%.2f"),
            "value":       st.column_config.NumberColumn("value", format="$%,.0f"),
            "GL $":        st.column_config.NumberColumn("GL $", format="$%,.0f"),
            "GL %":        st.column_config.NumberColumn("GL %", format="%+.1f%%"),
            "% portfolio": st.column_config.ProgressColumn(
                "% portfolio", min_value=0, max_value=100, format="%.1f%%"),
            "purchased":   st.column_config.TextColumn("purchased"),
            "notes":       st.column_config.TextColumn("notes", width="medium"),
        },
        height=min(540, 60 + 35 * len(show)),
        key="portfolio_holdings_table",
    )

    st.markdown(
        '<h3 style="margin-top:32px;">Price history</h3>',
        unsafe_allow_html=True,
    )

    chart_col1, chart_col2 = st.columns([2, 3])
    with chart_col1:
        selected_ticker = st.selectbox(
            "Ticker",
            options=list(tickers),
            index=0,
            key="portfolio_chart_ticker",
        )
    with chart_col2:
        period_map = {"1M": "1mo", "6M": "6mo", "1Y": "1y", "5Y": "5y"}
        period_label = st.radio(
            "Period",
            options=list(period_map.keys()),
            index=2,
            horizontal=True,
            key="portfolio_chart_period",
        )
        period = period_map[period_label]

    hist = _portfolio_history(selected_ticker, period)
    if hist is None or hist.empty:
        st.info(f"No history available for {selected_ticker} over {period_label}.")
    else:
        chart_df = hist[["Close"]].rename(columns={"Close": selected_ticker})
        st.line_chart(chart_df, height=320, use_container_width=True)


def main():
    st.set_page_config(
        page_title="Trend Engine — Daily Digest",
        page_icon="📰",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Page-level CSS — minimal dark editorial aesthetic
    st.markdown("""
        <style>
            /* Tighten default Streamlit padding for a denser editorial feel */
            .block-container { padding-top: 2rem; padding-bottom: 4rem; max-width: 1100px; }
            /* Headings in serif */
            h1, h2, h3 { font-family: Georgia, serif !important; }
            /* Hide the default Streamlit header chrome */
            header[data-testid="stHeader"] { background: transparent; }
        </style>
    """, unsafe_allow_html=True)

    # ---- Header ----
    st.markdown(
        '<h1 style="margin-bottom: 0;">Trend Engine</h1>'
        '<div style="color: #64748b; font-size: 13px; margin-bottom: 32px; '
        'font-family: monospace; letter-spacing: 0.05em;">'
        'arXiv research + macro news · scored for 2-year retail investing horizon'
        '</div>',
        unsafe_allow_html=True,
    )

    # ---- Session state init ----
    if "selected_id" not in st.session_state:
        st.session_state.selected_id = None

    # ---- Tabs ----
    # Research first since it's the established surface; News and Portfolio
    # are the newer additions. Sidebar widgets render per-tab — Streamlit
    # re-renders the sidebar on tab switch, so each tab's filters appear
    # only when its tab is active. Widget keys are tab-prefixed
    # (research_ / news_ / portfolio_) to dodge Streamlit's DuplicateWidgetID.
    research_tab, news_tab, portfolio_tab = st.tabs(["Research", "News", "Portfolio"])
    with research_tab:
        render_research_tab()
    with news_tab:
        render_news_tab()
    with portfolio_tab:
        render_portfolio_tab()


if __name__ == "__main__":
    main()
