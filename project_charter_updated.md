# Project Charter: Automated Trend-Spotting Engine

*This document is the single source of truth for the project. It lives in the Claude Project knowledge base and is loaded at the start of every conversation. Update it as decisions get made.*

*Last updated: 2026-05-15 • Owner: Jamie Mancuso*

## 1. Mission / North Star

Build a personal intelligence system that surfaces emerging technological paradigm shifts across 8 research domains **before they reach mainstream awareness**, to inform strategic investment and career decisions.

The reference example: catching something like the 2017 "Attention Is All You Need" paper in the weeks after publication, not after ChatGPT launched.

**Caveat on the reference example:** given this operator's 2-year decision horizon (see §2), the real target is not the 2017 research-phase moment — it's the 2021–22 commercialization-phase moment. This system is catching third-wave paradigm shifts, not first-wave. That is a more tractable target and honestly the one where non-insider retail money is actually made.

## 2. About the Operator

### Background

- CS degree + Marketing degree (data analytics focus), graduated May 2025.
- Ops Analyst role since Oct 2025 — primarily Power BI dashboards and data visualization.
- Rusty Python, comfortable with concepts, actively relearning.
- Hidden asset: data modeling / DAX / dashboard presentation to non-technical stakeholders is directly transferable to this project.

### Stakes / Arena

- **Primary:** retail investor. Concentrated thematic, long holds. Current portfolio ~$80k, primarily NVDA, LAC, VT. ~+$50k realized/unrealized on the thematic picks — track record shows this operator can pick paradigm-shift-adjacent names and hold them. This system is designed to amplify that skill, not replace it.
- **Secondary:** career capital, slow burn. Not leaving current role for ~18 months. "Career signal" here = what skills/domains to invest learning time in now so future options exist, NOT "what job next."
- Both legs are live, but the system leans stakes — decisions have real money and career years behind them.

### Time horizon for decisions

- 2 years. Themes that play out over quarters and earnings cycles.
- Implication: system should surface thesis-maturation signals (3rd/4th strong paper on X, commercialization milestones, hiring signals) — NOT just first-discovery papers.
- Biggest risk: signals arriving after they're already priced in. System must flag the "under-appreciated → consensus" transition, not just novelty.

### Weekly time commitment

- 4–6 hours/week, realistically ~4 effective hours after context-switching overhead.
- 90-day budget: ~52 hours total. Roadmap scoped accordingly.
- Time budget must eventually include *using* the system, not just building it. Daily digest review = 15–30 min/day once operational.

### Tool budget

- $50/month ceiling for the next 6 months.
- Anything above ceiling requires explicit cut elsewhere to make room.
- Paid data feeds (Bloomberg, Koyfin, Pitchbook) explicitly OUT OF SCOPE — thesis is open-data signal-finding.
- **Revised cost model (from Week 2 actuals):** LLM API ~$30–35/mo uncached (18-paper eval = $0.23; full 144-paper run = ~$1.90; every-other-day cadence = ~$28–32/mo). Prompt caching will cut this ~90% once rubric is locked — target post-Week 3. Existing AI subscription ~$20. Total ~$40–50/mo at ceiling before caching kicks in.

### Learning mode

- Adaptive by default — teach on genuinely new concepts, move fast on familiar territory.
- Operator overrides per-session with "fast mode" or "teach me this."

### Existing info diet

- Light-to-moderate. YouTube (Atrioc, Lemonade Stand, occasional WSJ/FT video), Reddit news feed, passive scroll.
- No FT/NYT currently (lapsed post-graduation). All current sources are lagging indicators — smart people reacting to news, not upstream of it.
- **Gap:** no upstream specialist sources to cross-reference system output against. Worth filling cheaply over time with 2–3 reference sources per domain (reference material, not daily reading).
- **Edge:** the system is competing against other retail investors with similar lagging diets — not against specialists reading Stratechery + The Information + Import AI. That edge is real but specifically narrow.

## 3. Goals & Success Criteria

### 90-day success (concrete — mid-July 2026)

