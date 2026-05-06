"""
scheduled_run.py — Headless pipeline runner for automated scheduling
---------------------------------------------------------------------
Called by the Cowork scheduler every other day at 9pm.
Does NOT open a browser or launch Streamlit.

Runs entirely in-process (no subprocess for Python stages) so it works in
the Cowork Linux sandbox, which doesn't have 'py -3.14' but does have
Python + the installed packages from the project's environment.

Steps:
  1. Fetch fresh papers from arXiv → arxiv_papers.csv
  2. Score new (never-before-scored) papers with Claude → results_*.csv
  3. git add + commit + push so Streamlit Cloud auto-redeploys

Run manually to test:
    py -3.14 scheduled_run.py        (Windows)
    python3 scheduled_run.py         (Linux / Cowork sandbox)

Logs are printed to stdout; Cowork captures them.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ---- PROJECT DIR ------------------------------------------------------------
# Resolve the project directory relative to this script's own location.
# This works whether we're on Windows (C:\Users\...\trend-engine) or the
# Cowork Linux sandbox (/sessions/.../mnt/trend-engine/), because the script
# always lives inside the project folder.
PROJECT_DIR = Path(__file__).resolve().parent

# Change cwd to the project dir so all relative paths in the imported modules
# (arxiv_papers.csv, results_*.csv, snapshots/, etc.) resolve correctly.
os.chdir(PROJECT_DIR)

# Add project dir to sys.path so we can import the pipeline modules directly.
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


# ---- STAGE HELPERS ----------------------------------------------------------

def banner(text: str) -> None:
    width = 55
    print(f"\n{'='*width}")
    print(f"  {text}")
    print(f"{'='*width}")


def git(args: list[str]) -> None:
    """Run a git command via subprocess. Halts on failure."""
    cmd = ["git"] + args
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=PROJECT_DIR)
    if result.returncode != 0:
        print(f"\nERROR: git {args[0]} failed (exit {result.returncode}). Halting.",
              file=sys.stderr)
        sys.exit(result.returncode)


# ---- STAGE 1: FETCH ---------------------------------------------------------

def run_fetch() -> None:
    banner("STAGE 1: Fetch papers from arXiv")
    from week1_arxiv_fetcher import (
        fetch_all_domains, filter_recent_papers, save_to_csv,
        DOMAINS, MAX_RESULTS_PER_DOMAIN, RECENCY_DAYS, SNAPSHOT_DIR, LATEST_FILE,
    )
    all_papers = fetch_all_domains(DOMAINS, MAX_RESULTS_PER_DOMAIN)
    recent = filter_recent_papers(all_papers, RECENCY_DAYS)
    save_to_csv(recent, SNAPSHOT_DIR, LATEST_FILE)
    print(f"Fetch complete: {len(recent)} papers written to {LATEST_FILE}")


# ---- STAGE 2: SCORE ---------------------------------------------------------

def run_score() -> None:
    banner("STAGE 2: Score new papers with Claude")

    # Import the scorer's helpers directly and replicate main()'s logic
    # so we can run headless without argparse.
    from week2_run_scoring import (
        load_papers, load_all_scored_ids, load_already_scored,
        score_paper, OUTPUT_COLUMNS, DEFAULT_MODEL, PROMPT_VERSION,
        MODEL_PRICING, estimate_cost, API_SLEEP_SECONDS,
    )
    from anthropic import Anthropic
    import csv
    from datetime import datetime as dt

    input_path = "arxiv_papers.csv"
    stamp = dt.now().strftime("%Y-%m-%d_%H%M%S")
    output_path = f"results_{stamp}.csv"
    model = DEFAULT_MODEL

    papers = load_papers(input_path, limit=None)
    globally_scored = load_all_scored_ids()
    to_score = [p for p in papers if p["id"] not in globally_scored]

    skipped = len(papers) - len(to_score)
    print(f"Input: {input_path} ({len(papers)} papers, {skipped} already scored)")
    print(f"  → {len(to_score)} new papers to score")

    if len(to_score) == 0:
        print("Nothing new to score. Skipping scoring stage.")
        return

    print(f"Output: {output_path}")
    print(f"Model: {model}    Prompt version: {PROMPT_VERSION}\n")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY env var not set.", file=sys.stderr)
        sys.exit(2)

    client = Anthropic()

    total_cost = 0.0
    total_in = total_out = total_cw = total_cr = 0
    ok = failed = 0

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()

        for i, paper in enumerate(to_score, start=1):
            title_preview = paper["title"][:55]
            print(f"  [{i:>3}/{len(to_score)}] {paper['domain']:<8} {title_preview}...",
                  end=" ", flush=True)
            try:
                row = score_paper(client, paper, model)
                writer.writerow(row)
                f.flush()
                total_cost += row["cost_usd"]
                total_in   += row["input_tokens"]
                total_out  += row["output_tokens"]
                total_cw   += row["cache_write_tokens"]
                total_cr   += row["cache_read_tokens"]
                ok += 1
                print(f"final={row['llm_final']} flag={row['llm_flag']} (${row['cost_usd']:.4f})")
            except Exception as e:
                failed += 1
                print(f"FAILED: {e}")
            time.sleep(API_SLEEP_SECONDS)

    print(f"\n--- Scoring summary ---")
    print(f"  Scored: {ok}  Failed: {failed}")
    print(f"  Tokens in/out: {total_in:,} / {total_out:,}")
    if total_cw or total_cr:
        pricing = MODEL_PRICING.get(model)
        if pricing:
            uncached = (total_in + total_cw + total_cr) * pricing["input"] / 1_000_000 \
                       + total_out * pricing["output"] / 1_000_000
            print(f"  Cache write: {total_cw:,}  Cache read: {total_cr:,}")
            print(f"  Saved vs uncached: ${uncached - total_cost:.4f}")
    print(f"  Total cost: ${total_cost:.4f}")
    print(f"  Output: {output_path}")


# ---- STAGE 3: GIT PUSH ------------------------------------------------------

def run_git_push() -> None:
    banner("STAGE 3: Commit and push to GitHub")
    stamp = datetime.now().strftime("%Y-%m-%d")

    git(["add", "results_*.csv", "arxiv_papers.csv"])
    git(["commit", "--allow-empty", "-m", f"Scheduled scoring run {stamp}"])
    git(["push"])
    print("Push complete. Streamlit Cloud will redeploy shortly.")


# ---- MAIN -------------------------------------------------------------------

def main() -> int:
    start = time.time()
    print(f"\nTrend Engine — Scheduled Run")
    print(f"Started:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Project dir: {PROJECT_DIR}")

    run_fetch()
    run_score()
    run_git_push()

    elapsed = time.time() - start
    banner(f"Done in {elapsed:.0f}s")
    print("Streamlit Cloud will redeploy shortly.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
