# Week 8 Coding Session Brief — Shadow Portfolio + Portfolio Tab

*Paste this into the Week 8 coding session. Charter is the source of truth; this is the build-scoped extract.*

## What we're building this session

Two features that share infrastructure (yfinance wrapper). Build them in the same session so the wrapper lands once.

1. **Shadow portfolio** — automatic capture of recurring tickers across research + news output, with price at first-mention. Feedback loop on whether the system surfaces names before they run.
2. **Portfolio tab** — manual `holdings.csv` driven view of Webull + ETrade positions with current prices and per-ticker historical charts.

## Why these, why now

- Both depend on yfinance for price data; building together avoids duplicating the wrapper.
- Portfolio tab is operator-utility, NOT Trend Engine mission. It earns its place because (a) infra overlap and (b) predicted higher daily digest engagement → feeds the §3 "daily digest the operator actually opens" success criterion.
- Strict guardrail: if scope creep starts (thesis tracking, sector breakdowns, options analytics), pull back. Those are separate features needing their own earn-its-keep cases.

## Hard constraints

- **Never modify .py files outside this session's scope** without operator OK.
- yfinance only — no paid feeds, no real-time tick data. yfinance is delayed/historical, which keeps us inside §4 "real-time market data out of scope."
- Every yfinance call wrapped in try/except. Broken ticker shows "—", doesn't crash the page or halt trigger logic.
- Session-cached prices via `@st.cache_data(ttl=3600)`. Refresh button clears cache. **No scheduled yfinance calls.**
- $50/mo tool budget unchanged. yfinance is free; this should add ~$0.

---

## Feature 1: Shadow Portfolio

### Trigger logic
- Watch both research output (`results_*.csv` → `llm_public_vehicles` column) and news output (`news_*.csv` → translations / extracted tickers).
- **Trigger condition:** ticker appears 3+ times in a rolling 7-day window across both content types combined.
- On trigger: snapshot the ticker's price at that date, write a row to `shadow_portfolio.csv`.

### Schema (`shadow_portfolio.csv`)
Suggested columns (refine in session):
- `ticker`
- `first_trigger_date` (date 3-mention threshold was crossed)
- `trigger_price` (yfinance close on that date)
- `mention_count_at_trigger`
- `source_breakdown` (e.g., "research:2, news:1")
- `notes` (free text — operator can annotate)

### Ticker extraction — two paths
- **Research:** `llm_public_vehicles` is already structured (LLM-output ticker list). Parse directly.
- **News:** translations are prose. Use an **allowlist of ~200 plausible tickers** to avoid false positives like "USA", "AI", "CEO", "FDA". Start with: operator's current holdings + tickers that have appeared in `llm_public_vehicles` historically + a hand-curated list of obvious major names (NVDA, AAPL, MSFT, GOOG, AMZN, META, TSLA, etc.). Don't try to be clever — false positives are worse than misses here.

### UI
- New section on `pages/2_Analytics.py` (not a new page).
- Sortable table of shadow-portfolio entries with current price + % change since trigger.
- "Refresh prices" button — on-demand only, no scheduled API calls.

### Files to create / touch
- NEW: `shadow_portfolio.py` — the trigger logic + price snapshot + CSV writer. Standalone script, runnable manually or chainable into `scheduled_run.py` later.
- NEW: `shadow_portfolio.csv` — output (initially empty header row).
- EDIT: `pages/2_Analytics.py` — add shadow portfolio section.
- NEW (shared): `yfinance_wrapper.py` (or inline in a utils module) — see below.

### Design subtleties to resolve in-session
1. **Ticker allowlist source of truth.** Hardcoded list in `shadow_portfolio.py`? Separate `ticker_allowlist.csv`? Operator-confirmed at 2026-05-12: "hand-curated allowlist of ~200 plausible tickers." Pick the simplest version that works.
2. **What counts as "in research"** — every `llm_public_vehicles` mention, or only papers with flag ∈ {thesis, watchlist, longshot}? Skip-flagged papers probably shouldn't trigger. Decide and document.
3. **Rolling-window edge:** if a ticker triggers, then drops below 3 mentions later, does it stay in shadow portfolio? Yes — once triggered, it's permanent. Threshold is a one-way gate.

