"""
yfinance wrapper — single point of contact with the yfinance library.
---------------------------------------------------------------------
Built Week 8. Used by both shadow_portfolio.py (standalone script) and
week4_digest.py / pages/2_Analytics.py (Streamlit context).

Design rules:
- EVERY external call wrapped in try/except. Network errors, ticker-not-found,
  yfinance schema changes — all surface as `None` / empty DataFrame, never
  a raised exception. The pipeline must keep going when one ticker breaks.
- Module-level import of yfinance is the only hard dependency. Streamlit
  caching is applied AT CALL SITES (pages/digest) via @st.cache_data, NOT
  here, so this module stays importable from pure-Python contexts.
- One module-level WARN_LOG list captures failures for debugging — callers
  can dump it if a row goes blank and they want to know why.

Pricing model:
- get_current_price: most-recent close. yfinance is delayed/historical,
  NOT real-time tick — this matches charter §4 "real-time market data out
  of scope." Caller decides cache TTL.
- get_price_on_date: closest close ON OR BEFORE the given date. Used by
  shadow_portfolio.py to snapshot a price at threshold-crossing date even
  if that date was a weekend/holiday.
- get_history: period-string passthrough to yfinance. Returns the full
  DataFrame so caller can plot Close, Volume, whatever.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd

try:
    import yfinance as yf
    _YF_AVAILABLE = True
except ImportError:
    _YF_AVAILABLE = False
    yf = None  # sentinel; callers will get None back from every function


logger = logging.getLogger(__name__)

# Diagnostic log — callers can introspect after a batch run to see what
# failed and why. Capped to prevent unbounded memory if a script loops.
WARN_LOG: list[str] = []
_WARN_CAP = 500


def _warn(msg: str) -> None:
    logger.warning(msg)
    if len(WARN_LOG) < _WARN_CAP:
        WARN_LOG.append(msg)


def yfinance_available() -> bool:
    """Cheap probe so the UI can show 'yfinance not installed' rather than crash."""
    return _YF_AVAILABLE


def get_current_price(ticker: str) -> Optional[float]:
    """
    Most recent close for `ticker`.

    Returns None on any failure: missing yfinance, unknown ticker, empty
    response, network blip. Never raises.
    """
    if not _YF_AVAILABLE:
        _warn("yfinance not installed; install with: pip install yfinance")
        return None
    if not ticker or not isinstance(ticker, str):
        return None
    try:
        t = yf.Ticker(ticker)
        # Pull 5 trading days to be robust to weekends/holidays;
        # we only want the most recent close.
        hist = t.history(period="5d", auto_adjust=False)
        if hist is None or hist.empty:
            _warn(f"get_current_price({ticker!r}): empty history")
            return None
        last_close = hist["Close"].iloc[-1]
        if pd.isna(last_close):
            _warn(f"get_current_price({ticker!r}): last close is NaN")
            return None
        return float(last_close)
    except Exception as exc:
        _warn(f"get_current_price({ticker!r}) raised: {exc!r}")
        return None


def get_price_on_date(ticker: str, target: str | date | datetime) -> Optional[float]:
    """
    Closing price on or before `target` date.

    Used by shadow_portfolio.py to snapshot a price at threshold-crossing
    date. If the target falls on a weekend / holiday / pre-IPO date, we
    walk BACKWARD up to 10 days looking for the nearest trading day.
    Returning None means "no trading data within 10 days before target."
    """
    if not _YF_AVAILABLE:
        _warn("yfinance not installed")
        return None
    if not ticker:
        return None

    # Normalize target → date object
    if isinstance(target, str):
        try:
            target_date = datetime.fromisoformat(target[:10]).date()
        except ValueError:
            _warn(f"get_price_on_date({ticker!r}, {target!r}): unparseable date")
            return None
    elif isinstance(target, datetime):
        target_date = target.date()
    elif isinstance(target, date):
        target_date = target
    else:
        _warn(f"get_price_on_date({ticker!r}, {target!r}): bad target type")
        return None

    try:
        t = yf.Ticker(ticker)
        # Pull a window ending the day AFTER target so target itself is included
        start = (target_date - timedelta(days=10)).isoformat()
        end = (target_date + timedelta(days=1)).isoformat()
        hist = t.history(start=start, end=end, auto_adjust=False)
        if hist is None or hist.empty:
            _warn(f"get_price_on_date({ticker!r}, {target_date}): empty history")
            return None
        # Drop any rows after the target date (defensive — yfinance shouldn't
        # return them given the end= bound, but timezones occasionally surprise).
        hist = hist[hist.index.date <= target_date]
        if hist.empty:
            _warn(f"get_price_on_date({ticker!r}, {target_date}): no rows on/before target")
            return None
        last_close = hist["Close"].iloc[-1]
        if pd.isna(last_close):
            return None
        return float(last_close)
    except Exception as exc:
        _warn(f"get_price_on_date({ticker!r}, {target}) raised: {exc!r}")
        return None


def get_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """
    Historical price DataFrame for `ticker` over `period`.

    `period` is passed straight through to yfinance.Ticker.history(period=...).
    Valid: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max.

    Returns an EMPTY DataFrame on failure (not None) so callers can chain
    .empty / .plot without a None check.
    """
    empty = pd.DataFrame()
    if not _YF_AVAILABLE:
        _warn("yfinance not installed")
        return empty
    if not ticker:
        return empty
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=period, auto_adjust=False)
        if hist is None:
            return empty
        return hist
    except Exception as exc:
        _warn(f"get_history({ticker!r}, {period!r}) raised: {exc!r}")
        return empty


def get_many_current_prices(tickers: list[str]) -> dict[str, Optional[float]]:
    """
    Batch convenience for the Portfolio tab and shadow portfolio refresh.

    Sequential, not parallel — yfinance's batch endpoint is finicky and the
    failure mode (one bad ticker poisoning the batch) is worse than the
    extra latency. ~0.5s per ticker; fine for portfolios under 100 names.
    """
    out: dict[str, Optional[float]] = {}
    for t in tickers:
        out[t] = get_current_price(t)
    return out


if __name__ == "__main__":
    # Smoke test — `py -3.14 yfinance_wrapper.py NVDA AAPL`
    import sys
    test_tickers = sys.argv[1:] or ["NVDA", "AAPL", "ZZZZZZ"]
    print(f"yfinance available: {yfinance_available()}")
    for tk in test_tickers:
        p = get_current_price(tk)
        print(f"  {tk}: {p}")
    print(f"warnings: {WARN_LOG}")
