"""
Shadow Portfolio — paths-not-taken tracker.
-------------------------------------------
Built Week 8 per the 2026-05-12 charter decision.

WHAT IT DOES
============
Scans research + news scoring output for recurring tickers. When a ticker
crosses a threshold (3+ mentions in a 7-day rolling window), snapshots its
price at that date and records it permanently to shadow_portfolio.csv.

WHY
===
Closes a feedback loop. If the system surfaced NVDA across 4 papers and 2
news items in May 2024 but operator didn't act, we want to look back later
and ask "did we have a real signal? did our judgment on system output
hold up?" Answers both questions: was the system finding signal, and was
the operator filtering it correctly.

TRIGGER RULES
=============
- Research: ticker counts only if paper flag ∈ {thesis, watchlist, longshot}.
  Skip-flagged papers contribute zero. (Charter 2026-05-15 decision.)
- News: ticker counts only if news flag ∈ {read, skim}. Pure-skip noise
  shouldn't pull a ticker over the threshold.
- News tickers extracted via the allowlist in ticker_allowlist.csv to
  prevent prose false positives ("USA", "AI", "CEO", "FDA"...).
- Window: 3+ mentions in any rolling 7-day window. Date = paper's
  run_timestamp for research, posted_at (or fetched_at) for news.
- Permanence: once a ticker is in shadow_portfolio.csv, it stays. The
  threshold is a one-way gate. New mentions don't re-trigger.

OUTPUT
======
shadow_portfolio.csv with columns:
    ticker
    first_trigger_date  (date the 3-mention threshold was crossed)
    trigger_price       (yfinance close on/before that date; blank if no data)
    mention_count_at_trigger
    source_breakdown    (e.g. "research:2, news:1")
    paper_ids           (semicolon-separated, the papers/news that contributed)
    notes               (left blank; operator can hand-edit)

USAGE
=====
    py -3.14 shadow_portfolio.py            # scan + extend
    py -3.14 shadow_portfolio.py --dry-run  # show what would be added, no write
    py -3.14 shadow_portfolio.py --refresh-prices  # re-pull current prices into
                                                   # an in-memory check column;
                                                   # does NOT modify CSV

The Streamlit Analytics page imports this module and calls scan_for_triggers()
+ refresh_current_prices() directly.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from yfinance_wrapper import get_current_price, get_price_on_date


# ---- CONFIG ----------------------------------------------------------------

RESEARCH_GLOB = "results_*.csv"
NEWS_GLOB = "news_results_*.csv"
ALLOWLIST_PATH = "ticker_allowlist.csv"
SHADOW_CSV = "shadow_portfolio.csv"

RESEARCH_ELIGIBLE_FLAGS = {"thesis", "watchlist", "longshot"}
NEWS_ELIGIBLE_FLAGS = {"read", "skim"}

WINDOW_DAYS = 7
THRESHOLD = 3

SHADOW_COLUMNS = [
    "ticker",
    "first_trigger_date",
    "trigger_price",
    "mention_count_at_trigger",
    "source_breakdown",
    "paper_ids",
    "notes",
]


# ---- LOAD ------------------------------------------------------------------

def load_allowlist(path: str = ALLOWLIST_PATH) -> set[str]:
    """Plain CSV → set of upper-case tickers."""
    p = Path(path)
    if not p.exists():
        print(f"[warn] allowlist not found at {path} — news extraction will return nothing")
        return set()
    df = pd.read_csv(p)
    if "ticker" not in df.columns:
        print(f"[warn] {path} missing 'ticker' column")
        return set()
    return {str(t).strip().upper() for t in df["ticker"].dropna() if str(t).strip()}


def load_existing_shadow(path: str = SHADOW_CSV) -> pd.DataFrame:
    """Return existing shadow_portfolio.csv or an empty frame with the schema."""
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=SHADOW_COLUMNS)
    df = pd.read_csv(p)
    # Defensive: ensure all expected columns exist
    for col in SHADOW_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[SHADOW_COLUMNS]


# ---- EXTRACT MENTIONS ------------------------------------------------------

def _parse_vehicles(v) -> list[str]:
    """llm_public_vehicles is a JSON-list-as-string. Return list of upper tickers."""
    if not isinstance(v, str) or not v.strip():
        return []
    try:
        parsed = json.loads(v)
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    out = []
    for item in parsed:
        # llm_public_vehicles entries can be bare strings ("NVDA") or dicts
        # ({"ticker": "NVDA", "name": "NVIDIA"}). Handle both.
        if isinstance(item, str):
            tk = item.strip().upper()
        elif isinstance(item, dict):
            tk = str(item.get("ticker", "")).strip().upper()
        else:
            continue
        # Quick sanity filter: tickers are 1-5 chars, letters/digits/dots/dashes.
        if tk and re.fullmatch(r"[A-Z0-9.\-]{1,6}", tk):
            out.append(tk)
    return out


# Pattern for news ticker extraction. Matches uppercase 1-5 letter sequences
# bounded by non-word chars. We then intersect with allowlist — that's the
# false-positive filter, not the regex.
_TICKER_REGEX = re.compile(r"\b([A-Z]{1,5})\b")


def _extract_news_tickers(text: str, allowlist: set[str]) -> list[str]:
    """Find allowlisted tickers in prose. Returns deduped list per item."""
    if not isinstance(text, str) or not text.strip() or not allowlist:
        return []
    hits = set()
    for m in _TICKER_REGEX.findall(text):
        if m in allowlist:
            hits.add(m)
    return sorted(hits)


def collect_research_mentions() -> pd.DataFrame:
    """
    Walk all results_*.csv files. For each eligible row, yield one mention
    per ticker in llm_public_vehicles.

    Returns frame: [ticker, date, source, paper_id]
    """
    paths = sorted(glob.glob(RESEARCH_GLOB))
    rows: list[dict] = []
    for path in paths:
        try:
            df = pd.read_csv(path)
        except Exception as exc:
            print(f"[warn] could not read {path}: {exc}")
            continue
        if "llm_flag" not in df.columns or "llm_public_vehicles" not in df.columns:
            continue
        eligible = df[df["llm_flag"].isin(RESEARCH_ELIGIBLE_FLAGS)]
        for _, row in eligible.iterrows():
            tickers = _parse_vehicles(row.get("llm_public_vehicles", ""))
            if not tickers:
                continue
            # Prefer run_timestamp (when we scored it) over published; reflects
            # when the system actually saw the signal.
            raw_date = row.get("run_timestamp") or row.get("published") or ""
            try:
                dt = pd.to_datetime(raw_date, errors="coerce", utc=True)
                date_str = dt.strftime("%Y-%m-%d") if pd.notna(dt) else ""
            except Exception:
                date_str = ""
            if not date_str:
                continue
            paper_id = str(row.get("id", "") or "")
            for tk in tickers:
                rows.append({
                    "ticker": tk,
                    "date": date_str,
                    "source": "research",
                    "paper_id": paper_id,
                })
    return pd.DataFrame(rows, columns=["ticker", "date", "source", "paper_id"])


def collect_news_mentions(allowlist: set[str]) -> pd.DataFrame:
    """
    Walk all news_results_*.csv files. For each read/skim row, extract
    allowlisted tickers from llm_translation.

    Returns frame: [ticker, date, source, paper_id]
    """
    paths = sorted(glob.glob(NEWS_GLOB))
    rows: list[dict] = []
    for path in paths:
        try:
            df = pd.read_csv(path)
        except Exception as exc:
            print(f"[warn] could not read {path}: {exc}")
            continue
        if "llm_flag" not in df.columns or "llm_translation" not in df.columns:
            continue
        eligible = df[df["llm_flag"].isin(NEWS_ELIGIBLE_FLAGS)]
        for _, row in eligible.iterrows():
            tickers = _extract_news_tickers(row.get("llm_translation", ""), allowlist)
            if not tickers:
                continue
            # posted_at preferred; fall back to fetched_at then run_timestamp.
            raw_date = (
                row.get("posted_at")
                or row.get("fetched_at")
                or row.get("run_timestamp")
                or ""
            )
            try:
                dt = pd.to_datetime(raw_date, errors="coerce", utc=True)
                date_str = dt.strftime("%Y-%m-%d") if pd.notna(dt) else ""
            except Exception:
                date_str = ""
            if not date_str:
                continue
            item_id = str(row.get("id", "") or "")
            for tk in tickers:
                rows.append({
                    "ticker": tk,
                    "date": date_str,
                    "source": "news",
                    "paper_id": item_id,
                })
    return pd.DataFrame(rows, columns=["ticker", "date", "source", "paper_id"])


# ---- TRIGGER LOGIC ---------------------------------------------------------

def find_trigger_date(
    mentions: pd.DataFrame,
    window_days: int = WINDOW_DAYS,
    threshold: int = THRESHOLD,
) -> Optional[dict]:
    """
    For a single ticker's sorted mentions, find the earliest date such that
    the trailing `window_days`-window contains >= `threshold` mentions.

    Returns the trigger record or None if never triggers. Mentions on the
    same date count separately (a paper + a news item on same day = 2).
    """
    if mentions.empty or len(mentions) < threshold:
        return None

    sorted_mentions = mentions.sort_values("date").reset_index(drop=True)
    sorted_mentions["date_dt"] = pd.to_datetime(sorted_mentions["date"])

    # Sliding window over sorted dates
    n = len(sorted_mentions)
    for i in range(threshold - 1, n):
        window_start = sorted_mentions.loc[i, "date_dt"] - pd.Timedelta(days=window_days - 1)
        in_window = sorted_mentions[
            (sorted_mentions["date_dt"] >= window_start)
            & (sorted_mentions["date_dt"] <= sorted_mentions.loc[i, "date_dt"])
        ]
        if len(in_window) >= threshold:
            source_counts = in_window["source"].value_counts().to_dict()
            breakdown = ", ".join(
                f"{k}:{v}" for k, v in sorted(source_counts.items())
            )
            return {
                "first_trigger_date": sorted_mentions.loc[i, "date"],
                "mention_count_at_trigger": int(len(in_window)),
                "source_breakdown": breakdown,
                "paper_ids": ";".join(in_window["paper_id"].astype(str).tolist()),
            }
    return None


# ---- TOP-LEVEL SCAN --------------------------------------------------------

def scan_for_triggers(
    fetch_prices: bool = True,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Build the up-to-date shadow portfolio. Returns the FULL frame (existing
    rows + any new triggers found this run). Does NOT write to disk — that's
    write_shadow_portfolio()'s job, kept separate for dry-run / UI use.
    """
    allowlist = load_allowlist()
    if verbose:
        print(f"[info] allowlist loaded: {len(allowlist)} tickers")

    existing = load_existing_shadow()
    existing_tickers = set(existing["ticker"].astype(str).str.upper().tolist())
    if verbose:
        print(f"[info] existing shadow portfolio: {len(existing)} ticker(s)")

    research = collect_research_mentions()
    news = collect_news_mentions(allowlist)
    if verbose:
        print(f"[info] research mentions: {len(research)}; news mentions: {len(news)}")

    combined = pd.concat([research, news], ignore_index=True)
    if combined.empty:
        if verbose:
            print("[info] no mentions found; nothing to do")
        return existing

    new_rows = []
    for ticker, grp in combined.groupby("ticker"):
        if ticker in existing_tickers:
            continue  # permanence: don't re-evaluate
        trig = find_trigger_date(grp)
        if trig is None:
            continue
        price = None
        if fetch_prices:
            price = get_price_on_date(ticker, trig["first_trigger_date"])
        new_rows.append({
            "ticker": ticker,
            "first_trigger_date": trig["first_trigger_date"],
            "trigger_price": price if price is not None else "",
            "mention_count_at_trigger": trig["mention_count_at_trigger"],
            "source_breakdown": trig["source_breakdown"],
            "paper_ids": trig["paper_ids"],
            "notes": "",
        })

    if verbose:
        print(f"[info] new triggers this run: {len(new_rows)}")
        for r in new_rows:
            print(
                f"       {r['ticker']:<6} "
                f"date={r['first_trigger_date']} "
                f"price={r['trigger_price']} "
                f"mentions={r['mention_count_at_trigger']} "
                f"({r['source_breakdown']})"
            )

    if new_rows:
        full = pd.concat(
            [existing, pd.DataFrame(new_rows, columns=SHADOW_COLUMNS)],
            ignore_index=True,
        )
    else:
        full = existing
    return full