---

## Feature 2: Portfolio Tab

### Schema (`holdings.csv`)
Exact columns per 2026-05-15 decision:
- `ticker`
- `broker` (Webull / ETrade)
- `shares`
- `cost_basis_per_share`
- `purchase_date`
- `notes`

Manually edited by operator on trades. No broker auto-sync.

### UI in `week4_digest.py`
Add a **third tab** alongside Research / News: **Portfolio**.

**Top section — holdings table**
- Columns: ticker, broker, shares, avg cost, current price, market value, gain/loss $, gain/loss %, % of total.
- Broker filter: All / Webull / ETrade.
- Sort by market value (default).

**Bottom section — per-ticker historical chart**
- Toggle: 1M / 6M / 1Y / 5Y.
- Selection: click row in table (st.session_state.selected_ticker) OR dropdown fallback if click-handling is fiddly.
- yfinance history.

**Refresh button** at top of tab — clears `@st.cache_data` so next render hits yfinance live.

### Files to create / touch
- NEW: `holdings.csv` (operator will populate; ship with header row + maybe 1 example commented out).
- EDIT: `week4_digest.py` — add third tab. **Watch for the Streamlit DuplicateWidgetID error pattern** that bit us on the news tab. Prefix all portfolio-tab widget keys with `portfolio_`.

### Explicitly NOT in this build
- Real-time tick data
- Options / crypto
- Dividend tracking
- Tax lots
- Broker auto-sync (Webull has no public API; ETrade requires OAuth + dev agreement)
- Thesis-linking (deferred)

---

## Shared infrastructure: yfinance wrapper

Build once, both features use it. Suggested signature:

```python
def get_current_price(ticker: str) -> float | None:
    """Returns current/most-recent close. None on failure."""

def get_history(ticker: str, period: str) -> pd.DataFrame | None:
    """period in {'1mo', '6mo', '1y', '5y'}. None on failure."""

def get_price_on_date(ticker: str, date: str) -> float | None:
    """Closest close on or before date. None on failure."""
```

Every call wrapped in try/except. Log warnings on failure, don't raise. Cache with `@st.cache_data(ttl=3600)` at the call site where Streamlit context exists; pure-Python callers (shadow_portfolio.py running standalone) bypass cache.

---

## Files the coding agent will care about

From charter §10:
- `week4_digest.py` — has Research + News tabs already, ~1000 lines, **CRLF line endings** — known fragile under Edit tool on large files. Verify with `wc -l` + `tail` + `python3 -c "ast.parse"` after each substantial edit. If corruption appears, `git restore` rather than incremental patch. (See 2026-05-12 decision log entry on the corruption saga.)
- `pages/2_Analytics.py` — cross-corpus dashboard, gets shadow portfolio section appended.
- `results_*.csv` files — research scorer output. `llm_public_vehicles` column is the source for research-side ticker mentions.
- `news_*.csv` files — news scorer output. Translation field is the source for news-side ticker mentions (extract via allowlist).
- `.streamlit/config.toml` — forces dark theme. Portfolio tab CSS should assume dark background like the others.

## Estimated effort

2–3 hours combined per the 2026-05-15 decision entry. Earn-its-keep on Portfolio tab: 30 days from build, operator should be opening it ≥3x/week.

## Definition of done for this session

1. `yfinance_wrapper.py` (or equivalent) exists, every call wrapped in try/except.
2. `shadow_portfolio.py` runs, scans existing `results_*.csv` + `news_*.csv`, writes `shadow_portfolio.csv` with at least the schema above. Allowlist documented.
3. Analytics page shows shadow portfolio section with sortable table + Refresh button.
4. `week4_digest.py` has a Portfolio tab with holdings table + per-ticker chart toggle, driven off `holdings.csv`.
5. `holdings.csv` shipped with header row.
6. Everything pushes to GitHub and renders on Streamlit Cloud without crashing on the first ticker yfinance can't find.
7. **Closeout doc written** (`week8_session_closeout.md`) covering: what shipped, what didn't, design decisions made in-session (especially around ticker allowlist + edge cases listed above), any new earn-its-keep gates.

Once the closeout lands, the file-maintenance agent will fold the decisions into §9 and update §10 Current Status / Next Actions.
