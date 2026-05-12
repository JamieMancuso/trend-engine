"""
Week 7 News Scorer — score news items via Haiku
------------------------------------------------
Reads a news_*.csv produced by week7_news_fetcher.py, scores each item using
the v0.1 news rubric (see week7_news_scoring_prompt_v01.py) on Haiku 4.5,
and writes news_results_*.csv.

Mirrors week2_run_scoring.py patterns but is intentionally simpler:
- 3-axis schema (signal_strength, investment_relevance, tag) + flag + translation
- Haiku 4.5 (per scoping doc: ~10× cheaper, fine for short summaries)
- Same prompt-caching + retry + cost-tracking machinery

GLOBAL DEDUP: news IDs are namespaced (e.g. "hn:12345") and the scorer scans all
news_results_*.csv to skip already-scored items. --rescore-missing bypasses for
prompt-version backfills (matches the paper-scorer convention).

RUN:
    py -3.14 week7_news_scoring.py --input news_hn_2026-05-11_*.csv
    py -3.14 week7_news_scoring.py --input <file> --limit 5      # smoke test
    py -3.14 week7_news_scoring.py --input <file> --rescore-missing
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from anthropic import Anthropic, APIError

from week7_news_scoring_prompt_v01 import (
    SYSTEM_PROMPT, build_user_message, PROMPT_VERSION,
    ALLOWED_TAGS, ALLOWED_FLAGS,
)


# ---- MODEL + COST CONFIG ----------------------------------------------------
# Haiku 4.5 pricing — per 1M tokens. cache_write/cache_read mirror the paper scorer.
MODEL_PRICING = {
    "claude-haiku-4-5":          {"input": 1.00, "output": 5.00, "cache_write": 1.25, "cache_read": 0.10},
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00, "cache_write": 1.25, "cache_read": 0.10},
    "claude-sonnet-4-6":         {"input": 3.00, "output": 15.00, "cache_write": 3.75, "cache_read": 0.30},
}

DEFAULT_MODEL = "claude-haiku-4-5"
MAX_TOKENS_OUT = 512        # news output ~150-300 tokens
API_SLEEP_SECONDS = 0.3
MAX_RETRIES = 3


# ---- SCHEMA -----------------------------------------------------------------
# v0.2 added market_impact alongside signal_strength + investment_relevance.
EXPECTED_JSON_KEYS = {
    "signal_strength", "investment_relevance", "market_impact",
    "tag", "flag", "translation",
}

OUTPUT_COLUMNS = [
    # From input (preserved)
    "id", "source", "title", "url", "author", "posted_at",
    "hn_score", "hn_comments", "fetched_at",
    # LLM scores
    "llm_signal_strength", "llm_investment_relevance", "llm_market_impact",
    "llm_tag", "llm_flag", "llm_translation",
    # Run metadata
    "prompt_version", "model", "input_tokens", "output_tokens",
    "cache_write_tokens", "cache_read_tokens", "cost_usd",
    "run_timestamp",
]


# ---- HELPERS ----------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Score news items with Claude Haiku.")
    p.add_argument("--input", required=True,
                   help="Input CSV from week7_news_fetcher.py.")
    p.add_argument("--output", default=None,
                   help="Output CSV. Default: news_results_YYYY-MM-DD_HHMMSS.csv.")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--limit", type=int, default=None,
                   help="Score only first N items (smoke test).")
    p.add_argument("--resume", action="store_true",
                   help="If output file exists, skip rows already scored in it.")
    p.add_argument("--rescore-missing", action="store_true",
                   help="Bypass global dedup across all news_results_*.csv. "
                        "Used for prompt-version backfills.")
    return p.parse_args()


def estimate_cost(in_tok: int, out_tok: int, model: str,
                  cache_w: int = 0, cache_r: int = 0) -> float:
    p = MODEL_PRICING.get(model)
    if p is None:
        return 0.0
    return (
        in_tok      * p["input"]                                / 1_000_000
        + out_tok   * p["output"]                               / 1_000_000
        + cache_w   * p.get("cache_write", p["input"] * 1.25)   / 1_000_000
        + cache_r   * p.get("cache_read",  p["input"] * 0.10)   / 1_000_000
    )


def load_items(path: str, limit: int | None) -> list[dict]:
    items = []
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            for col in ("id", "title"):
                if col not in row:
                    raise ValueError(f"Input missing required column: {col}")
            items.append(row)
    return items[:limit] if limit else items


def load_already_scored(path: str) -> set[str]:
    if not Path(path).exists():
        return set()
    out = set()
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("id"):
                out.add(row["id"])
    return out


def load_all_news_scored_ids(pattern: str = "news_results_*.csv") -> set[str]:
    """Scan all prior news_results CSVs; return union of IDs (for global dedup)."""
    out: set[str] = set()
    for p in sorted(glob.glob(pattern)):
        try:
            with open(p, encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    if row.get("id"):
                        out.add(row["id"])
        except Exception:
            pass
    return out


def call_claude(client: Anthropic, model: str, user_msg: str
                ) -> tuple[dict, int, int, int, int]:
    cached_system = [
        {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
    ]
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=MAX_TOKENS_OUT,
                system=cached_system,
                messages=[{"role": "user", "content": user_msg}],
            )
            text = resp.content[0].text.strip()
            if text.startswith("```"):
                text = text.strip("`")
                if text.startswith("json"):
                    text = text[4:].strip()
            parsed = json.loads(text)
            missing = EXPECTED_JSON_KEYS - set(parsed.keys())
            if missing:
                raise ValueError(f"LLM response missing keys: {missing}")
            # Soft-validate enums; coerce to "other"/"skip" if model strays.
            if parsed["tag"] not in ALLOWED_TAGS:
                parsed["tag"] = "other"
            if parsed["flag"] not in ALLOWED_FLAGS:
                parsed["flag"] = "skip"
            cw = getattr(resp.usage, "cache_creation_input_tokens", 0) or 0
            cr = getattr(resp.usage, "cache_read_input_tokens", 0) or 0
            return parsed, resp.usage.input_tokens, resp.usage.output_tokens, cw, cr
        except (APIError, json.JSONDecodeError, ValueError) as e:
            last_err = e
            if attempt < MAX_RETRIES:
                wait = 2 ** attempt
                print(f"    retry {attempt}/{MAX_RETRIES} after error: {e} (waiting {wait}s)",
                      file=sys.stderr)
                time.sleep(wait)
            else:
                raise
    raise last_err  # type: ignore[misc]


def score_item(client: Anthropic, item: dict, model: str) -> dict:
    user_msg = build_user_message(item)
    parsed, in_tok, out_tok, cw, cr = call_claude(client, model, user_msg)
    cost = estimate_cost(in_tok, out_tok, model, cw, cr)
    return {
        "id":          item.get("id", ""),
        "source":      item.get("source", ""),
        "title":       item.get("title", ""),
        "url":         item.get("url", ""),
        "author":      item.get("author", ""),
        "posted_at":   item.get("posted_at", ""),
        "hn_score":    item.get("hn_score", ""),
        "hn_comments": item.get("hn_comments", ""),
        "fetched_at":  item.get("fetched_at", ""),
        "llm_signal_strength":      parsed["signal_strength"],
        "llm_investment_relevance": parsed["investment_relevance"],
        "llm_market_impact":        parsed["market_impact"],
        "llm_tag":         parsed["tag"],
        "llm_flag":        parsed["flag"],
        "llm_translation": parsed["translation"],
        "prompt_version":     PROMPT_VERSION,
        "model":              model,
        "input_tokens":       in_tok,
        "output_tokens":      out_tok,
        "cache_write_tokens": cw,
        "cache_read_tokens":  cr,
        "cost_usd":           round(cost, 6),
        "run_timestamp":      datetime.now().isoformat(timespec="seconds"),
    }


def main() -> int:
    args = parse_args()

    if args.output is None:
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        args.output = f"news_results_{stamp}.csv"

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY env var not set.", file=sys.stderr)
        return 2

    if args.model not in MODEL_PRICING:
        print(f"WARNING: unknown model '{args.model}' — cost tracking will report $0.",
              file=sys.stderr)

    items = load_items(args.input, args.limit)

    globally_scored = set() if args.rescore_missing else load_all_news_scored_ids()
    resume_scored = load_already_scored(args.output) if args.resume else set()
    skip_set = globally_scored | resume_scored
    to_score = [it for it in items if it["id"] not in skip_set]

    print(f"Input: {args.input} ({len(items)} items)")
    if args.rescore_missing:
        print(f"  --rescore-missing: global dedup BYPASSED")
    if globally_scored:
        already = len([it for it in items if it["id"] in globally_scored])
        print(f"  Skipped {already} already scored in previous news runs")
    print(f"  → {len(to_score)} to score")

    if not to_score:
        print("Nothing new. Run the fetcher to pull fresh items.")
        return 0

    print(f"Output: {args.output}")
    print(f"Model: {args.model}    Prompt: {PROMPT_VERSION}\n")

    client = Anthropic()
    first_write = not Path(args.output).exists()
    total_cost = total_in = total_out = total_cw = total_cr = 0
    ok = failed = 0

    with open(args.output, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        if first_write:
            w.writeheader()
        for i, item in enumerate(to_score, start=1):
            preview = item["title"][:55]
            print(f"  [{i:>3}/{len(to_score)}] {item['id']:<14} {preview}...",
                  end=" ", flush=True)
            try:
                row = score_item(client, item, args.model)
                w.writerow(row)
                f.flush()
                total_cost += row["cost_usd"]
                total_in += row["input_tokens"]
                total_out += row["output_tokens"]
                total_cw += row["cache_write_tokens"]
                total_cr += row["cache_read_tokens"]
                ok += 1
                print(f"sig={row['llm_signal_strength']} rel={row['llm_investment_relevance']} "
                      f"mkt={row['llm_market_impact']} tag={row['llm_tag']} "
                      f"flag={row['llm_flag']} (${row['cost_usd']:.4f})")
            except Exception as e:
                failed += 1
                print(f"FAILED: {e}")
            time.sleep(API_SLEEP_SECONDS)

    print("\n--- Summary ---")
    print(f"  Scored: {ok}  Failed: {failed}")
    print(f"  Tokens in/out: {total_in:,} / {total_out:,}")
    if total_cw or total_cr:
        print(f"  Cache write: {total_cw:,}  Cache read: {total_cr:,}")
        p = MODEL_PRICING.get(args.model)
        if p:
            uncached = (total_in + total_cw + total_cr) * p["input"] / 1_000_000 \
                     + total_out * p["output"] / 1_000_000
            saved = uncached - total_cost
            pct = 100 * (1 - total_cost / uncached) if uncached else 0
            print(f"  Without caching: ${uncached:.4f}  Actual: ${total_cost:.4f}  "
                  f"Saved: ${saved:.4f} ({pct:.0f}%)")
    print(f"  Total cost: ${total_cost:.4f}")
    if ok:
        print(f"  Avg per item: ${total_cost / ok:.4f}")
    print(f"  Output: {args.output}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