def write_shadow_portfolio(df: pd.DataFrame, path: str = SHADOW_CSV) -> None:
    """Persist the shadow portfolio CSV."""
    df.to_csv(path, index=False, quoting=csv.QUOTE_MINIMAL)
    print(f"[ok] wrote {len(df)} row(s) to {path}")


def refresh_current_prices(df: pd.DataFrame) -> pd.DataFrame:
    """
    For UI use: return a copy of df with an added 'current_price' and
    'pct_change_since_trigger' column. Does NOT modify the saved CSV.
    """
    out = df.copy()
    out["current_price"] = out["ticker"].map(get_current_price)

    def _pct(row):
        try:
            tp = float(row["trigger_price"])
            cp = float(row["current_price"])
            if tp <= 0:
                return None
            return (cp / tp - 1.0) * 100.0
        except (TypeError, ValueError):
            return None

    out["pct_change_since_trigger"] = out.apply(_pct, axis=1)
    return out


# ---- CLI -------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Shadow Portfolio scanner")
    ap.add_argument("--dry-run", action="store_true",
                    help="Scan and print but do not write shadow_portfolio.csv")
    ap.add_argument("--no-prices", action="store_true",
                    help="Skip yfinance trigger-price lookup (faster, leaves blank)")
    ap.add_argument("--refresh-prices", action="store_true",
                    help="Print current prices for existing shadow_portfolio rows; "
                         "does NOT modify CSV.")
    args = ap.parse_args()

    if args.refresh_prices:
        existing = load_existing_shadow()
        if existing.empty:
            print("[info] shadow portfolio is empty.")
            return
        refreshed = refresh_current_prices(existing)
        for _, row in refreshed.iterrows():
            tp = row.get("trigger_price", "")
            cp = row.get("current_price")
            pc = row.get("pct_change_since_trigger")
            cp_str = f"{cp:.2f}" if isinstance(cp, (int, float)) and pd.notna(cp) else "—"
            pc_str = f"{pc:+.1f}%" if isinstance(pc, (int, float)) and pd.notna(pc) else "—"
            print(f"  {row['ticker']:<6} trigger={tp}  current={cp_str}  Δ={pc_str}")
        return

    full = scan_for_triggers(fetch_prices=not args.no_prices)
    if args.dry_run:
        print("[dry-run] not writing CSV")
        return
    write_shadow_portfolio(full)


if __name__ == "__main__":
    main()
