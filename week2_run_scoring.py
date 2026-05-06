"""
Week 2 API Runner — score papers with the Anthropic API
--------------------------------------------------------
Wires week2_scoring_prompt.py (SYSTEM_PROMPT + build_user_message) to the
Anthropic Messages API and writes scored results to CSV.

WHAT IT DOES:
  - Reads papers from an input CSV (default: eval_set_v1__Scoring.csv).
  - For each paper, calls Claude Sonnet 4.6 with SYSTEM_PROMPT + user message.
  - Parses the JSON output, stamps PROMPT_VERSION + run_timestamp.
  - Writes results to results_YYYY-MM-DD_HHMMSS.csv.
  - Tracks token usage + dollar cost and prints a summary.
  - Resume-safe: if output CSV exists, skips rows already scored.

SETUP (one-time):
    py -3.14 -m pip install anthropic --user
    setx ANTHROPIC_API_KEY "sk-ant-..."          # then restart terminal

RUN:
    py -3.14 week2_run_scoring.py                                  # full eval set
    py -3.14 week2_run_scoring.py --limit 3                        # first 3 only (smoke test)
    py -3.14 week2_run_scoring.py --input arxiv_papers.csv         # score a fetcher output
    py -3.14 week2_run_scoring.py --model claude-haiku-4-5         # try a cheaper model

COST CONTROL (charter: $50/mo ceiling):
  18-paper eval run ~ $0.20-0.30 with Sonnet 4.6 (verified below).
  Full daily-ish run (~150 papers) ~ $1.50-2.00.
  At every-other-day cadence -> ~$25-30/mo before prompt caching.
  Prompt caching enabled as of v0.2 (rubric stable). Expected ~90% reduction
  on system-prompt tokens after the first call in each run.

PROMPT CACHING NOTES:
  The system prompt is passed as a list with cache_control="ephemeral".
  First call in a run: pays cache_write cost (1.25x normal input rate).
  Subsequent calls: pays cache_read cost (~0.1x normal input rate).
  The summary prints a cache breakdown so you can verify savings.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from anthropic import Anthropic, APIError

# Import the prompt from the sibling module. If this file lives next to
# week2_scoring_prompt.py, this import just works.
from week2_scoring_prompt_v02 import SYSTEM_PROMPT, build_user_message, PROMPT_VERSION


# ---- MODEL + COST CONFIG ----------------------------------------------------
# Pricing is per 1M tokens. Update if Anthropic changes prices.
# Source: https://docs.claude.com/en/docs/about-claude/pricing (verify before budgeting)
# cache_write: 1.25x normal input rate (you pay to populate the cache)
# cache_read:  0.10x normal input rate (the ~90% saving vs. uncached)
MODEL_PRICING = {
    "claude-sonnet-4-6":  {"input": 3.00, "output": 15.00, "cache_write": 3.75, "cache_read": 0.30},
    "claude-opus-4-7":    {"input": 15.00, "output": 75.00, "cache_write": 18.75, "cache_read": 1.50},
    "claude-opus-4-6":    {"input": 15.00, "output": 75.00, "cache_write": 18.75, "cache_read": 1.50},
    "claude-haiku-4-5":   {"input": 1.00, "output": 5.00, "cache_write": 1.25, "cache_read": 0.10},
}

DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS_OUT = 1024        # JSON scoring output is ~300-500 tokens; 1024 is safe ceiling
API_SLEEP_SECONDS = 0.5      # small pause between calls to avoid burst rate limits
MAX_RETRIES = 3              # on transient API failure


# ---- SCHEMA -----------------------------------------------------------------
# The fields we expect the LLM to return (from the prompt spec).
EXPECTED_JSON_KEYS = {
    "maturation", "profit_mechanism", "retail_accessibility", "specificity", "horizon",
    "final", "flag", "time_to_thesis", "translation", "public_vehicles", "rationale",
}

# Columns written to the output CSV. Everything from the input is preserved
# (paper metadata), then LLM scores appended, then run metadata.
OUTPUT_COLUMNS = [
    # Input columns (preserved)
    "id", "domain", "title", "abstract", "url", "published",
    # LLM sub-scores
    "llm_maturation", "llm_profit_mechanism", "llm_retail_accessibility",
    "llm_specificity", "llm_horizon", "llm_final",
    # LLM extras
    "llm_flag", "llm_time_to_thesis", "llm_translation",
    "llm_public_vehicles", "llm_rationale",
    # Run metadata (for version tracking and cost audit)
    "prompt_version", "model", "input_tokens", "output_tokens",
    "cache_write_tokens", "cache_read_tokens", "cost_usd",
    "run_timestamp",
]


# ---- HELPERS ----------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Score arXiv papers with Claude.")
    p.add_argument("--input", default="eval_set_v1__Scoring.csv",
                   help="Input CSV with columns id, domain, title, abstract, url (at minimum).")
    p.add_argument("--output", default=None,
                   help="Output CSV path. Default: results_YYYY-MM-DD_HHMMSS.csv.")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"Model ID. Default: {DEFAULT_MODEL}.")
    p.add_argument("--limit", type=int, default=None,
                   help="Score only first N papers (useful for smoke tests).")
    p.add_argument("--resume", action="store_true",
                   help="If output file exists, skip papers already scored.")
    return p.parse_args()


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    model: str,
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    """Compute dollar cost for a single call given token usage.

    cache_write_tokens: tokens written to cache on the first call (1.25x rate).
    cache_read_tokens:  tokens served from cache on subsequent calls (0.10x rate).
    input_tokens here is the non-cached input (user message + any uncached content).
    """
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        return 0.0   # unknown model; caller will see $0 and can update MODEL_PRICING
    return (
        input_tokens       * pricing["input"]       / 1_000_000
        + output_tokens    * pricing["output"]      / 1_000_000
        + cache_write_tokens * pricing.get("cache_write", pricing["input"] * 1.25) / 1_000_000
        + cache_read_tokens  * pricing.get("cache_read",  pricing["input"] * 0.10) / 1_000_000
    )


def load_papers(path: str, limit: int | None) -> list[dict]:
    """Read papers from a CSV. Required columns: id, domain, title, abstract."""
    papers = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Minimal validation — fail loudly if required columns are missing.
            for col in ("id", "domain", "title", "abstract"):
                if col not in row:
                    raise ValueError(f"Input CSV missing required column: {col}")
            papers.append(row)
    if limit is not None:
        papers = papers[:limit]
    return papers


def load_already_scored(output_path: str) -> set[str]:
    """Return set of paper IDs already present in a single output CSV (for --resume)."""
    if not Path(output_path).exists():
        return set()
    scored = set()
    with open(output_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("id"):
                scored.add(row["id"])
    return scored


def load_all_scored_ids(results_glob: str = "results_*.csv") -> set[str]:
    """
    Scan every results_*.csv in the current directory and return the set of
    all paper IDs that have ever been scored.

    This is the global dedup check — prevents re-scoring papers that appeared
    in a previous run's 7-day fetch window. Called automatically on every run
    (no flag needed). Typically reduces a 200-paper fetch to 20-30 new papers.
    """
    import glob as _glob
    all_ids: set[str] = set()
    result_files = sorted(_glob.glob(results_glob))
    for path in result_files:
        try:
            with open(path, encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("id"):
                        all_ids.add(row["id"])
        except Exception:
            pass   # skip unreadable files silently
    return all_ids


def call_claude(client: Anthropic, model: str, user_msg: str) -> tuple[dict, int, int, int, int]:
    """
    Call the API with retry on transient errors.
    Returns (parsed_json, in_tokens, out_tokens, cache_write_tokens, cache_read_tokens).

    The system prompt is passed with cache_control="ephemeral" so Anthropic caches it
    after the first call. Subsequent calls in the same run pay ~10% of normal input cost
    for the system prompt instead of 100%.

    Raises ValueError if the response isn't valid JSON matching the expected schema.
    """
    # Pass system as a list with cache_control on the last (only) block.
    # Anthropic caches everything up to and including the last block marked ephemeral.
    cached_system = [
        {
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ]

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=MAX_TOKENS_OUT,
                system=cached_system,
                messages=[{"role": "user", "content": user_msg}],
            )
            text = response.content[0].text.strip()
            # Be defensive: some models occasionally wrap JSON in code fences
            # despite the prompt saying not to. Strip if present.
            if text.startswith("```"):
                text = text.strip("`")
                if text.startswith("json"):
                    text = text[4:].strip()
            parsed = json.loads(text)
            missing = EXPECTED_JSON_KEYS - set(parsed.keys())
            if missing:
                raise ValueError(f"LLM response missing keys: {missing}")

            # Extract cache token counts (present when caching is active; default 0).
            cache_write = getattr(response.usage, "cache_creation_input_tokens", 0) or 0
            cache_read  = getattr(response.usage, "cache_read_input_tokens", 0) or 0
            return parsed, response.usage.input_tokens, response.usage.output_tokens, cache_write, cache_read

        except (APIError, json.JSONDecodeError, ValueError) as e:
            last_err = e
            if attempt < MAX_RETRIES:
                wait = 2 ** attempt   # exponential backoff: 2s, 4s
                print(f"    retry {attempt}/{MAX_RETRIES} after error: {e} (waiting {wait}s)",
                      file=sys.stderr)
                time.sleep(wait)
            else:
                raise

    # Unreachable, but mypy-happy
    raise last_err  # type: ignore[misc]


def score_paper(client: Anthropic, paper: dict, model: str) -> dict:
    """
    Score a single paper. Returns a dict ready to write as a CSV row
    (keys match OUTPUT_COLUMNS).
    """
    user_msg = build_user_message(paper)
    parsed, in_tok, out_tok, cache_write_tok, cache_read_tok = call_claude(client, model, user_msg)

    cost = estimate_cost(in_tok, out_tok, model, cache_write_tok, cache_read_tok)

    return {
        # Preserve input metadata (blank-safe — `published` is missing from
        # the original eval set CSV but present in fetcher output)
        "id":        paper.get("id", ""),
        "domain":    paper.get("domain", ""),
        "title":     paper.get("title", ""),
        "abstract":  paper.get("abstract", ""),
        "url":       paper.get("url", ""),
        "published": paper.get("published", ""),
        # LLM sub-scores
        "llm_maturation":            parsed["maturation"],
        "llm_profit_mechanism":      parsed["profit_mechanism"],
        "llm_retail_accessibility":  parsed["retail_accessibility"],
        "llm_specificity":           parsed["specificity"],
        "llm_horizon":               parsed["horizon"],
        "llm_final":                 parsed["final"],
        # LLM extras
        "llm_flag":             parsed["flag"],
        "llm_time_to_thesis":   parsed["time_to_thesis"],
        "llm_translation":      parsed["translation"],
        # Lists: json-dump so CSV round-trips cleanly
        "llm_public_vehicles":  json.dumps(parsed["public_vehicles"]),
        "llm_rationale":        parsed["rationale"],
        # Run metadata
        "prompt_version":     PROMPT_VERSION,
        "model":              model,
        "input_tokens":       in_tok,
        "output_tokens":      out_tok,
        "cache_write_tokens": cache_write_tok,
        "cache_read_tokens":  cache_read_tok,
        "cost_usd":           round(cost, 6),
        "run_timestamp":      datetime.now().isoformat(timespec="seconds"),
    }


# ---- MAIN -------------------------------------------------------------------

def main() -> int:
    args = parse_args()

    # Default output filename: timestamped so nothing is silently overwritten.
    if args.output is None:
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        args.output = f"results_{stamp}.csv"

    # Check env + API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY env var not set. See setup instructions at top of file.",
              file=sys.stderr)
        return 2

    # Warn if model pricing unknown (cost summary will be zero)
    if args.model not in MODEL_PRICING:
        print(f"WARNING: unknown model '{args.model}' — cost tracking will report $0. "
              f"Update MODEL_PRICING in this file.", file=sys.stderr)

    papers = load_papers(args.input, args.limit)

    # Global dedup: skip any paper already scored in ANY previous results_*.csv.
    # This prevents re-scoring the same papers that fall in overlapping 7-day
    # fetch windows. Runs automatically — no flag needed.
    globally_scored = load_all_scored_ids()

    # --resume: additionally skip papers already in THIS run's output file.
    # Useful for resuming a run that crashed partway through.
    resume_scored = load_already_scored(args.output) if args.resume else set()

    already_scored = globally_scored | resume_scored
    to_score = [p for p in papers if p["id"] not in already_scored]

    skipped_global = len([p for p in papers if p["id"] in globally_scored])
    skipped_resume = len([p for p in papers if p["id"] in resume_scored - globally_scored])

    print(f"Input: {args.input} ({len(papers)} papers total)")
    if skipped_global:
        print(f"  Skipped {skipped_global} already scored in previous runs")
    if skipped_resume:
        print(f"  Skipped {skipped_resume} already in current output file (--resume)")
    print(f"  → {len(to_score)} new papers to score")

    if len(to_score) == 0:
        print("Nothing new to score. Run the fetcher to pull fresh papers.")
        return 0

    print(f"Output: {args.output}")
    print(f"Model: {args.model}    Prompt version: {PROMPT_VERSION}")
    print(f"Scoring {len(to_score)} papers...\n")

    client = Anthropic()   # reads ANTHROPIC_API_KEY from env

    # Open output file in append mode so --resume works and crashes don't lose prior rows.
    first_write = not Path(args.output).exists()
    with open(args.output, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        if first_write:
            writer.writeheader()

        total_cost = 0.0
        total_in = 0
        total_out = 0
        total_cache_write = 0
        total_cache_read = 0
        ok = 0
        failed = 0

        for i, paper in enumerate(to_score, start=1):
            title_preview = paper["title"][:60]
            print(f"  [{i:>3}/{len(to_score)}] #{paper['id']} {paper['domain']:<8} {title_preview}...",
                  end=" ", flush=True)
            try:
                row = score_paper(client, paper, args.model)
                writer.writerow(row)
                f.flush()   # persist each row immediately (crash-safety)
                total_cost += row["cost_usd"]
                total_in += row["input_tokens"]
                total_out += row["output_tokens"]
                total_cache_write += row["cache_write_tokens"]
                total_cache_read  += row["cache_read_tokens"]
                ok += 1
                print(f"final={row['llm_final']} flag={row['llm_flag']} (${row['cost_usd']:.4f})")
            except Exception as e:
                failed += 1
                print(f"FAILED: {e}")

            time.sleep(API_SLEEP_SECONDS)

    # Summary
    print("\n--- Summary ---")
    print(f"  Scored: {ok}  Failed: {failed}")
    print(f"  Tokens in/out: {total_in:,} / {total_out:,}")
    if total_cache_write or total_cache_read:
        print(f"  Cache write tokens: {total_cache_write:,}  Cache read tokens: {total_cache_read:,}")
        # Show what the same run would have cost without caching for comparison
        pricing = MODEL_PRICING.get(args.model)
        if pricing:
            uncached_cost = (total_in + total_cache_write + total_cache_read) * pricing["input"] / 1_000_000 \
                            + total_out * pricing["output"] / 1_000_000
            print(f"  Estimated cost without caching: ${uncached_cost:.4f}  Actual: ${total_cost:.4f}  "
                  f"Saved: ${uncached_cost - total_cost:.4f} ({100*(1 - total_cost/uncached_cost):.0f}%)")
    print(f"  Total cost: ${total_cost:.4f}")
    if ok > 0:
        print(f"  Avg per paper: ${total_cost / ok:.4f}")
    print(f"  Output written to: {args.output}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())