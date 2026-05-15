# Week 8 Session Closeout — Shadow Portfolio + Portfolio Tab

*Date: 2026-05-15. Single coding session. ~3 hours wall clock.*

## What shipped

All four artifacts from the build brief landed end-to-end:

1. **`yfinance_wrapper.py`** (new, 196 lines) — single point of contact with
   yfinance. Three public functions (`get_current_price`, `get_price_on_date`,
   `get_history`) plus a `get_many_current_prices` batch helper. Every call
   wrapped in try/except — broken ticker returns `None` / empty DataFrame,
   never raises. Module-level `WARN_LOG` captures failures for debugging.
   No Streamlit dependency at module load (caching applied at call sites).
   Standalone smoke test: `py -3.14 yfinance_wrapper.py NVDA AAPL ZZZZZZ`.

2. **`ticker_allowlist.csv`** (new, 203 tickers after pruning) — hand-curated
   list covering operator's 8 domains + obvious mega-caps. Used by
   `shadow_portfolio.py` to filter news-prose ticker extraction. False
   positives caught in dry-run testing (see Decisions below).

3. **`shadow_portfolio.py`** (new, 438 lines) — paths-not-taken tracker.
   Scans `results_*.csv` (thesis/watchlist/longshot only) and
   `news_results_*.csv` (read/skim only) for ticker mentions, applies the
   3-mentions-in-7-days rolling trigger, snapshots price via yfinance on
   threshold-crossing date, writes append-only to `shadow_portfolio.csv`.
   Permanence guaranteed — once a ticker triggers it's never re-evaluated.
   CLI: `--dry-run`, `--no-prices`, `--refresh-prices`. Also importable from
   the Analytics page; exposes `scan_for_triggers()`, `write_shadow_portfolio()`,
   `refresh_current_prices()` for UI use.

4. **`shadow_portfolio.csv`** (new, header-only) — left empty by design so
   the first run happens via the Analytics page "Scan for new triggers"
   button. Validates the UI path on first open.

5. **`holdings.csv`** (new, 52 rows) — schema `ticker, broker, shares,
   cost_basis_per_share, purchase_date, notes`. Populated in-session from
   operator's ETrade PortfolioDownload.csv (19 positions, per-lot rows
   aggregated to weighted-avg) and Webull screenshot (33 positions
   transcribed manually). ETrade cost-basis sum $31,801.54 vs statement
   $31,808.49 (within $7 rounding); Webull mkt value sum $45,554.71 vs
   operator-stated $45,608 (within $54 timing noise).

6. **`pages/2_Analytics.py`** (modified) — added `render_shadow_portfolio()`
   below the existing watchlist-aging section. Sortable table with current
   prices, % change since trigger, Refresh button + Scan button. Both
   buttons clear the 1-hour TTL cache.

7. **`week4_digest.py`** (modified) — added third tab `Portfolio` alongside
   Research / News. Holdings table with computed market value / gain-loss /
   % of portfolio, broker filter, KPI strip (total MV, cost basis, GL$, GL%,
   positions). Below: per-ticker historical chart with 1M/6M/1Y/5Y toggle
   and ticker selectbox. Refresh button clears price + history cache. Empty
   state when `holdings.csv` has no rows. All widgets keyed with
   `portfolio_` prefix per the existing pattern. Also added cross-broker
   **rollup toggle** ("Rolled up" / "By broker", default rolled up):
   collapses (ticker × broker) duplicates into one row per ticker with
   summed shares and weighted-avg cost basis. Disabled when a specific
   broker is selected (rollup is trivial in that case). Operator currently
   has 3 multi-broker positions (GOOG, LAC, NVDA) so this matters.

## Verification done

- `python3 -c "import ast; ast.parse(...)"` passes on all four .py files.
- `python3 shadow_portfolio.py --dry-run --no-prices` runs end-to-end against
  the real corpus (147 research mentions + 83 news mentions after allowlist
  fixes); identifies 17 ticker triggers including LAC, NVDA, IONQ, GOOGL,
  AMZN, MSFT, ISRG, RGTI, SYM, TER, MBLY, COHR, GM, ALB, TSLA, SDGR, QUBT.
- yfinance integration is sandbox-only verified at the wrapper level. Real
  network calls happen when operator opens Analytics / Portfolio tabs.

## In-session decisions

### Allowlist pruning (the "AI" problem)

First dry-run produced 19 triggers including `AI` at 21 news mentions and
`VT` at 5 news mentions. Inspection revealed both were natural-language
matches in prose translations ("AI" the technology, "VT" inside
abbreviations like "EV/VT" or as token chunks), not the actual tickers
C3.ai and Vanguard Total World.

**Dropped from allowlist:**
- `AI` (C3.ai) — every match was the English word "AI"
- `VT` (Vanguard Total World) — operator's holding, but every news match
  was prose noise. Research path (structured JSON `llm_public_vehicles`)
  is unaffected; if a paper ever names VT it'll still trigger.
- `ON` (ON Semiconductor) — common English word
- `D` (Dominion Energy) — single-letter, matched alongside AI noise

**Kept despite some risk:**
- `F` (Ford) — single-letter, but real Ford mentions in EV news fired
  correctly alongside GM. Watch for false positives.
