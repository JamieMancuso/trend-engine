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
    "skip":      {"bg": "#27272a", "fg": "#71717a"},   # muted graphite
}


# ---- DATA LOADING ----------------------------------------------------------

def find_latest_results() -> str | None:
    """Find the most recent results_*.csv in the current directory."""
    matches = sorted(glob.glob(RESULTS_GLOB))
    return matches[-1] if matches else None


def find_all_results() -> list[str]:
    """Return all results_*.csv files sorted oldest → newest."""
    return sorted(glob.glob(RESULTS_GLOB))


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
                "llm_specificity", "llm_final"):
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


def render_subscores(row) -> str:
    """Compact row of sub-scores below the title."""
    parts = [
        ("MAT",  int(row["llm_maturation"])),
        ("PROF", int(row["llm_profit_mechanism"])),
        ("RET",  int(row["llm_retail_accessibility"])),
        ("SPEC", int(row["llm_specificity"])),
    ]
    pills = []
    for label, val in parts:
        # Subtle color hint: dim sub-scores under 4 to make weak axes visible.
        opacity = "0.45" if val < 4 else "0.95"
        pills.append(f"""
            <span style="
                display: inline-block;
                padding: 3px 10px;
                margin-right: 6px;
                background: rgba(120,120,140,0.12);
                border-radius: 999px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 12px;
                opacity: {opacity};
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


def render_card(row) -> None:
    """Render a single paper as a card. Uses two columns: text + score badge."""
    with st.container():
        st.markdown('<div style="margin-top: 24px;"></div>', unsafe_allow_html=True)
        col_text, col_score = st.columns([8, 1.2])

        with col_score:
            st.markdown(render_score_badge(row["llm_final"], row["llm_flag"]),
                        unsafe_allow_html=True)

        with col_text:
            # Domain tag + title
            st.markdown(
                f'<div style="font-family: monospace; font-size: 11px; '
                f'letter-spacing: 0.15em; color: #64748b; '
                f'text-transform: uppercase; margin-bottom: 4px;">{row["domain"]}</div>'
                f'<div style="font-family: Georgia, serif; font-size: 19px; '
                f'line-height: 1.3; font-weight: 600; color: #e2e8f0;">'
                f'{row["title"]}</div>',
                unsafe_allow_html=True,
            )

            # Sub-scores
            st.markdown(render_subscores(row), unsafe_allow_html=True)

            # Translation — the most important field
            st.markdown(
                f'<div style="font-size: 14px; line-height: 1.55; color: #cbd5e1;">'
                f'{row["llm_translation"]}</div>',
                unsafe_allow_html=True,
            )

            # Expandable rationale (the "why this scored X" audit trail)
            with st.expander("Scoring rationale"):
                st.markdown(f"*{row['llm_rationale']}*")
                st.caption(f"Prompt {row.get('prompt_version', '?')} · "
                           f"{row.get('model', '?')} · "
                           f"id `{row['id']}`")

            # Footer
            st.markdown(render_footer(row), unsafe_allow_html=True)

        # Soft separator between cards
        st.markdown(
            '<div style="margin-top: 24px; '
            'border-bottom: 1px solid rgba(120,120,140,0.12);"></div>',
            unsafe_allow_html=True,
        )


# ---- MAIN APP --------------------------------------------------------------

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
        'arXiv research digest · scored for 2-year retail investing horizon'
        '</div>',
        unsafe_allow_html=True,
    )

    # ---- Sidebar: file picker + filters ----
    st.sidebar.header("Source")

    all_result_files = find_all_results()
    if not all_result_files:
        st.error("No results_*.csv found in the current directory. "
                 "Run week2_run_scoring.py first.")
        st.stop()

    # Multi-run toggle — merges all CSVs when enabled
    multi_run = st.sidebar.toggle(
        "Merge all runs",
        value=False,
        help="Combines every results_*.csv, keeping the latest score per paper. "
             "Good for a cross-run best-of view once several runs have accumulated.",
    )

    num_runs = 1
    if multi_run:
        df, num_runs = load_all_results(tuple(all_result_files))
        if df.empty:
            st.error("Could not load any results files.")
            st.stop()
        st.sidebar.caption(f"Merged **{num_runs}** run(s) · **{len(df)}** unique papers")
    else:
        # Single-file mode: default to latest, allow override
        default_path = all_result_files[-1]
        csv_path = st.sidebar.text_input("Results CSV", value=default_path,
                                         help="Path to a results_*.csv file.")
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

    # Domain multiselect — default all selected
    all_domains = sorted(df["domain"].unique().tolist())
    selected_domains = st.sidebar.multiselect(
        "Domains", all_domains, default=all_domains,
    )

    # Flag multiselect — default to thesis + watchlist (skip is the noise tier)
    all_flags = ["thesis", "watchlist", "skip"]
    selected_flags = st.sidebar.multiselect(
        "Flags", all_flags, default=["thesis", "watchlist"],
        help="thesis = act today · watchlist = revisit in 3-6 months · skip = noise",
    )

    # Min final score
    min_final = st.sidebar.slider(
        "Min final score", min_value=0.0, max_value=10.0,
        value=DEFAULT_MIN_FINAL, step=0.5,
    )

    # "Has public vehicle" toggle — useful for "show me actionable picks only"
    require_vehicle = st.sidebar.checkbox(
        "Only papers with named public vehicle(s)", value=False,
        help="Hides papers where the LLM couldn't name a public-equity exposure.",
    )

    # Sort
    sort_options = {
        "Final score (high → low)": ("llm_final", False),
        "Final score (low → high)": ("llm_final", True),
        "Date (newest → oldest)":   ("published_dt", False),
        "Date (oldest → newest)":   ("published_dt", True),
        "Domain (A → Z)":           ("domain", True),
    }
    sort_choice = st.sidebar.selectbox("Sort by", list(sort_options.keys()),
                                       index=0)
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

    # ---- Counts header ----
    flag_counts = filtered["llm_flag"].value_counts()
    run_label = f" across {num_runs} runs" if multi_run and num_runs > 1 else ""
    counts_text = (
        f"**{len(filtered)}** papers{run_label} · "
        f"thesis: {flag_counts.get('thesis', 0)} · "
        f"watchlist: {flag_counts.get('watchlist', 0)} · "
        f"skip: {flag_counts.get('skip', 0)}"
    )
    st.markdown(counts_text)

    if len(filtered) == 0:
        st.info("No papers match the current filters. Loosen the filters in the sidebar.")
        return

    # ---- Render cards ----
    for _, row in filtered.iterrows():
        render_card(row)


if __name__ == "__main__":
    main()