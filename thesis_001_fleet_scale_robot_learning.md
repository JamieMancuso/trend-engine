# Thesis #1 — Fleet-Scale Robot Learning

**Status:** DRAFT (operator review pending)
**Declared:** 2026-06-11 (Day 45 go/no-go — see charter §9)
**Horizon:** 2 years (checkpoints below)
**Prompt-version provenance:** Learning while Deploying scored under v0.4; DockAnywhere under v0.2 (pre-Horizon)

---

## Claim

Robots that improve from deployment data — rather than being frozen after lab training — are crossing from research milestone to commercial moat within the 2-year window. Companies operating large robot fleets will compound an advantage smaller operators can't match: every deployed unit becomes a data-collection asset that makes the whole fleet better. The market currently prices these companies as hardware/logistics vendors, not as compounding-data businesses.

## Mechanism

The moat is the flywheel: more deployed robots → more edge-case data (including human corrections) → better shared policy → higher task success → more customer deployments → more robots. This is the same dynamic that made Tesla's FSD data advantage and Google's search feedback loop durable. The key 2026 development is that it now works on physical fleets at meaningful scale, not just in simulation.

## Supporting evidence

**Primary — Learning while Deploying: Fleet-Scale RL for Generalist Robot Policies** ([2605.00416](https://arxiv.org/abs/2605.00416), Final 7.0 / Horizon 8 / time-to-thesis <2yr). 16 real robots continuously improving a shared policy through deployment experience and human corrections; 95% average success on multi-step tasks (grocery restocking, 3–5 min manipulation sequences). Fleet-validated, quantitative, on real hardware — a commercialization-phase result.

**Primary — DockAnywhere** ([2604.15023](https://arxiv.org/abs/2604.15023), Final 6.5, time-to-thesis 2–5yr). Attacks the data-cost side of the same flywheel: one demonstration auto-expanded into many positional variants, making mobile manipulators robust to docking variance. Lowers the cost-per-skill of deploying fleets — the supply-side enabler of the primary paper's demand-side loop.

**Confirmation — Robotic Strawberry Harvesting** ([2605.23863](https://arxiv.org/abs/2605.23863), Final 6.5 / Horizon 6). 84.3% end-to-end harvest success in real greenhouses using the same enabling stack (sim-to-real RL + robust vision + manipulation in unstructured environments). Not an investable vehicle (all pure-plays private — see charter §9 2026-06-11), but independent evidence the stack commercializes in labor-cost-driven markets.

**External corroboration:** MIT LIDS + Symbotic published deep-RL fleet congestion control in JAIR (March 2026) — 25% throughput improvement on real e-commerce warehouse layouts. A public company is already doing fleet-scale RL in production-relevant settings.

## Candidate vehicles

| Ticker | Exposure | Verification status |
|---|---|---|
| SYM (Symbotic) | Purest fleet-learning angle: operates warehouse robot fleets; MIT/JAIR deep-RL fleet coordination work | **Verified via Q2 FY2026 10-Q (2026-06-11)** — see findings below |
| TER (Teradyne) | Owns Universal Robots + MiR — cobot/AMR fleets are the deployment surface for fleet learning; also flagged by DockAnywhere scoring | **Verified 2026-06-11** — fleet-learning product story is real: Q1 2026 robotics revenue $91M (+32% YoY), AI applications = 15% of robotics sales, NVIDIA partnership (UR AI Trainer feeds NVIDIA GR00T VLA + Isaac Sim), "physical AI" work cells with Generalist shown at GTC/Automate 2026. **Thesis-purity caveat:** robotics is a small slice of total Teradyne revenue — the stock trades primarily on semiconductor test (AI chip demand), so TER is a diluted vehicle for this thesis even though the robotics story checks out. Operator holds 1 share @ $363.95 (Webull, in holdings.csv) |
| ABB | Global industrial robot installed base; scale to benefit if fleet learning becomes table stakes | **Verified 2026-06-11 — with a material development:** ABB is spinning off its robotics division as a separately listed pure-play ("ABB Robotics"), targeted Q2 2026 (i.e., NOW), listing Switzerland/Sweden, distributed as dividend-in-kind to ABB holders. Division: $2.3B 2024 revenue, 12.1% EBITA margin, ~80% of offerings include software/AI components. The spin-off converts the weakest vehicle (diluted conglomerate) into potentially the cleanest pure-play on the list. **Open items: confirm actual listing date/ticker; check US retail access (foreign listing — may need OTC/ADR).** Holding ABB parent before the record date captures the spin-off shares |

### SYM 10-Q findings (Q2 FY2026, quarter ended 2026-03-28)

**Supports the thesis:**
- Revenue $676.5M for the quarter, +23% YoY ($1.31B six-month, +26%). First profitable quarter in the comparison: net income $9.4M vs −$9.9M prior year.
- Backlog **$22.7B** — enormous multi-year deployment runway, i.e., the robot fleet (the data-collection surface) keeps growing on contract.
- Software maintenance & support revenue nearly doubled YoY ($6.7M → $12.9M quarterly) — the recurring layer is growing fastest, off a tiny base.
- Supports the "market prices them as hardware vendor" framing: software is only ~2% of revenue and gross margin is ~22% (hardware economics) — if fleet learning becomes a margin story, it isn't priced in yet.

**Cuts against / risks (added to falsification watch):**
- **Customer A (Walmart) = 84.5% of quarterly revenue**, and the $22.7B backlog is "vast majority" Walmart + Exol (the JV with SoftBank's Sunlight, 35% Symbotic-owned). This is single-customer dependency, not a diversified fleet-learning business. Walmart also acquired Symbotic's Advanced Systems Robotics unit (Jan 2025) — the customer is partly internalizing the capability.
- The 10-Q's own language contains **zero** mentions of machine learning, fleet learning, or autonomy; "artificial intelligence" appears once (Exol description). The fleet-learning moat is the thesis's interpretation (backed by the MIT/JAIR collaboration), not management's stated strategy. If it never shows up in their strategic language or margin structure, falsification condition #2 is live.
- R&D actually declined YoY ($58.0M → $51.3M quarterly).

## What would falsify this thesis

1. Fleet-learning results fail to replicate beyond curated demos — e.g., follow-up papers show the 95% success collapses outside controlled task sets.
2. The data flywheel doesn't translate to economics: fleet operators (SYM earnings) show no margin or win-rate improvement attributable to learning systems within 18 months.
3. Foundation-model robotics (generalist policies trained on internet-scale data) commoditizes the advantage — if a frozen pretrained policy matches continuously-learning fleets, the deployment-data moat evaporates.
4. The niche consolidates into private hands (as strawberry harvesting did) with no public-market value capture.

## Checkpoints

- **2026-12-11 (6 mo):** Has fleet learning appeared in any SYM/TER/ABB earnings call, product announcement, or filing? Are follow-up papers confirming or contradicting LWD's results? Pipeline check: count new thesis/watchlist papers in this niche.
- **2027-06-11 (12 mo):** Mid-thesis review. If zero commercial signal by now, downgrade to watchlist and write the post-mortem.
- **2028-06-11 (24 mo):** Final scoring against §3 success criteria. Did the system surface this before the market priced it?

## Position notes

No position sizing or trade recommendation here — that's the operator's call with their own risk tolerance. Current exposure: operator holds 1 TER share @ $363.95 (Webull) — a pre-existing position that now doubles as a thesis tracker. The shadow portfolio also tracks SYM and TER (both triggered in the 2026-05-15 dry-run), so the "did we see it before it ran" feedback loop is live regardless of whether positions change. If SYM exposure is ever considered, the 84.5% Walmart concentration is the first risk to size against.
