# News Layer Scoping

*Scoped 2026-05-07. Decisions to be revisited at build-trigger.*

## Purpose

Extend Trend Engine from research-only to research + news, working toward the
"FT in aggregate" vision in charter §11. **This is a scoping doc, not a build
spec** — code starts only when the build trigger below is met.

## Build trigger

Do NOT build until BOTH conditions hold:

1. Digest has been used for **14+ consecutive days at 15+ min/day** (proves
   the research layer is habit-forming).
2. Operator can name **at least one investment decision** where the missing
   signal was news/commentary, not research (proves the demand is real, not
   imagined).

Without (2), the news layer is feature creep dressed up as ambition.

## Architectural decisions

### Decision 1: Scoring schema — separate, lighter rubric

Research papers and news need different rubrics. The 5-axis paper rubric
makes no sense for a TechCrunch article — "is this the 3rd paper on X?" doesn't
apply. But pure summarization with no structure means no filter or rank,
which makes a daily firehose useless.

**News rubric (3 axes + tag):**

| Axis | Range | Meaning |
| :---- | :---- | :---- |
| `signal_strength` | 1-10 | Is this real news or noise? PR puff = 1, primary-source breakthrough = 10 |
| `investment_relevance` | 1-10 | Does this matter for current picks or thesis-formation? |
| `tag` | categorical | `ai` / `energy` / `robotics` / `bio` / `macro` / `career` / `other` |
| `flag` | categorical | `read` / `skim` / `skip` |
| `translation` | text | 2-sentence "why this matters for a 2-year retail horizon" |

No "thesis" tier — news rarely warrants act-today. The two-axis score is
intentionally simpler than papers; cost ~10x lower per item.

### Decision 2: Source priority

Build in this order, validate each before moving to the next:

1. **Hacker News API** — free, no auth, high density of tech-investor signal.
   Top 30 stories filtered per fetch.
2. **Company research blogs** (RSS) — DeepMind, OpenAI, Anthropic, Meta FAIR,
   Microsoft Research. Low volume, very high signal per item.
3. **VC blogs** (RSS) — a16z, Sequoia, USV, Stratechery-light substacks.
4. **Reddit via PRAW** — r/MachineLearning, r/localllama, r/investing.
   Skim-tier source; high noise.
5. **bioRxiv / medRxiv** — defer until health/bio matters.
6. **FT/WSJ RSS** — defer pending the FT-subscription decision in §11.

### Decision 3: Refresh cadence

News refreshes at the **same cadence as research** (every 2 days at 9:55 PM,
existing scheduled task), with a fetch window of **last 48 hours**.

Why not hourly: news that matters is still a story 24h later; hourly is
budget waste; same cadence reuses existing infra.

### Decision 4: UI integration

The home page (`week4_digest.py`) gets split into two tabs:

- **Research tab** — current card view, unchanged.
- **News tab** — new card format suited to short summaries + tag chips.

Why tabs not separate pages: review flow is "what's worth looking at today
across everything", not "first research, then news." Tabs keep the cognitive
load on one page.

The analytics page (`pages/2_Analytics.py`) adds a News section: signal
strength over time, source heat, tag distribution.

### Decision 5: Model choice

Use **Haiku 4.5** for news scoring, not Sonnet. Reasons:
- Article scoring is shorter and simpler than paper scoring.
- ~10× cheaper input/output rates.
- Latency matters less than for the digest's interactive filters.

Cost estimate: ~$0.001/article × 30 articles every 2 days = **~$0.75/mo**
for HN alone. Adding company blogs maybe doubles it. Well under budget
even with sources 1-4 active.

## What this is NOT

- A general-purpose news aggregator. Bar = "would I pay attention to this
  for my 2-year thesis?" If no, skip.
- A replacement for FT/Stratechery. Complement, not substitute.
- A real-time alert system. Cadence ceiling = daily.

## Open questions to revisit at build time

- Does deduplication across sources matter? (HN often surfaces the same
  story as VC blogs.) Probably yes — dedupe by URL canonical form.
- Does the analytics dashboard cover news items too? Yes, but as separate
  charts — flag/score distributions are different.
- How do we handle paywalls on FT/WSJ? Either skip-and-log, or score from
  the headline/preview only and tag `paywalled`.
- Watchlist for *companies* mentioned in news (vs research)? Defer until
  there's enough news signal to know whether this matters.

## Estimated effort

If trigger is met and scope holds:

- HN fetcher + Haiku scorer + CSV writer: **~3 hours**
- Tabbed digest UI: **~2 hours**
- Analytics page additions: **~1 hour**
- Total Week N: **~6 hours**, fits one session.

Sources 2-4 add roughly 1-2 hours each. Total to feature-complete:
~10-12 hours over 2-3 sessions.