- `GM` (General Motors) — fired correctly in EV-trade-policy stories.

**Validated as legitimate (left in):**
- `LAC` triggered 20 times in news because the Haiku news scorer's
  translations parenthetically cite operator's portfolio holdings
  ("battery/EV thesis (LAC) benefits..."). This is by-design behavior of
  the news rubric, not a false positive. Shadow portfolio correctly
  captures it — useful as a calibration data point ("LAC kept showing up
  while you held it; did the system's view track yours?").

### Stayed standalone (`shadow_portfolio.py` not chained into `scheduled_run.py`)

Per kickoff decision. Folding into the every-2-days automated run is
deferred to a follow-up session — small change, but keeps blast radius
narrow this round. The Analytics page "Scan for new triggers" button
covers manual invocation.

### Broker APIs explicitly ruled out (again)

Operator asked mid-session if Webull/ETrade APIs were worth wiring up
instead of manual CSV. Answer was no, with reasoning preserved here for
future revisit: Webull has no public API (community reverse-engineered
package is fragile and TOS-violating); ETrade has an API but it's OAuth
1.0a + dev-registration paperwork, ~4-8 hours of work for ongoing token
maintenance. Charter 2026-05-15 already carved this out, and it's still
the right call. Instead we parsed the existing ETrade CSV export and
transcribed the Webull screenshot — got accurate cost-basis numbers in
under 10 minutes.

### Empty initial `shadow_portfolio.csv`

Chose to ship the CSV empty rather than pre-populating it from the 17
dry-run triggers. Reasoning: first user-facing action will be operator
clicking "Scan for new triggers" on the Analytics page, which exercises
the full UI path and writes the CSV. Validates the button works before
operator depends on it. Alternative was to pre-populate and the operator
might never test the button path until something broke.

### CRLF/Edit-tool corruption hit again (charter 2026-05-12 lesson held)

Edit tool reported success on `week4_digest.py` insertion but disk had a
truncated tail ("with por" mid-line at line 1242). Recovered exactly as
the 2026-05-12 entry prescribed: `git show HEAD:week4_digest.py > /tmp/clean.py`,
applied edits programmatically in a single Python script with line-ending
detection, wrote once with `open(..., newline='')`. Final file parses, has
the expected 1241 lines, tail intact.

**Note for future sessions:** the file's current line endings on disk are
LF, not CRLF as the charter implied. Either it was normalized in a recent
commit or the CRLF charter note conflated WSL-view with native view.
Either way the corruption pattern reproduced — so the lesson stands. On
this file, prefer programmatic patches over Edit tool for inserts >100 lines.

## Earn-its-keep gates (per charter §10)

- **Shadow portfolio:** no formal gate set — passive feature, near-zero
  cost. Re-evaluate at the Day 45 thesis checkpoint if it hasn't surfaced
  anything actionable.
- **Portfolio tab:** 30 days from build (2026-06-14). Operator should be
  opening the tab ≥3x/week. If not, deprecate or simplify.

## Deferred / not in this build

- **Chaining `shadow_portfolio.py` into `scheduled_run.py`** — should land
  next session. ~15 min change. Charter §10 item #7 (news-into-scheduled)
  is the same pattern; do both together.
- **News-tab analytics additions** (signal/market_impact over time, source
  heat, tag distribution) — still gated on news layer earning its keep.
- **Portfolio tab features the operator explicitly said no to**: real-time
  tick, options, crypto, dividend tracking, tax lots, broker auto-sync,
  thesis linking to research/news cards. Each is its own earn-its-keep
  case if/when revisited.
- **Allowlist hygiene policy** — no formal process. If the shadow portfolio
  starts producing obvious noise tickers, prune by hand. If pruning gets
  frequent, consider switching to a context-aware extraction (e.g. require
  the ticker to appear in parentheses or after a company name).

## Files touched

| File | Action | Lines |
|------|--------|------:|
| `yfinance_wrapper.py`     | new       | 196 |
| `shadow_portfolio.py`     | new       | 438 |
| `ticker_allowlist.csv`    | new       | 204 |
| `shadow_portfolio.csv`    | new       |   1 |
| `holdings.csv`            | new       |  53 (52 positions + header) |
| `pages/2_Analytics.py`    | modified  | 577 (was ~456) |
| `week4_digest.py`         | modified  | 1292 (was 1015) |

## Recommended next session work

1. Operator: open the Streamlit deploy, hit the Portfolio tab, confirm the
   52 positions render with current prices. Toggle "Rolled up" / "By broker"
   to verify GOOG, LAC, NVDA collapse correctly (47.94 NVDA @ $42.69 avg
   in rolled-up mode; 47.54 ETrade + 0.40 Webull when split).
2. Operator: open Analytics, scroll to Shadow Portfolio, hit "Scan for new
   triggers", confirm the table renders with current prices and % moves.
3. If both work, fold `shadow_portfolio.py` into `scheduled_run.py` so
   weekly scans happen automatically (charter §10 item #7 territory).
4. Watch the shadow portfolio for 30 days. The interesting question is
   whether any ticker triggered before a meaningful price move — that's
   the feedback loop this feature was built to surface.
