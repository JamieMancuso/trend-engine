"""
Week 6 Analytics — Streamlit dashboard across all scored runs
--------------------------------------------------------------
Companion to week4_digest.py. The digest is for *reading* — this is for
*pattern-finding*. Where is the engine spending its attention? Are flag
ratios drifting? Which watchlist items are aging without follow-up signal?

DESIGN PHILOSOPHY:
- Same visual language as the digest: dark editorial, serif headings,
  monospace metadata, minimal chrome.
- Cross-history queries by default — single-run mode is an override.
- Earn-its-keep gate: every chart has to answer a question worth asking
  weekly. If a chart goes 3 weeks without changing your mind, kill it.

WHAT IT SHOWS:
  1. KPI strip — totals, cost-to-date, cache savings %
  2. Domain heat — paper count × mean final score per domain
  3. Flag distribution over time — stacked area by run date
  4. Top by Horizon — long-term lens (the longshot pile, sorted)
  5. Watchlist aging — what's been sitting unattended, oldest first

RUN:
    py -3.14 -m streamlit run week6_analytics.py

Will share the same port as the digest if it's already running — kill the
digest first or use --server.port 8502.
"""

from __future__ import annotations

import glob
import json
from pathlib import Path

import pandas as pd
import streamlit as st

# Shadow portfolio module (Week 8 addition). Wrapped in try/except so the
# Analytics page renders even if yfinance isn't installed locally — the
# section will degrade to an "install yfinance" hint.
try:
    import shadow_portfolio as sp
    _SHADOW_AVAILABLE = True
except Exception as _sp_exc:
    sp = None
    _SHADOW_AVAILABLE = False
    _SHADOW_IMPORT_ERR = str(_sp_exc)


# ---- CONFIG ----------------------------------------------------------------

RESULTS_GLOB = "results_*.csv"

# Score-tier palette mirrors the digest. Reused for chart colors so flag
# distribution charts read at a glance against the digest itself.
FLAG_COLORS = {
    "thesis":    "#fb923c",   # warm amber
    "watchlist": "#94a3b8",   # slate
    "longshot":  "#34d399",   # green
    "skip":      "#52525b",   # muted graphite
}

DOMAIN_ORDER = ["AI", "Bio", "Health", "Space", "Quantum", "Robotics", "Energy", "Climate"]


# ---- DATA LOADING (mirrors week4_digest._normalize) ------------------------

def find_all_results() -> list[str]:
    return sorted(glob.glob(RESULTS_GLOB))


