# Week 3 Planning Session Summary
_To be added to Project Knowledge. Open tonight's chat inside the project and continue from here._

---

## Status going in

- **Week 1** (arXiv fetcher): done and stable → `week1_arxiv_fetcher.py`
- **Week 2** (LLM scoring): done and stable → `week2_scoring_prompt_v02.py`, `week2_run_scoring.py`, `week2_compare_scores.py`, `clean_latex.py`
- Eval set: 18 papers, validated. v0.2 prompt stable. Scoring pipeline production-ready.

---

## Week 3 goal

Add Semantic Scholar citation velocity as a signal layer alongside LLM scores.
The framing: citations answer "is the field paying attention?" — a question abstract-only scoring can't answer. This is the "3rd convergent paper on a topic" signal.

---

## Decisions made this session

### Citation signal architecture: Option C (hybrid gate)
Three options were considered:

- **A** — Feed citations into LLM prompt as a new scoring dimension. Rejected: destabilises validated v0.2 prompt, couples two failure modes, loses clean abstract-only signal.
- **B** — Separate column, post-hoc filter. Safe and reversible, but you own the combination rule explicitly.
- **C (chosen)** — Citations as a gate/flag, LLM as the scorer. Two signals answering different questions, each interpretable. Papers where LLM score and citation signal disagree are flagged for human review. Matches the "convergent paper" framing.

Gate rule specifics are **not yet decided** — depends on the distribution you see when you run validation on the eval set.

### Prompt caching: approved, not yet implemented
Rubric is stable enough. Saves ~90% on system-prompt input token cost. Implementation is a small diff to `week2_run_scoring.py` — see below.

---

## Files produced this session

### `week3_semantic_scholar.py` (ready to copy into project)
- Takes the scored CSV, hits the Semantic Scholar public API (no key), returns three new columns joined to existing output:
  - `s2_citations_total` — lifetime citation count
  - `s2_citations_12mo` — citations in last 12 months (the velocity signal)
  - `s2_influential_citations` — S2's influential flag count
- Disk cache in `.s2_cache/` keyed by arXiv ID. Delete to force refresh.
- Rate-limits to 1 req/sec, handles 429 with exponential backoff.
- Failures write `None` to S2 columns + reason in `s2_error`. They don't abort the run.
- arXiv ID parsed from full URL format (`arxiv.org/abs/2403.12345`). Strips version suffix. Handles old-style cross-listed IDs.
- Input column name expected: `arxiv_url`. Adjust `ARXIV_COL` constant at top of file if different.
- Eval path: adjust `EVAL_PATH` constant to your actual eval CSV filename.

Usage:
```bash
python week3_semantic_scholar.py --eval                          # validates on 18-paper eval set
python week3_semantic_scholar.py --input scored.csv --output scored_enriched.csv
```

### Prompt caching diff for `week2_run_scoring.py` (not yet written to file — apply manually)

**Change 1** — `call_claude()`: switch `system=` from a string to a content block list:
```python
system=[
    {
        "type": "text",
        "text": SYSTEM_PROMPT,
        "cache_control": {"type": "ephemeral"},
    }
],
```

**Change 2** — update `estimate_cost()` signature and body:
```python
def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    cache_creation_tokens: int,
    cache_read_tokens: int,
    model: str,
) -> float:
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        return 0.0
    base_in = pricing["input"]
    return (
        input_tokens * base_in
        + cache_creation_tokens * base_in * 1.25
        + cache_read_tokens * base_in * 0.10
        + output_tokens * pricing["output"]
    ) / 1_000_000
```

**Change 3** — return cache token counts from `call_claude()`:
```python
usage = response.usage
return (
    parsed,
    usage.input_tokens,
    usage.output_tokens,
    getattr(usage, "cache_creation_input_tokens", 0) or 0,
    getattr(usage, "cache_read_input_tokens", 0) or 0,
)
```

**Change 4** — add two columns to `OUTPUT_COLUMNS`: `cache_creation_tokens`, `cache_read_tokens`. Thread the new values through `score_paper()` into the row dict and into `estimate_cost()`.

**Watch-out:** Add a comment near the `SYSTEM_PROMPT` import: *"Must be byte-identical across all calls in a run for prompt caching to work — do not interpolate per-call values into the system block."* It currently is byte-stable (constant imported from module, no interpolation). Keep it that way.

**Watch-out:** Minimum cacheable size is 1024 tokens for Sonnet. Your rubric needs to clear that bar or `cache_control` is silently ignored. First run will confirm — `cache_creation_input_tokens` will be 0 on call #1 if under the minimum.

---

## Exact next steps for tonight (in order)

1. **Copy `week3_semantic_scholar.py`** into your `trend-engine/` project directory.
2. **Adjust two constants** at the top of the file:
   - `ARXIV_COL` — confirm it matches the actual column name in your scored CSV
   - `EVAL_PATH` — point it at your actual 18-paper eval CSV
3. **Run validation on the eval set:**
   ```bash
   python week3_semantic_scholar.py --eval
   ```
4. **Inspect the enriched output. Check:**
   - Do citation counts look right? Spot-check 2-3 papers you know against S2 web UI or Google Scholar.
   - How many of the 18 get `s2_error`? If ≥3, plan for "missing S2 data → let through, flag it" in the gate logic.
   - Are `s2_citations_12mo` counts non-zero and plausible? If everything is zero, date parsing may be off — flag for debugging.
5. **Look at the distribution** of `s2_citations_12mo` across the 18 papers. This tells you where to set the gate threshold. Don't pick a number before you see the data.
6. **Apply the prompt caching diff** to `week2_run_scoring.py` (see above). Run a 3-paper smoke test:
   ```bash
   python week2_run_scoring.py --limit 3
   ```
   Confirm `cache_creation_tokens > 0` on call #1 and `cache_read_tokens > 0` on calls #2 and #3.
7. **Decide the gate rule** based on what you saw in step 5. Options to consider once you have the distribution: hard threshold on `s2_citations_12mo`, disagreement flag (high LLM score + zero citations = flag for review), or separate leaderboards.
8. Wire gate logic into production once you're happy with validation.

---

## Open questions to resolve tonight

- What is the actual column name for arXiv URLs in your scored CSV? (Expected: `arxiv_url` — confirm before running)
- Does your `SYSTEM_PROMPT` clear 1024 tokens? (Will be confirmed empirically on first cached run)
- What gate threshold makes sense given the eval set citation distribution? (Don't decide until you see the data)