**Core (must ship):**
- A daily/weekly digest the operator actually opens and reads.
- Visibly improved Python fluency as a byproduct of building it (write the code, debug own errors, don't just paste AI output).

**Stretch (gated — only attempted if core is genuinely working by Day 45):**
- 1–2 written investment theses derived from system-surfaced signals, each containing: the claim, evidence (traceable to signals), mechanism (why this makes money), risks (3+ credible failure modes), invalidation criteria (specific observable events, NOT stop-losses), action plan.
- Length: 2–4 pages each. Written for future-self to honestly judge in 18 months whether the thesis was right, wrong, or lucky.

**Day 45 go/no-go on stretch:** if digest isn't surfacing credible signal by Day 45, drop the stretch. Do not fake theses to hit the milestone.

### 12-month success

- A running daily/weekly digest the operator still reads.
- At least one acted-on decision (investment, career, or skill focus) that traces back to a system-surfaced signal, with a written thesis on file.
- Demonstrable improvement in Python fluency through building this.

### What this is NOT

- A financial trading bot.
- A public product.
- A general-purpose news aggregator (Feedly already exists).
- A portfolio piece for job-hopping — operator is not leaving current role for ~18 months. If it becomes portfolio-grade as a byproduct, fine, but not a goal.
- A replacement for a specialist info diet — it's a complement. It does not replace reading.

## 4. Scope

### In scope (research domains)

| Domain | arXiv categories | Notes |
| :---- | :---- | :---- |
| AI | cs.AI, cs.LG, cs.CL | Highest volume, most signal |
| Bio | q-bio.BM, q-bio.GN, q-bio.QM | Computational bio; AlphaFold-style work |
| Health | q-bio.NC, q-bio.TO, q-bio.PE | Add medRxiv later for clinical coverage |
| Space | astro-ph.EP, astro-ph.IM, astro-ph.HE, astro-ph.SR | Narrow signal; supplement with NASA/ESA RSS |
| Quantum | quant-ph | High investment relevance |
| Robotics | cs.RO | Humanoid / autonomy focus |
| Energy | cond-mat.mtrl-sci, cond-mat.supr-con, physics.app-ph | Batteries, solar, superconductors |
| Climate | physics.ao-ph | Lower signal-to-noise for investing |

### Planned future sources (not yet integrated)

- bioRxiv (real clinical/medical preprints)
- medRxiv (medical preprints)
- Hacker News API (technology signal)
- Reddit via PRAW (r/MachineLearning, r/localllama)
- **Semantic Scholar API** — citation velocity. Week 3 target. For a 2-year horizon this is arguably the single most valuable signal: converts "stylistic maturation" into "this is actually the 3rd convergent result on topic X."
- Company research blogs (DeepMind, OpenAI, Anthropic, Meta FAIR, Microsoft Research)
- VC blogs (a16z, Sequoia, USV)

### Explicitly out of scope

- Real-time market data / stock prices
- Auto-executing trades
- Sentiment analysis on Twitter/X
- Building this into a product for others
- Paid data feeds (Bloomberg, Koyfin, Pitchbook, etc.)

## 5. Constraints & Assumptions

- **Skill:** Rusty Python, comfortable with concepts, needs explanations of new libraries.
- **OS:** Windows 10/11.
- **Python:** 3.14 (installed via Python launcher, `py -3.14`).
- **Infrastructure:** Local machine for now; cloud deploy/automation at Week 6+.
- **Storage:** CSV snapshots (dated, append-only); no database until CSV querying causes real friction.
- **Budget:** $50/month ceiling. Paid data feeds out of scope.

## 6. Tech Stack (as of now)

| Layer | Chosen | Rationale |
| :---- | :---- | :---- |
| Language | Python 3.14 | Low barrier, best ecosystem for scraping + ML |
| Fetching | feedparser + arXiv API | Simple, robust, no auth needed |
| Storage | Dated CSV snapshots in `snapshots/`; `arxiv_papers.csv` as latest-pointer | Zero setup; revisit when cross-history querying causes friction |
| Scheduling | Manual runs, every other day | Cadence matches operator's time budget; cuts API cost in half vs. daily |
| Scoring | Claude Sonnet 4.6 API via `week2_run_scoring.py` | Strong calibration confirmed on eval set; v0.2 prompt stable |
| Citation velocity | Semantic Scholar API (Week 3) | Free, no auth for basic use; adds the substantive maturation signal LLM abstract-scoring can't provide |
| Vector DB | Deferred | Don't add until keyword search fails |
| UI | Deferred | Terminal + CSV first; Streamlit only when needed |

## 7. Roadmap

*Weeks are approximate. At 4 effective hours/week, a "week" may be 1–3 calendar weeks. The Day 45 checkpoint (Wk 5) gates the stretch goal.*

| Week | Milestone | Status |
| :---- | :---- | :---- |
| 1 | Fetch papers from 8 domains → dated CSV snapshots | ✅ DONE |
| 2 | LLM scoring: prompt design + hand-scored eval set + API wiring + eval run | ✅ DONE |
| 3 | Add Semantic Scholar citation velocity (critical for 2yr horizon) | 🟡 Deferred indefinitely — fresh papers have no citations at fetch time |
| 4 | Streamlit digest (cards, filters, score badges) — local first | ✅ DONE |
| 5 | Prompt caching · GitHub deploy · multi-run digest · pipeline runner · global dedup · Horizon score · longshot flag · per-score explanations · detail page · Windows Task Scheduler automation | ✅ DONE |
| 6 | Analytics dashboard — trend velocity, domain heat, watchlist revisit across scored corpus | ✅ DONE |
| 7 | News layer scoping (no code yet — architecture locked, build trigger defined) | ✅ Scoped 2026-05-07 |
| 8 | Broader news/FT-replacement layer: trade press, RSS, structured summarization | Not started |
| 9 | Use the system. Tune. Kill features that don't earn their keep. | Not started |
| 10–13 | STRETCH: Draft 1–2 investment theses from system-surfaced signals | Gated on Day 45 (~June 1) |
| Later | Vector embeddings / SQLite migration — only if CSV querying causes real friction | Deferred |

## 8. Working Principles with Claude

These are the rules of engagement to get maximum leverage from AI in this project.

### Principles I commit to

- **Give Claude full context.** Not "help me write a function" — instead "I'm building [project], I'm at [stage], I know [X], here's my constraint [Y], here's what I'm trying to accomplish [Z]."
- **Ask for tradeoffs, not verdicts.** For any consequential choice, I ask Claude to lay out options and tradeoffs, then *I* decide. Claude doesn't decide for me.
- **Log decisions with rationale.** When we pick X over Y, I update the Decisions Log below with *why*.
- **Verify before acting.** Claude can hallucinate current facts, prices, and product details. Anything before action goes through sanity check (search, official docs, or my own verification).
- **Small commits, visible progress.** Every session ends with something working, even if small. Momentum > perfection.
- **Earn-its-keep gate.** Every 2–3 weeks, ask: is this feature actually being used? Kill what isn't. The simple version usually suffices.
- **Write the thesis before buying.** No buying a stock held <30 days without a written thesis first. Retrospective thesis-writing is rationalization, not analysis.
- **Adaptive learning mode.** Default: teach deeply on new concepts, move fast on familiar. I override with "fast mode" or "teach me this" per session.
- **Stop at clean seams.** When a session completes a coherent sub-task, switch to a fresh chat rather than pushing through long context. Preserves attention quality and forces state to live in files, not chat history.

### What I use Claude for

- Code drafting with explanation
- Code review and debugging
- Teaching me concepts as I encounter them
- Brainstorming approaches and surfacing blind spots
- Drafting research summaries and synthesis
- Writing documentation

### What I do NOT use Claude for

- Final investment decisions (Claude explains; I decide)
- Real-time market data without web search verification
- Anything I can't sanity-check myself

### Claude's standing instructions (copy to Project Instructions)

*I'm running a multi-month research engineering project to surface emerging technological paradigm shifts for a 2-year retail investment horizon and long-run career capital. I have a CS + Marketing (data analytics) degree and work as an Ops Analyst doing Power BI; I'm actively relearning Python. When writing code, default to adaptive teaching — explain new concepts, move fast on familiar ones; I'll say "fast mode" or "teach me this" to override. When I face a decision, give me tradeoffs not verdicts. Always flag assumptions. When your answer depends on recent facts, search the web rather than guess. Tell me what I'm not thinking about. Push back when I overscope. Help me stay under a $50/month tool budget.*

## 9. Decisions Log

*Append-only. Every consequential choice goes here with a one-line rationale. When we revisit, we can see why we made past calls.*

| Date | Decision | Why |
| :---- | :---- | :---- |
| 2026-04-17 | Start with arXiv only (no bioRxiv/HN yet) | Minimize moving parts; validate core loop first |
| 2026-04-17 | CSV over database | Zero setup; revisit when volume justifies it |
| 2026-04-17 | Python over no-code (Zapier/Airtable) | Aligns with learning goal; no rate limits; data stays unified |
| 2026-04-17 | 8 domains chosen (AI, Bio, Health, Space, Quantum, Robotics, Energy, Climate) | Covers major paradigm-shift territory for investing/career |
| 2026-04-17 | Defer vector DB until keyword/LLM scoring proves insufficient | Don't add complexity before it's needed |
| 2026-04-17 | 2-year decision horizon; optimize for thesis-maturation signals, not first-discovery | Matches operator's actual investing style (concentrated thematic, long holds) |
| 2026-04-17 | 90-day scope: working digest + Python fluency (core); 1–2 theses (stretch, gated on Wk5) | 4–6 hr/wk × 13 wks ≈ 52 hr budget; "all four" was overscoped |
| 2026-04-17 | $50/month tool budget ceiling for 6 months | Forces "earn its keep" discipline during pre-ROI build phase |
| 2026-04-17 | Paid data feeds (Bloomberg, Koyfin, Pitchbook) explicitly out of scope | Thesis is open-data signal-finding; keeps budget and scope honest |
| 2026-04-17 | No buying a stock held <30 days without a written thesis first | Retrospective thesis-writing is rationalization, not analysis |
| 2026-04-17 | Adaptive learning mode default; operator calls "fast mode" / "teach me this" to override | Matches how real learning works — depth where new, speed where familiar |
| 2026-04-18 | Week 2 scoring output: pure score + filter downstream (not in-prompt filtering) | More flexible; threshold tuning doesn't require re-running the LLM |
| 2026-04-18 | Scoring schema v0.1: 4 sub-dimensions (Maturation, Profit Mechanism, Retail-accessibility, Specificity) + final composite + 3-way flag (thesis/watchlist/skip) + translation + time-to-thesis categorical | Matches how operator actually scores; translation field critical for papers operator can't parse |
| 2026-04-18 | Renamed Commercialization → Profit Mechanism | "Who makes money and how" is the real question; catches commodity-enabler trap where cool tech creates no pricing power for any single player |
| 2026-04-18 | Hard rule in scoring prompt: retail_access < 4 caps final at 5 and blocks "thesis" flag | Encodes operator's paper #16 gut call (high sub-scores, low final) as a rule |
| 2026-04-18 | Abstracts passed to LLM as raw LaTeX; cleaned only at human-facing edges (eval set, future digest) | LLMs parse LaTeX fluently; markup carries semantic info cleaning would strip; keeps options open for re-rendering |
| 2026-04-18 | Prompt caching deferred until rubric is stable (~Week 2.5) | False economy to cache content that's churning; will cut system-prompt cost ~90% once locked |
| 2026-04-18 | Soft ceiling: scoring system prompt stays under 3,000 tokens | Prompt creep is the main budget risk; current v0.2 is ~2,284 tokens |
| 2026-04-18 | Fetcher writes dated snapshots (`snapshots/arxiv_papers_YYYY-MM-DD.csv`, canonical, never overwritten) + `arxiv_papers.csv` as latest-pointer | Preserves all captured data for future analytics; same-day re-runs timestamp-suffixed to prevent silent loss |
| 2026-04-18 | Long-term analytics (dashboards, trend velocity, cross-history queries) deferred to Parking Lot | Build trigger: CSV friction OR trend chart wanted 3+ times. Expected Month 4–6 at earliest. Persistence architecture set up now so data is available when needed. |
| 2026-04-18 | Run cadence: every other day, not daily | Cuts API cost ~50%; matches operator's 4 hr/week review budget; 2-day recency filter means no paper loss. Revisit when Week 3 velocity signal lands. |
| 2026-04-18 | Eval set: 18 papers (Climate had 0 in 2-day window, Bio only 1); accepted skewed stratification | Sample shape mirrors real daily paper flow — realistic rather than artificially balanced |
| 2026-04-18 | Eval set papers #2 and #3 flagged "over my head" by operator; excluded from calibration weighting | Kept in set as translation-layer test cases, not scoring ground truth |
| 2026-04-18 | Keep breadth across 8 domains; add LLM translation layer rather than narrowing to domains operator can parse | Translation converts "uncomfortable guesses" into "informed reads"; deep-dive only on papers that stick out |
| 2026-04-18 | Stress-test papers identified: #16 Goxpyriment (tests profit_mechanism anchor) and #17 Omega Centauri (tests cap rule as bound vs. anchor) | These two papers tell us if v0 calibration works without needing to eyeball all 18 |
| 2026-04-18 | Operator retail_access hand scores were systematically too generous (mean Δ=−2.62 vs Sonnet v0.1 and v0.2) | Sonnet's stricter interpretation is correct — sector-level exposure without a named pure play = 2-3, not 6-8. Hand scores were miscalibrated; Sonnet's baseline is ground truth going forward. |
| 2026-04-18 | Promoted scoring prompt to v0.2 | Three changes: (1) translation field prohibition on scoring-rule narration — fixed 0/18 clean vs ~6/18 in v0.1; (2) Example B profit_mechanism note clarifying the commercialization→profit rename; (3) Example C replaced with altermagnet TMR paper (correctly calibrated watchlist) — old Exceptional Points anchor had miscalibrated retail=8 |
| 2026-04-18 | v0.2 scoring rubric declared stable; prompt caching now appropriate to enable | Score distributions unchanged v0.1→v0.2 confirms rubric is settled. Enable caching before Week 3 production runs to cut system-prompt cost ~90%. |
| 2026-04-18 | Semantic Scholar chosen as Week 3 citation velocity source | Free, no auth for basic use, covers arXiv corpus well; citation velocity is the substantive maturation signal that abstract-only scoring cannot provide |
| 2026-05-04 | Fetcher emits canonical arXiv ID per paper (regex extraction from URL, version suffix stripped) | Required for scorer schema; stable across paper revisions; joins cleanly to Semantic Scholar / OpenAlex. Old row-index IDs would have broken cross-snapshot joins. |
| 2026-05-04 | RECENCY_DAYS bumped from 2 to 7 | Monday-morning runs returned 0 papers under a 2-day window because arXiv has no weekend announcements (Fri-2pm-ET to Mon-2pm-ET batches into Mon 8pm announcement). 7 days guarantees coverage on any day at ~3.5x scoring cost. |
| 2026-05-04 | Scorer output gains `published` column | Cheap to add upstream; required by digest for date sorting/display. Blank-safe via `.get()` so re-scoring the eval set still works. |
| 2026-05-04 | Week 4 digest built as single-file Streamlit app, run locally only | Path A from session: ship local first, deploy later. GitHub + Streamlit Cloud deferred to next session. Earn-its-keep gate — deploy doesn't earn its keep until digest does. |
| 2026-05-04 | Digest default filter: thesis + watchlist (skip hidden by default) | Compresses 211 papers to ~9 visible on first paint. Counts header always shows full distribution so a misfire is detectable. |
| 2026-05-04 | Cowork: candidate replacement for Week 6 automation milestone + future trade-press scraping | Defer until digest is validated. Don't automate an unproven pipeline. Revisit at end of Week 4 / start of Week 5. |
| 2026-05-04 | Production run #1: 211 papers scored, $2.83, 0 failures, 0 thesis flags / 9 watchlist | 0 thesis is consistent with prompt's stinginess — top paper (fleet-scale RL, final=6.0) correctly flagged watchlist because beneficiaries are private. Watchlist tier becomes the de-facto top tier on most days. |
| 2026-05-04 | Dark mode locked via `.streamlit/config.toml` | Forced dark theme for all viewers; operator preference, digest CSS assumes dark background |
| 2026-05-04 | Public GitHub repo at JamieMancuso/trend-engine | Simplest deploy path; nothing sensitive in source |
| 2026-05-04 | CSV deployment strategy: commit `results_*.csv` to repo | Zero extra infrastructure; auto-redeploys on git push after each scoring run |
| 2026-05-04 | Streamlit Cloud deployed, Python 3.14, free tier | Mobile-accessible at trend-engine-76lmj4cwezv3p7jhctym3s.streamlit.app |
| 2026-05-04 | Cowork project set up pointing at trend-engine folder | File maintenance agent for post-session charter updates |
| 2026-05-05 | Prompt caching enabled in week2_run_scoring.py | Rubric stable at v0.2; cache_control="ephemeral" on system prompt block; adds cache_write_tokens + cache_read_tokens columns to output CSV; summary prints uncached vs actual cost comparison |
| 2026-05-05 | Semantic Scholar citation velocity deferred indefinitely | Fresh arXiv papers have no citations yet — signal would arrive too late to be useful at fetch time. Would only work as a retroactive enrichment pass on older papers; different workflow, not worth building now |
| 2026-05-05 | Day 45 checkpoint recalibrated | Project started 2026-04-17; Day 45 = ~June 1. First digest day was 2026-05-04. No meaningful signal to evaluate yet; checkpoint remains on track |
| 2026-05-05 | Multi-run digest mode added to week4_digest.py | Sidebar toggle merges all results_*.csv, deduplicates by paper ID (latest score wins), shows "X runs merged" in counts header. Single-file mode unchanged. |
| 2026-05-05 | run_pipeline.py built — fetch → score → digest in one command | Chains three stages via subprocess; halts on non-zero exit code; supports --limit, --skip-fetch, --no-browser, --dry-run. Replaces the manual 3-step run workflow. |
| 2026-05-05 | Global dedup added to week2_run_scoring.py | Scorer now loads all previously scored IDs from every results_*.csv before each run and skips them automatically. 7-day fetch window means ~90% of papers in a given fetch were already scored; dedup drops a typical run from ~200 papers to ~20-30 genuinely new ones. |
| 2026-05-05 | Scoring rubric promoted to v0.3 — Horizon score + longshot flag added | New Horizon axis (1-10) scores the long-term transformative ceiling of the topic area independent of near-term actionability. New "longshot" flag for papers with high Horizon but low near-term actionability — 5-20yr hold signal. |
| 2026-05-05 | Scoring rubric promoted to v0.4 — per-score explanations added | New score_explanations JSON object in prompt output: one paper-specific sentence per dimension explaining why this paper got that score. Stored in llm_score_explanations column. Powers the new detail page in the digest. |
| 2026-05-05 | Digest detail page added — click any paper title to open | Shows full score breakdown: each axis with rubric definition + paper-specific explanation. Implemented via st.session_state.selected_id; back button returns to card list. Works with or without score_explanations (older rows show definition only). | New Horizon axis (1-10) scores the long-term transformative ceiling of the topic area independent of near-term actionability. New "longshot" flag (alongside thesis/watchlist/skip) for papers with high Horizon but low near-term actionability — 5-20yr hold signal. Digest shows HRZ pill in green, longshot badge in deep green. Old scored rows missing llm_horizon display gracefully (pill hidden). |
| 2026-05-07 | Multi-page Streamlit setup: digest as home, analytics in `pages/` | Native Streamlit pattern; one URL, sibling pages. No nav code needed — Streamlit auto-renders sidebar links. |
| 2026-05-07 | Analytics dashboard avoids matplotlib dep — uses `ProgressColumn` for heat cues instead of `background_gradient` | Keeps deploy footprint minimal; Streamlit Cloud already has streamlit/pandas, no extra installs. |
| 2026-05-07 | Task Scheduler env-var fix: `setx ANTHROPIC_API_KEY` at User scope | Non-interactive logon context doesn't inherit shell env; permanent user-scope var fixes the silent `Last Result: 2` failure mode. |
| 2026-05-07 | Don't manually fire scheduled task near its scheduled time | Two `scheduled_run.py` instances racing for the git index lock will produce `Last Result: 128` (fatal git error) even when scoring succeeds. Use `run_pipeline.py` for ad-hoc runs instead. |
| 2026-05-07 | News layer rubric scoped: separate 3-axis schema (signal_strength, investment_relevance, tag) — not paper rubric | Paper rubric's Maturation/Profit_Mechanism don't apply to articles; forcing them would produce noise scores. Lighter rubric also justifies cheaper model. |
| 2026-05-07 | News layer model: Haiku 4.5, not Sonnet | ~10× cheaper, fine for short summaries; mixed-model pricing across content types is acceptable complexity. |
| 2026-05-07 | News layer build trigger: 14 days × 15 min digest use + 1 named missed-decision | Without demand signal, news layer is feature creep dressed up as ambition. Hard gate prevents premature build. |
| 2026-05-11 | Digest run-scope control: 3-way radio (Single file / Latest run only / All runs merged) replaces the merge-all toggle | Operator wanted a quick "what just landed" view without losing single-file or merged modes. Radio is mutually exclusive — fewer foot-guns than two booleans. Default set to "Latest run only" (most common workflow). |
| 2026-05-11 | week2_run_scoring.py gains `--rescore-missing` flag | Bypasses global dedup so prompt-version backfills are possible (otherwise dedup blocks them). Used to backfill v0.4 Horizon + score_explanations on the May 4 / May 5 production runs. |
| 2026-05-11 | v0.4 backfill: 199 papers from May 4 / May 5 production runs queued for re-scoring under v0.4 rubric | The May 6 fetch was a fresh batch, not a backfill — only 11 papers (top11_rescore.csv) overlap with the May 4 corpus. Backfill input written to `backfill_v04_input.csv`, run executed locally by operator. April eval-set papers excluded — calibration history, not signal. |
| 2026-05-11 | News layer build trigger formally OVERRIDDEN — operator opted to ship despite gate not being met | Trigger was 14 days × 15 min digest use + 1 named missed decision. Operator chose to build now anyway. Earn-its-keep re-evaluation set for 30 days from first news run; if it isn't being read, deprecate. |
| 2026-05-11 | News layer scope this session: fetcher + scorer only (no UI integration) | Tabbed digest UI + analytics page additions deferred to next session. Ships an end-to-end pipeline (fetch → score → CSV) without leaving UI half-built. |
| 2026-05-11 | News scoring prompt v0.1 written: 3-axis schema (signal_strength, investment_relevance, tag) + flag + translation | Mirrors the scoping doc's Decision 1. Calibration anchors include OpenAI/Tim Cook/DOE/Boston Dynamics examples to illustrate flag thresholds. Will iterate after first real run shows where Haiku miscalibrates. |
| 2026-05-11 | News IDs namespaced as `hn:<item_id>` (and `<source>:<id>` for future sources) | Prevents accidental collision with arXiv IDs in any merged view. Same dedup pattern as paper scorer — global scan across `news_results_*.csv`. |
| 2026-05-11 | News scoring rubric promoted v0.1 → v0.2: added `market_impact` axis (1-10) | Operator flagged that political/macro news with market consequence was a known blind spot. Original 2-axis rubric (signal_strength + investment_relevance) under-weighted stories where the chain from policy/event → portfolio impact requires reasoning the operator might not do unprompted. New axis explicitly scores broad-market consequence regardless of personal-portfolio fit. Flag rule updated: `read = signal >=6 AND (relevance >=7 OR market_impact >=7)` — the OR catches macro stories the AND was filtering out. Translation field now required to walk the causal chain when market_impact >= 7 and exceeds investment_relevance. Output schema gains `llm_market_impact` column. |
| 2026-05-11 | News source gap acknowledged — current pipeline is HN-only | HN is tech/startup-skewed and won't surface pure macro/political news. Building macro/political RSS fetcher (Reuters Politics, AP, Axios, etc.) deferred to next session — closes the source gap that the v0.2 rubric is now ready to score against. Doing the rubric upgrade first lets us see how Haiku handles the new axis on whatever HN does carry, before adding more sources. |
| 2026-05-11 | First news run: 19 HN items, $0.057, 0 thesis-equivalent / 1 read / 4 skim / 14 skip | v0.2 rubric works mechanically — JSON parses, market_impact column populates, flag rule fires correctly. Single `read` was an AI-security story (sig=7/rel=6/mkt=7). Notably, today's HN top-30 contained zero pure macro/political stories — confirms the source gap. Rubric upgrade earned its keep on the one applicable item; broader value blocked on macro RSS fetcher. |
| 2026-05-11 | Macro/political RSS fetcher built: `week7_news_fetcher_rss.py` (Reuters Top + Politics, AP Top + Politics, Fed press + speeches) | Closes the source gap the v0.2 market_impact axis was designed for. Same OUTPUT_COLUMNS as HN fetcher so `week7_news_scoring.py` runs unchanged on its output. Uses `feedparser` (already in stack via arxiv fetcher). 48h recency window matches research cadence. IDs namespaced `reuters:` / `ap:` / `fed:` to prevent collision with `hn:`. RSS popularity columns left blank. |
| 2026-05-11 | Sources NOT included in first RSS cut: Axios | Operator picked Reuters + AP + Fed in clarification. Axios was offered but skipped — more editorial spin and noisier than wire services. Easy to add later by appending to FEEDS dict. |
| 2026-05-11 | Digest split into Research / News tabs (`st.tabs()`) | Tabs over separate pages — review flow is "what's worth looking at today across everything," not "first research, then news." Each tab owns its own sidebar widgets (15 total, all keyed with `research_` / `news_` prefixes to avoid Streamlit's DuplicateWidgetID error). Detail page (paper click → full breakdown) still works inside the Research tab. |
| 2026-05-11 | News card design: market_impact is the badge headline, not signal_strength | Operator's whole reason for adding market_impact was to surface stories he might overlook. Putting it as the big number on the card makes the eye go straight to it. SIG/REL/MKT all visible as smaller pills; MKT pill gets a blue tint matching the badge, distinguishing it from the rest. |
| 2026-05-11 | News tab default filters: read+skim flags only, all sources, all tags, min market_impact=0 | Conservative default matches research tab pattern (hide skip by default). min_market=0 means "show everything not filtered by flag" — operator can crank it up to 7+ to see only macro stories. |
| 2026-05-11 | Analytics page additions for news (signal/market_impact over time, source heat, tag distribution) deferred to next session | Per scoping: tabbed digest only this round. Analytics page additions are ~1 hour of focused work and can wait until news has accumulated 5+ runs of data worth charting. |
| 2026-05-11 | RSS source set revised after first run discovered dead URLs | Reuters RSS (`feeds.reuters.com/*`) and AP RSS (`feeds.apnews.com/*`) both returned DNS failures — Reuters retired their public RSS years ago, AP restructured. Replaced with: (1) NPR Top + Politics RSS — active wire-quality alternative; (2) Reuters via Google News RSS query (`site:reuters.com`) — indirect proxy that works. Source keys: `npr`, `reuters_via_google`, `fed`. Digest's NEWS_SOURCE_LABELS updated to render the new keys with friendly names. Lesson: should have verified RSS URLs live before shipping; news org RSS is notoriously unstable. |
| 2026-05-11 | Per-source recency window introduced (Fed: 7d, others: 48h) | Fed releases are 1-3/week; a 48h window caught 0 items on first run despite 35 entries fetched. Added `SOURCE_RECENCY_HOURS` override dict in `week7_news_fetcher_rss.py`. Pattern is generic — any future low-volume source can get its own override without touching the loop. |
| 2026-05-11 | First RSS news run: 137 items (15 NPR + 117 Reuters-via-Google + 5 Fed), $0.45, ~30 reads | v0.2 market_impact axis validated on real macro/political content. Multiple `read` flags fired specifically because of the new OR-rule (rel < 7 but mkt >= 7) — Hormuz/oil-supply, Fed chair succession, China factory inflation, Trump-Iran. Pattern operator was missing under v0.1 is now being caught. Reuters-via-Google delivers ~88% of items by volume and dominates cost; if budget tightens, drop the second query. |
| 2026-05-11 | News run cadence cost projection: ~$7/mo for news + ~$30/mo for research = ~$37/mo total | Within the $50/mo ceiling. Largest cost lever is the second Reuters-via-Google query (politics/economy) which roughly doubles RSS volume. Worth keeping for now since the macro coverage is the whole point. |
| 2026-05-11 | Observed first-run miscalibration: rate-path news scoring at signal=6 boundary gets demoted to skim | Item #92 (BofA/Goldman pushing back Fed rate-cut expectations) scored sig=6/rel=6/mkt=7 → skim, when it should arguably be read. The flag rule's `signal >= 6` floor is borderline-correct here. Watch this pattern across 2-3 runs before tweaking — single observation isn't enough to retune. If it persists, consider lowering signal threshold in the OR clause to 5 for high-market_impact items, or adding a "consensus bank macro forecast" calibration anchor. |
| 2026-05-12 | Latest-run picker: switched from alpha sort to date-in-filename sort | Two failure modes hit in sequence. (1) Alphabetical sort puts `results_top11_rescore.csv` AFTER any `results_YYYY-MM-DD_*.csv` because `t > digit`. (2) Tried mtime sort as a fix — works locally but FAILS on Streamlit Cloud because `git clone` gives every file the same mtime. Final fix: extract YYYY-MM-DD substring from filename via regex; undated files sort BEFORE dated files (treated as "older than any timestamped run"). `_sort_key()` in week4_digest.py is the source of truth; `_sort_by_mtime()` is now a misleading-name wrapper kept for back-compat. |
| 2026-05-12 | Top 11 v0.4 rescore re-run after accidental delete-and-loss | Operator deleted `results_top11_rescore.csv` mid-debugging. Today's full backfill had skipped those 11 IDs (because at backfill-build time they were considered "already v0.4-scored"). Net: 11 papers including Fleet-Scale RL temporarily reverted to v0.2 watchlist scores in the merged digest. Recovered by re-running `rescore_top11.py`; new file `results_top11_rescore.csv` (mtime May 6) holds the v0.4 scores again. Charter §10 line about "Fleet-Scale RL upgraded to thesis (7.0)" still holds, but operator should verify in digest after redeploy — scoring is non-deterministic so the second run may differ slightly from the first. |
| 2026-05-12 | week4_digest.py corruption saga (lesson, not a project decision) | During the latest-run-fix work, week4_digest.py got truncated/duplicated multiple times via the agent's Edit tool before being repaired with a manually-uploaded clean copy. Root cause traced to Edit tool reporting success without flushing to disk on this large file (~1000 lines, CRLF), compounded by bash heredoc shell-expansion bugs in the recovery attempts. Lesson recorded for future sessions: on large files, verify with bash `wc -l` + `tail -N` + `python3 -c "ast.parse"` after each edit, don't trust Edit's success message; if corruption appears, recover from `git restore` rather than incremental patching. |
| 2026-05-12 | NEW IDEA logged — "shadow portfolio" of paths-not-taken | When a ticker recurs across the system's output (research `llm_public_vehicles` + news translations), capture its price at threshold-crossing date. Lets operator look back later and ask "did we surface this before it ran?" — feedback loop on whether the system finds signal AND whether operator's judgment on system output is calibrated. Operator-confirmed defaults: trigger = 3+ mentions in 7-day rolling window across both content types; price source = yfinance (free, no auth, fragile but acceptable); snapshot at trigger plus on-demand refresh button on analytics page (no scheduled API calls). Build deferred to Week 8. Two design subtleties to resolve at build time: (1) ticker extraction from prose news translations needs allowlist of ~200 plausible tickers to avoid false positives like "USA"/"AI"/"CEO"; (2) yfinance API calls must be wrapped so breakage logs a warning rather than halting the trigger logic — record blank price, allow manual backfill. |
| 2026-05-15 | NEW SCOPE — personal portfolio view added to Week 8 as lightweight fold-in | Operator wants to view Webull + ETrade holdings together in one place with historical price context. Broker APIs (Webull has none, ETrade requires OAuth + dev agreement) explicitly out of scope — too much work, off-mission. Solution: manual `holdings.csv` (ticker, broker, shares, cost_basis_per_share, purchase_date, notes), edited by operator on trades. New "Portfolio" tab in `week4_digest.py` alongside Research/News. Top section: holdings table with current price via yfinance, gain/loss $/%, % of total, broker filter. Below: per-ticker historical chart with 1M/6M/1Y/5Y toggle, also yfinance. Click ticker in table → chart loads. Session-cached prices + Refresh button (no scheduled yfinance calls). Reuses the yfinance wrapper being built for shadow portfolio — both should land in the same session to share infra. Explicitly NOT in scope this build: real-time tick data, options/crypto, dividend tracking, tax lots, broker auto-sync, thesis-linking (deferred). Earn-its-keep gate: if operator isn't opening the Portfolio tab 3x/week after 30 days, consider deprecating. Strict adherence to §4 "real-time market data out of scope" — yfinance is delayed/historical, not real-time tick. |
| 2026-05-15 | Scope guardrail noted — portfolio view is operator-utility, not Trend Engine mission | The portfolio tab does not advance the §1 mission (surfacing emerging paradigm shifts). It's a quality-of-life addition that earns its place because (a) infra overlap with shadow portfolio is high, (b) operator predicts higher daily engagement with the digest if portfolio lives there, which feeds the §3 "daily digest the operator actually opens" success criterion. If build creep happens (thesis tracking, sector breakdowns, options analytics), pull back to the original spec — those are separate features needing their own earn-its-keep cases. |

## 10. Current Status & Next Actions

**Phase:** Start of Week 8 (2026-05-15) — coming off the Week 7 wrap (full news layer shipped end-to-end including macro/political sources, tabbed digest UI live on Streamlit Cloud, latest-run picker hardened against undated CSV filenames after a Streamlit Cloud mtime gotcha). v0.4 backfill complete on 199 pre-v0.4 production papers; top 11 v0.4 rescore re-run after accidental delete. News-layer earn-its-keep checkpoint set for ~June 10. Day 45 thesis go/no-go ~June 1. New scope this week: Portfolio tab (lightweight, manual holdings.csv + yfinance) added as fold-in to share infra with shadow portfolio.

**Working files:**
- `week1_arxiv_fetcher.py` — emits arXiv ID per paper, RECENCY_DAYS=7
- `week2_scoring_prompt_v02.py` — stable, v0.4 (Horizon + per-score explanations)
- `week2_run_scoring.py` — prompt caching enabled, global dedup, `--rescore-missing` for backfills
- `week2_compare_scores.py` — comparison/divergence analyzer
- `week4_digest.py` — home page; Research/News tabs (`st.tabs()`). Research tab: cards, 3-way run-scope, detail page. News tab: cards with market_impact-as-headline badge, source/tag/flag filters, market_impact slider.
- `pages/2_Analytics.py` — cross-corpus dashboard
- `run_pipeline.py` — one command fetch → score → digest
- `scheduled_run.py` — headless variant for Task Scheduler
- `.streamlit/config.toml` — forces dark theme
- `eval_set_v1.xlsx` / `eval_set_v1__Scoring.csv` — hand-scored eval set
- `clean_latex.py` — utility for human-facing abstract rendering
- `week6_news_layer_scoping.md` — architectural plan for the news layer
- `week7_news_fetcher.py` — HN top-stories fetcher → news_hn_*.csv
- `week7_news_fetcher_rss.py` — NEW: macro/political RSS fetcher (Reuters + AP + Fed) → news_rss_*.csv
- `week7_news_scoring_prompt_v01.py` — 3-axis news rubric, currently at v0.2 (signal/relevance/market_impact + tag + flag + translation). Filename kept stable across versions; PROMPT_VERSION constant inside is the source of truth.
- `week7_news_scoring.py` — Haiku-based news scorer with caching, dedup, `--rescore-missing`. v0.2 schema includes market_impact column.
- `backfill_v04_input.csv` — 199 papers queued for v0.4 backfill rescore

**Deployment:** Public GitHub repo `JamieMancuso/trend-engine`. Streamlit Cloud free tier, Python 3.14, live at `trend-engine-76lmj4cwezv3p7jhctym3s.streamlit.app`. CSVs commit to repo so each scoring run auto-redeploys via git push.

**Last run (scorer):** 211 papers, v0.2 prompt, $2.83 total, 0 failures, 0 thesis / 9 watchlist / 202 skip flags. Date range 2026-04-28 to 2026-05-01 (4 distinct dates — arXiv weekend gap shows up clearly in the spread).

**Week 4 / 4.5 outcomes:**
- Digest renders cards with sub-scores, translation, vehicles, rationale expander, arxiv link
- Filters work: domain, flag, min final score, "named vehicle only" toggle, sort by score/date/domain
- Default view ("thesis + watchlist") collapses 211 papers → 9 actionable cards
- Confirmed watchlist papers are legit signals: fleet-scale RL (SYM/TER), GaN-on-silicon (NVTS/WOLF), ECMWF ocean modeling, autonomous depot vehicles (XPO/ODFL/UPS/AMZN)
- Light-mode rendering issue resolved by forcing dark theme via `.streamlit/config.toml`
- Digest mobile-accessible via Streamlit Cloud
- Cowork file-maintenance agent now points at the project folder; handles post-session charter updates so closeout docs flow into §9 / §10 automatically
- Pipeline ergonomics: refetch + score takes ~15 min wall time and ~$3 at current settings; well within budget

### Week 5 outcomes (2026-05-05 session)

All Week 5 items shipped:
- ✅ Prompt caching (~90% cost reduction on system prompt)
- ✅ Multi-run digest mode (merge all CSVs, deduplicate by ID)
- ✅ `run_pipeline.py` — one command for full fetch → score → digest
- ✅ Global dedup in scorer — skips previously scored papers automatically
- ✅ Windows Task Scheduler automation — runs every 2 days at 9pm
- ✅ Scoring rubric v0.3 — Horizon score (1-10) + longshot flag
- ✅ Scoring rubric v0.4 — per-score explanations in JSON output
- ✅ Digest detail page — click any title for full score breakdown with definitions + paper-specific explanations
- ✅ Top 11 papers rescored with v0.4 — Fleet-Scale RL upgraded to thesis (7.0)

### Week 6 outcomes (2026-05-06 → 2026-05-07 session)

- ✅ Task Scheduler verified working — fixed silent `Last Result: 2` failure (env-var inheritance)
- ✅ Analytics dashboard built (`pages/2_Analytics.py`) — KPI strip, domain heat, flag-over-time, top by Horizon, watchlist aging
- ✅ Multi-page Streamlit setup — digest as home, analytics in `pages/`, both at same URL
- ✅ Verified against real data: 256 unique papers, 295 scoring events, $3.81 cumulative cost, ~84% cache savings
- ✅ News layer scoping doc — architectural decisions locked, hard build trigger defined
- ✅ Identified Task Scheduler race condition: don't manually fire scheduled task within ~10 min of its scheduled time (git index lock collision produces `Last Result: 128`)

### Next concrete actions (Week 8)

1. **Verify the deploy is healthy** after wrap-up push. Hard-refresh the live URL, click the News tab, set min market_impact=7 — should show a few macro reads (Hormuz/oil, Fed, China inflation). Confirm Latest run on Research tab shows `results_2026-05-11_201030.csv`, not the top11 file.
2. **Use the system.** Daily/every-other-day digest review is the milestone. News-layer earn-its-keep clock starts now (~June 10).
3. **Watch for v0.2 news rubric miscalibrations** across 2-3 more runs before tweaking. Known suspect pattern: rate-path forecasts at signal=6 boundary getting demoted to skim. Don't retune on single observation.
4. **Day 45 checkpoint** (~June 1) — go/no-go on thesis stretch. Verify Fleet-Scale RL is showing v0.4 scores in the merged digest after the rescore recovery.
5. **News-layer analytics additions** (only if news proves useful by ~Week 9): signal/market_impact over time, source heat, tag distribution on `pages/2_Analytics.py`. ~1 hour.
6. **Cleanup backlog:** delete `scheduled_run_restored.py` duplicate; consider deleting `rescore_top11.py` after one more Streamlit-Cloud-clean run confirms top11 stable; consider renaming `results_top11_rescore.csv` to follow the date convention so the sort fix isn't load-bearing.
7. **Fold news pipeline into `scheduled_run.py`** so news fetch + score + commit happens automatically on the every-2-days cadence. Currently news is the ONLY manual step in the workflow. ~30 min build (add news stages between current research stages and git push).
8. **Shadow portfolio build (Week 8)** — see 2026-05-12 decisions log entry. New `shadow_portfolio.py`, schema for `shadow_portfolio.csv`, new section on analytics page with sortable table and "Refresh prices" button. Start with hand-curated ticker allowlist for news extraction; yfinance for prices wrapped in try/except. **Land this in the same session as the Portfolio tab below — both need the yfinance wrapper, build it once.**
9. **Portfolio tab build (Week 8, NEW)** — see 2026-05-15 decisions log entry. Lightweight unified view of Webull + ETrade holdings driven by manual `holdings.csv`. Add as third tab in `week4_digest.py` (Research / News / Portfolio). Spec:
   - Schema: `holdings.csv` columns = `ticker, broker, shares, cost_basis_per_share, purchase_date, notes`
   - Top: holdings table — ticker, broker, shares, avg cost, current price, market value, gain/loss $, gain/loss %, % of total. Broker filter (All / Webull / ETrade). Sort by value default.
   - Bottom: per-ticker historical chart, 1M / 6M / 1Y / 5Y toggle. Selected via click on row (st.session_state.selected_ticker) or dropdown fallback.
   - yfinance for both current price and history. Wrap every call in try/except — broken ticker shows "—", doesn't crash the page. Use shared wrapper with shadow portfolio.
   - Session cache on prices (`@st.cache_data(ttl=3600)`). Refresh button at top of tab clears cache.
   - Strictly NOT in this build: real-time tick, options, crypto, dividends, tax lots, broker auto-sync, thesis linking.
   - Estimated effort: 2–3 hours combined with shadow portfolio yfinance wrapper.
10. **Use the system.** Daily/every-other-day digest review is still the milestone. Reps > new features.
11. **Day 45 checkpoint** (≈ June 1) — go/no-go on thesis stretch goal. Fleet-Scale RL (SYM/TER) at Final 7.0 / Horizon 8 leading candidate.
12. **News layer earn-its-keep checkpoint:** 30 days from first news run — if news isn't being read, deprecate. Override of original build trigger needs to actually pay off.
13. **Portfolio tab earn-its-keep checkpoint:** 30 days from build — operator should be opening the tab ≥3x/week, otherwise deprecate or simplify.
14. **Watchlist revisit affordance** — defer until analytics aging chart demands it.
15. **Cleanup:** delete `scheduled_run_restored.py` (identical duplicate).

## 11. Open Questions / Parking Lot

*Things worth revisiting but not blocking current work.*

### Vision note — "FT in aggregate" (logged 2026-05-05)

Operator wants Trend Engine to grow into a single personal intelligence dashboard covering both research signals (current arXiv pipeline) and broader current events / world news. The goal is to recreate the Financial Times in aggregate — high-signal, curated, investment and career relevant — using open sources rather than a subscription.

**What this means architecturally:**
- Two distinct content types: (1) research papers — structured, scoreable with current rubric; (2) news/commentary — unstructured, needs lighter-touch summarization + tagging rather than full investment scoring.
- Not everything needs the full 5-axis score. News items need: source, headline, 2-sentence summary, relevance tag (investing / macro / tech / career), and maybe a simple 1-5 signal strength rating.
- UI implication: probably two tabs in the digest — "Research" (current) and "News" (new). Same aesthetic, different card format.

**Candidate sources for news layer (in priority order):**
1. Hacker News API — free, no auth, high signal-to-noise for tech
2. Company/lab research blogs — DeepMind, OpenAI, Anthropic, Meta FAIR, Microsoft Research
3. VC blogs — a16z, Sequoia, USV (RSS available)
4. Reddit via PRAW — r/MachineLearning, r/investing, r/localllama
5. arXiv-adjacent: bioRxiv, medRxiv (when health/bio coverage matters)
6. FT/WSJ RSS — partial coverage without subscription; worth testing

**Open questions before building:**
- Does news get investment-scored or just summarized? (Scoring adds cost + complexity)
- How do we handle paywalls on FT/WSJ/Nature?
- What's the refresh cadence for news vs. research (hourly? daily?)?
- Does the analytics dashboard cover news items too, or research only?

**Build trigger:** after analytics dashboard ships and digest has been in daily use for 4+ weeks. Don't build the news layer until the research layer is genuinely habit-forming.

- Should we eventually track GitHub trending repos as a signal? (Paper → code velocity is a leading indicator.)
- Do we need a "watchlist" of specific researchers/labs whose output always gets flagged?
- How do we handle paywalled sources (Nature, Science) when they matter?
- Can we use arxiv-sanity-lite as an existing reference instead of reinventing?
- When (if ever) does this justify moving off a local machine?
- **Restart FT subscription?** $40–75/mo — fits within the $50 ceiling if we trade off API spend. Best upstream source among legacy finance media. Decide once API costs are actually measured with caching enabled.
- How do we detect the "under-appreciated → consensus" transition? (Key risk for 2-year horizon investing.)
- **Analytics layer / dashboards / trend velocity.** Want to query across all captured history (flag patterns over time, topic velocity, watchlist revisit). Build trigger: CSV friction, not calendar date. Likely path: SQLite → simple Streamlit or notebook dashboard. Do NOT build before digest is operational and in daily use.
- **Prompt version re-scoring policy.** When the prompt changes, do we re-score the backlog or keep scores version-stamped and filter-by-version? Current default: append-only with version tags, selective re-score on big prompt changes. Decide formally once we have >30 days of scored data.
- **Watchlist revisit mechanism.** Once Week 5 digest exists, need a way to resurface aging watchlist items periodically (monthly? when new related papers arrive?). Cheap to build once digest is live.
- **Prompt caching:** now appropriate to enable (rubric stable as of v0.2). Will cut system-prompt cost ~90%. Implement before next production scoring run.
- **Mining/extraction tech coverage gap.** arXiv has partial coverage (cond-mat.mtrl-sci, physics.app-ph capture battery/catalyst science; physics.geo-ph and physics.flu-dyn would add seismic/reservoir but aren't in current set). Real commercial signals (autonomous mining trucks, shale productivity) live in trade press, not arXiv. AI/Robotics domains already capture the upstream ML/robotics. Defer until news/trade-press layer (Week 5+).
- **Light-mode CSS for digest.** Card backgrounds assume dark theme. Easy fix once base UX is locked.
- **Cowork for scheduled fetch/score automation.** Strong fit, no extra cost (Pro plan covers it). Earliest sensible time: end of Week 4 / start of Week 5, after digest is validated. Could replace the Week 6 GitHub Actions automation milestone entirely.
- **Cowork for trade-press scraping.** Strong fit when news/trade-press layer goes in. Solves the extraction-industry coverage gap.
- **Day 45 stretch goal: 1-2 written theses.** Core 90-day goal hit. Stretch decision deferred to Week 5 — depends on whether watchlist + citation velocity together produce a credible thesis-quality signal on real papers.