def _parse_vehicles(v):
    if not isinstance(v, str) or not v.strip():
        return []
    try:
        parsed = json.loads(v)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, ValueError):
        return []


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Same coercions the digest does, kept in sync deliberately."""
    for col in ("llm_maturation", "llm_profit_mechanism", "llm_retail_accessibility",
                "llm_specificity", "llm_horizon", "llm_final",
                "input_tokens", "output_tokens",
                "cache_write_tokens", "cache_read_tokens", "cost_usd"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["vehicles_list"] = df.get("llm_public_vehicles", "").apply(_parse_vehicles)
    df["published_dt"] = pd.to_datetime(df.get("published"), errors="coerce", utc=True)
    df["run_dt"] = pd.to_datetime(df.get("run_timestamp"), errors="coerce")
    df["run_date"] = df["run_dt"].dt.strftime("%Y-%m-%d")
    return df


@st.cache_data(show_spinner=False)
def load_all_runs(file_tuple: tuple[str, ...]) -> pd.DataFrame:
    """
    Load EVERY row from EVERY results CSV — no dedup.
    Each row is one paper-scoring event. We want history, not just the
    latest-score-per-paper view that the digest uses.
    """
    frames = []
    for path in file_tuple:
        try:
            f = pd.read_csv(path)
            f["__source_file"] = Path(path).name
            frames.append(f)
        except Exception:
            pass
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    return _normalize(combined)


@st.cache_data(show_spinner=False)
def load_latest_per_paper(file_tuple: tuple[str, ...]) -> pd.DataFrame:
    """
    Latest score per paper — the digest's view. Used for the cross-corpus
    'current state' charts (domain heat, watchlist aging) so a paper isn't
    double-counted across re-scores.
    """
    df = load_all_runs(file_tuple)
    if df.empty:
        return df
    if "run_timestamp" in df.columns:
        df = df.sort_values("run_timestamp", ascending=True)
    return df.drop_duplicates(subset=["id"], keep="last").reset_index(drop=True)


# ---- UI: HEADER + KPI STRIP -------------------------------------------------

def render_kpi_strip(all_runs: pd.DataFrame, latest: pd.DataFrame) -> None:
    """Top-of-page numbers. Total events, unique papers, cost, cache %, flags."""
    total_events = len(all_runs)
    unique_papers = len(latest)
    total_cost = all_runs["cost_usd"].sum() if "cost_usd" in all_runs.columns else 0.0

    # Cache savings: if cache_read_tokens are present, those would have
    # cost ~10x more uncached. Same for cache_write at 1.25x.
    if "cache_read_tokens" in all_runs.columns and "cache_write_tokens" in all_runs.columns:
        # Sonnet 4.6 input pricing per 1M tokens (matches week2_run_scoring)
        INPUT_PRICE = 3.0     # $/M
        CACHE_READ  = 0.30    # $/M (10% of input)
        CACHE_WRITE = 3.75    # $/M (125% of input)
        cw = all_runs["cache_write_tokens"].sum()
        cr = all_runs["cache_read_tokens"].sum()
        # What we actually paid for cache reads + writes
        actual = (cw * CACHE_WRITE / 1_000_000) + (cr * CACHE_READ / 1_000_000)
        # What that same volume would have cost as plain input
        uncached = (cw + cr) * INPUT_PRICE / 1_000_000
        cache_savings = max(0.0, uncached - actual)
        cache_pct = (cache_savings / uncached * 100) if uncached > 0 else 0.0
    else:
        cache_savings = 0.0
        cache_pct = 0.0

    # Flag counts from the latest-per-paper view (current state of corpus)
    flag_counts = latest["llm_flag"].value_counts() if "llm_flag" in latest.columns else pd.Series()

    cols = st.columns(5)
    cols[0].metric("Scoring events", f"{total_events:,}")
    cols[1].metric("Unique papers", f"{unique_papers:,}")
    cols[2].metric("Cost to date", f"${total_cost:.2f}")
    cols[3].metric("Cache savings", f"${cache_savings:.2f}", f"{cache_pct:.0f}%")

    # Compact flag summary — only the actionable tiers (thesis + watchlist + longshot).
    # Skip count is implicit (= total - these) and not interesting at a glance.
    flag_summary = (
        f"{flag_counts.get('thesis', 0)}T · "
        f"{flag_counts.get('watchlist', 0)}W · "
        f"{flag_counts.get('longshot', 0)}L"
    )
    cols[4].metric("Active flags", flag_summary, help="Thesis · Watchlist · Longshot")


# ---- CHART 1: DOMAIN HEAT --------------------------------------------------

def render_domain_heat(latest: pd.DataFrame) -> None:
    """
    Domain heat = where the engine has been *finding* signal, not just where
    it's been looking. Two stats per domain:
        - paper count (volume)
        - mean final score (signal density)
    A domain with high count + low mean = noisy. Low count + high mean = rare gold.
    """
    st.markdown(
        '<h2 style="margin-top:32px;">Domain heat</h2>'
        '<div style="color:#64748b; font-size:13px; margin-bottom:16px;">'
        'Volume vs mean signal per domain — across all scored papers (latest score per paper).'
        '</div>',
        unsafe_allow_html=True,
    )

    if "domain" not in latest.columns or latest.empty:
        st.info("No domain data yet.")
        return

    grp = latest.groupby("domain").agg(
        papers=("id", "count"),
        mean_final=("llm_final", "mean"),
        thesis=("llm_flag", lambda s: (s == "thesis").sum()),
        watchlist=("llm_flag", lambda s: (s == "watchlist").sum()),
        longshot=("llm_flag", lambda s: (s == "longshot").sum()),
    ).round(2)

    # Stable domain order matching the charter
    grp = grp.reindex([d for d in DOMAIN_ORDER if d in grp.index]).fillna(0)
    grp["mean_final"] = grp["mean_final"].fillna(0).round(2)

    # Display: bar chart for counts + adjacent stat table
    col_chart, col_table = st.columns([3, 2])
    with col_chart:
        st.bar_chart(grp[["papers"]], color="#fb923c", height=320)
    with col_table:
        # Reset index so 'domain' is a real column we can show + use ProgressColumn
        # for mean_final (gives the visual "heat" cue without needing matplotlib).
        table = grp.reset_index()
        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
            column_config={
                "domain":     st.column_config.TextColumn("domain"),
                "papers":     st.column_config.NumberColumn("papers", format="%d"),
                "mean_final": st.column_config.ProgressColumn(
                    "mean final", min_value=0, max_value=10, format="%.2f"),
                "thesis":     st.column_config.NumberColumn("T", format="%d", help="thesis count"),
                "watchlist":  st.column_config.NumberColumn("W", format="%d", help="watchlist count"),
                "longshot":   st.column_config.NumberColumn("L", format="%d", help="longshot count"),
            },
        )


# ---- CHART 2: FLAG DISTRIBUTION OVER TIME ----------------------------------

def render_flag_over_time(all_runs: pd.DataFrame) -> None:
    """
    Stacked counts of thesis / watchlist / longshot / skip per run date.
    'Per run date' = grouped by the date the scoring ran, not paper publication.
    What this catches: prompt drift (thesis count suddenly spikes →
    rubric got lenient), or a quiet research week (everything skip).
    """
    st.markdown(
        '<h2 style="margin-top:48px;">Flag distribution over time</h2>'
        '<div style="color:#64748b; font-size:13px; margin-bottom:16px;">'
        'Each scoring run, broken out by flag. Watch for sudden swings — '
        'usually rubric drift, occasionally a real signal week.'
        '</div>',
        unsafe_allow_html=True,
    )

    if "run_date" not in all_runs.columns or all_runs.empty:
        st.info("No run-timestamp data yet.")
        return

    pivot = (
        all_runs.groupby(["run_date", "llm_flag"])
        .size()
        .unstack(fill_value=0)
    )
    # Force flag order so legend is consistent across runs
    flag_order = [f for f in ["thesis", "watchlist", "longshot", "skip"] if f in pivot.columns]
    pivot = pivot[flag_order]

    if pivot.empty:
        st.info("No runs to chart yet.")
        return

    # Streamlit's native bar chart accepts a color list when y is multi-column
    colors = [FLAG_COLORS[f] for f in flag_order]
    st.bar_chart(pivot, color=colors, height=320, stack=True)

    # Tiny supporting table — exact numbers for the recent runs
    with st.expander("Run-by-run table"):
        st.dataframe(pivot.iloc[::-1], use_container_width=True)


# ---- CHART 3: TOP BY HORIZON -----------------------------------------------

def render_top_horizon(latest: pd.DataFrame) -> None:
    """
    Sort by Horizon score descending — the longshot lens. Horizon is the
    transformative-ceiling axis (added in v0.3); it's deliberately decoupled
    from final score so a 'this could be huge but not yet' paper still surfaces.
    """
    st.markdown(
        '<h2 style="margin-top:48px;">Top by Horizon</h2>'
        '<div style="color:#64748b; font-size:13px; margin-bottom:16px;">'
        'Long-term transformative ceiling. High Horizon + low Final = the longshot pile. '
        'High Horizon + high Final = the trillion-dollar lottery ticket that\'s also actionable today.'
        '</div>',
        unsafe_allow_html=True,
    )

    if "llm_horizon" not in latest.columns:
        st.info("No Horizon scores yet — present only in v0.3+ scored rows.")
        return

    horizon_df = latest.dropna(subset=["llm_horizon"]).copy()
    if horizon_df.empty:
        st.info("No papers with Horizon scores yet.")
        return

    # Sort key: Horizon desc, then Final desc as tiebreaker
    horizon_df = horizon_df.sort_values(
        by=["llm_horizon", "llm_final"], ascending=[False, False]
    )

    show = horizon_df[[
        "domain", "title", "llm_horizon", "llm_final", "llm_flag", "url"
    ]].rename(columns={
        "llm_horizon": "HRZ",
        "llm_final":   "Final",
        "llm_flag":    "Flag",
        "url":         "arxiv",
    }).head(25)

    st.dataframe(
        show,
        use_container_width=True,
        column_config={
            "HRZ":   st.column_config.ProgressColumn("HRZ", min_value=0, max_value=10, format="%d"),
            "Final": st.column_config.ProgressColumn("Final", min_value=0, max_value=10, format="%.1f"),
            "arxiv": st.column_config.LinkColumn("arxiv", display_text="↗"),
            "title": st.column_config.TextColumn("title", width="large"),
        },
        hide_index=True,
        height=600,
    )


# ---- CHART 4: WATCHLIST AGING ----------------------------------------------

def render_watchlist_aging(latest: pd.DataFrame, all_runs: pd.DataFrame) -> None:
    """
    The watchlist is supposed to be revisited periodically. This surfaces
    items that have been sitting longest without a fresh look — sorted by
    days-since-first-seen.

    'First seen' = earliest run_timestamp for that paper across all runs.
    """
    st.markdown(
        '<h2 style="margin-top:48px;">Watchlist aging</h2>'
        '<div style="color:#64748b; font-size:13px; margin-bottom:16px;">'
        'Watchlist items, oldest first. The point of a watchlist is to revisit — '
        'this is the revisit queue.'
        '</div>',
        unsafe_allow_html=True,
    )

    if "llm_flag" not in latest.columns:
        st.info("No flag data yet.")
        return

    wl = latest[latest["llm_flag"].isin(["watchlist", "longshot"])].copy()
    if wl.empty:
        st.info("No watchlist or longshot items yet.")
        return

    # Earliest run_timestamp per paper id, computed from all_runs
    if "run_dt" in all_runs.columns:
        first_seen = (
            all_runs.dropna(subset=["run_dt"])
            .groupby("id")["run_dt"]
            .min()
            .rename("first_seen")
        )
        wl = wl.merge(first_seen, on="id", how="left")
        today = pd.Timestamp.now()
        wl["age_days"] = (today - wl["first_seen"]).dt.days.fillna(0).astype(int)
    else:
        wl["age_days"] = 0

    wl = wl.sort_values(by=["age_days", "llm_final"], ascending=[False, False])

    show = wl[[
        "domain", "title", "llm_flag", "llm_final", "llm_horizon",
        "age_days", "llm_public_vehicles", "url",
    ]].rename(columns={
        "llm_flag":             "Flag",
        "llm_final":            "Final",
        "llm_horizon":          "HRZ",
        "age_days":             "Age (d)",
        "llm_public_vehicles":  "Vehicles",
        "url":                  "arxiv",
    })

    st.dataframe(
        show,
        use_container_width=True,
        column_config={
            "Final":    st.column_config.ProgressColumn("Final", min_value=0, max_value=10, format="%.1f"),
            "HRZ":      st.column_config.ProgressColumn("HRZ", min_value=0, max_value=10, format="%d"),
            "Age (d)":  st.column_config.NumberColumn("Age (d)"),
            "arxiv":    st.column_config.LinkColumn("arxiv", display_text="↗"),
            "title":    st.column_config.TextColumn("title", width="large"),
        },
        hide_index=True,
        height=480,
    )


# ---- CHART 5: SHADOW PORTFOLIO --------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def _load_shadow_with_prices() -> pd.DataFrame:
    """
    Pull the on-disk shadow portfolio, then enrich with current prices via
    yfinance. Cached for 1 hour to keep network calls cheap. The Refresh
    button below clears this cache.
    """
    if not _SHADOW_AVAILABLE:
        return pd.DataFrame()
    df = sp.load_existing_shadow()
    if df.empty:
        return df
    return sp.refresh_current_prices(df)


@st.cache_data(show_spinner=False)
def _load_news_url_map(file_tuple: tuple) -> dict:
    """Build a map of news_id -> article URL by scanning all news_results_*.csv.
    News IDs look like 'hn:48094641' or 'reuters_via_google:abc123'. The 'url'
    column in news_results CSVs points to the actual article. Cached so we
    only scan the files once per render."""
    out = {}
    for path in file_tuple:
        try:
            f = pd.read_csv(path)
        except Exception:
            continue
        if "id" not in f.columns or "url" not in f.columns:
            continue
        for _, r in f.iterrows():
            nid = str(r.get("id", "") or "").strip()
            url = str(r.get("url", "") or "").strip()
            if nid and url and nid not in out:
                out[nid] = url
    return out


def render_shadow_portfolio() -> None:
    """
    Shadow portfolio = tickers the system surfaced 3+ times in 7 days,
    snapshotted at threshold-crossing. Feedback loop: did we have signal
    BEFORE the run-up, and did we act on it?

    Charter 2026-05-12 + Week 8 build. Refresh button is on-demand only —
    no scheduled yfinance calls.
    """
    st.markdown(
        '<h2 style="margin-top:48px;">Shadow portfolio</h2>'
        '<div style="color:#64748b; font-size:13px; margin-bottom:16px;">'
        'Tickers the system flagged 3+ times in a 7-day window. Price snapshotted '
        'at threshold-crossing; current price refreshed via yfinance. '
        'Did we have the signal before the move?'
        '</div>',
        unsafe_allow_html=True,
    )

    if not _SHADOW_AVAILABLE:
        st.info(
            "Shadow portfolio module not available. "
            f"Import error: `{_SHADOW_IMPORT_ERR}`. "
            "Install yfinance: `py -3.14 -m pip install yfinance --user`"
        )
        return

    col_refresh, col_scan = st.columns([1, 1])
    with col_refresh:
        if st.button("↻ Refresh prices", key="shadow_refresh",
                     help="Re-pull current prices via yfinance. Cleared cache, no scheduled calls."):
            _load_shadow_with_prices.clear()
    with col_scan:
        if st.button("⊕ Scan for new triggers", key="shadow_scan",
                     help="Re-scan all results / news CSVs for new 3-mention triggers. "
                          "Writes any new rows to shadow_portfolio.csv."):
            with st.spinner("Scanning…"):
                full = sp.scan_for_triggers(fetch_prices=True, verbose=False)
                sp.write_shadow_portfolio(full)
            _load_shadow_with_prices.clear()
            st.success(f"Scan complete — shadow portfolio now has {len(full)} ticker(s).")

    df = _load_shadow_with_prices()
    if df.empty:
        st.info(
            "Shadow portfolio is empty. Click **Scan for new triggers** above to "
            "build the initial set from existing results / news CSVs."
        )
        return

    # Sort selector. Default to absolute-% movers so biggest swings (up or
    # down) come first — that's the "did the system see it" question this
    # whole feature is built for.
    sort_options = {
        "Δ% (biggest movers)":     ("__abs", False),
        "Δ% (high → low)":         ("pct_change_since_trigger", False),
        "Δ% (low → high)":         ("pct_change_since_trigger", True),
        "Mentions (high → low)":   ("mention_count_at_trigger", False),
        "Trigger date (newest)":   ("first_trigger_date", False),
        "Trigger date (oldest)":   ("first_trigger_date", True),
        "Ticker (A → Z)":          ("ticker", True),
    }
    sort_choice = st.selectbox(
        "Sort by",
        list(sort_options.keys()),
        index=0,
        key="shadow_sort",
    )
    sort_col, sort_asc = sort_options[sort_choice]

    sortable = df.copy()
    if sort_col == "__abs":
        sortable["__abs_move"] = sortable["pct_change_since_trigger"].abs().fillna(-1)
        sortable = sortable.sort_values("__abs_move", ascending=False).drop(columns="__abs_move")
    else:
        sortable = sortable.sort_values(by=sort_col, ascending=sort_asc, kind="stable", na_position="last")

    # Build a lookup of news_id -> (url, title) by scanning all news_results_*.csv
    # once per render. Cached on the file_tuple so it's fast across reruns.
    news_url_map = _load_news_url_map(tuple(sorted(glob.glob("news_results_*.csv"))))

    def _build_links_html(paper_ids_str: str) -> str:
        """Given a semicolon-joined ID list, return HTML <a> tags for each ID.
        Arxiv IDs link to arxiv.org. News IDs link to the article URL from
        news_results CSVs (when found). Returns inline-HTML string."""
        if not isinstance(paper_ids_str, str) or not paper_ids_str.strip():
            return "<span style=\"color:#64748b;\">—</span>"
        ids = [pid.strip() for pid in paper_ids_str.split(";") if pid.strip()]
        links = []
        for pid in ids:
            if ":" in pid:
                # News-style ID (hn:..., reuters_via_google:..., npr:..., fed:...)
                source_key = pid.split(":", 1)[0]
                url = news_url_map.get(pid)
                if url:
                    label = source_key
                    links.append(
                        f"<a href=\"{url}\" target=\"_blank\" "
                        f"style=\"color:#93c5fd; text-decoration:underline; "
                        f"margin-right:6px; font-family:monospace; font-size:12px;\">"
                        f"{label}↗</a>"
                    )
                else:
                    links.append(
                        f"<span style=\"color:#64748b; margin-right:6px; "
                        f"font-family:monospace; font-size:12px;\">{source_key}</span>"
                    )
            else:
                # Arxiv ID — link to arxiv.org/abs/<id>
                url = f"https://arxiv.org/abs/{pid}"
                links.append(
                    f"<a href=\"{url}\" target=\"_blank\" "
                    f"style=\"color:#fdba74; text-decoration:underline; "
                    f"margin-right:6px; font-family:monospace; font-size:12px;\">"
                    f"arxiv↗</a>"
                )
        return " ".join(links)

    # Header row
    cols = st.columns([1.2, 1.4, 1.2, 1.2, 1.0, 0.8, 3.0])
    headers = ["ticker", "trigger date", "trigger $", "current $", "Δ %", "mentions", "sources"]
    for c, h in zip(cols, headers):
        c.markdown(
            f"<div style=\"font-family:monospace; font-size:11px; "
            f"letter-spacing:0.1em; color:#64748b; text-transform:uppercase; "
            f"border-bottom:1px solid rgba(120,120,140,0.2); padding-bottom:6px;\">"
            f"{h}</div>",
            unsafe_allow_html=True,
        )

    # Data rows
    for _, row in sortable.iterrows():
        cols = st.columns([1.2, 1.4, 1.2, 1.2, 1.0, 0.8, 3.0])
        tp = row.get("trigger_price")
        cp = row.get("current_price")
        pc = row.get("pct_change_since_trigger")
        mc = row.get("mention_count_at_trigger")
        tp_str = f"${float(tp):.2f}" if pd.notna(tp) and str(tp).strip() not in ("", "nan") else "—"
        cp_str = f"${float(cp):.2f}" if pd.notna(cp) else "—"
        pc_color = "#34d399" if (pd.notna(pc) and pc > 0) else ("#f87171" if pd.notna(pc) and pc < 0 else "#64748b")
        pc_str = (f"<span style=\"color:{pc_color};\">{pc:+.1f}%</span>"
                  if pd.notna(pc) else "<span style=\"color:#64748b;\">—</span>")
        cols[0].markdown(f"**{row['ticker']}**")
        cols[1].markdown(f"<span style=\"font-family:monospace;font-size:12px;\">"
                         f"{row['first_trigger_date']}</span>", unsafe_allow_html=True)
        cols[2].markdown(tp_str)
        cols[3].markdown(cp_str)
        cols[4].markdown(pc_str, unsafe_allow_html=True)
        cols[5].markdown(f"{int(mc)}" if pd.notna(mc) else "—")
        cols[6].markdown(_build_links_html(row.get("paper_ids", "")), unsafe_allow_html=True)


# ---- MAIN ------------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="Trend Engine — Analytics",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    # Inherit the digest's editorial CSS so the two pages feel like siblings
    st.markdown("""
        <style>
            .block-container { padding-top: 2rem; padding-bottom: 4rem; max-width: 1200px; }
            h1, h2, h3 { font-family: Georgia, serif !important; }
            header[data-testid="stHeader"] { background: transparent; }
        </style>
    """, unsafe_allow_html=True)

    # Header
    st.markdown(
        '<h1 style="margin-bottom: 0;">Trend Engine — Analytics</h1>'
        '<div style="color: #64748b; font-size: 13px; margin-bottom: 32px; '
        'font-family: monospace; letter-spacing: 0.05em;">'
        'cross-run patterns · domain heat · watchlist revisit queue'
        '</div>',
        unsafe_allow_html=True,
    )

    files = find_all_results()
    if not files:
        st.error("No results_*.csv found in the current directory.")
        st.stop()

    file_tuple = tuple(files)
    all_runs = load_all_runs(file_tuple)
    latest = load_latest_per_paper(file_tuple)

    if all_runs.empty:
        st.error("Could not load any results files.")
        st.stop()

    # KPI strip
    render_kpi_strip(all_runs, latest)

    st.markdown(
        f'<div style="color:#64748b; font-size:12px; font-family:monospace; '
        f'margin-top:8px;">Loaded {len(file_tuple)} run file(s) · '
        f'{len(all_runs)} scoring events · {len(latest)} unique papers</div>',
        unsafe_allow_html=True,
    )

    # Charts
    render_domain_heat(latest)
    render_flag_over_time(all_runs)
    render_top_horizon(latest)
    render_watchlist_aging(latest, all_runs)
    render_shadow_portfolio()


if __name__ == "__main__":
    main()
