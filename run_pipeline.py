"""
run_pipeline.py — One command to fetch, score, and open the digest
-------------------------------------------------------------------
Chains the three pipeline stages in order:

  1. week1_arxiv_fetcher.py   — pull fresh papers from arXiv → arxiv_papers.csv
  2. week2_run_scoring.py     — score with Claude → results_YYYY-MM-DD_HHMMSS.csv
  3. week4_digest.py          — launch Streamlit digest in the browser

Each stage is run as a subprocess so this script stays decoupled from the
internals of the other files. If any stage fails (non-zero exit code), the
pipeline halts immediately with a clear error message.

RUN:
    py -3.14 run_pipeline.py                    # full run + open browser
    py -3.14 run_pipeline.py --limit 5          # score only 5 papers (smoke test)
    py -3.14 run_pipeline.py --no-browser       # run but don't open the digest
    py -3.14 run_pipeline.py --skip-fetch       # score existing arxiv_papers.csv
    py -3.14 run_pipeline.py --dry-run          # print commands, don't execute

NOTES:
- The digest (stage 3) launches as a background process so the pipeline
  returns control to your terminal. Stop the digest with Ctrl-C in its window,
  or just close the browser — the Streamlit server keeps running until you
  kill it explicitly.
- If a Streamlit server is already running on 8501, the browser will open to
  the existing one. That's fine — just hit the "Reload data" button in the UI.
- Wall time: ~30s fetch + ~5-15 min score (depends on paper count). The
  progress output of each stage prints live so you can watch it.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


# ---- CONFIG ------------------------------------------------------------------

PYTHON = "py"           # Windows Python launcher; change to "python" if needed
PYTHON_VER = "-3.14"
FETCHER  = "week1_arxiv_fetcher.py"
SCORER   = "week2_run_scoring.py"
DIGEST   = "week4_digest.py"
STREAMLIT_URL = "http://localhost:8501"
STREAMLIT_STARTUP_WAIT = 3   # seconds to wait before opening browser


# ---- HELPERS -----------------------------------------------------------------

def banner(text: str) -> None:
    """Print a clearly visible stage header."""
    width = 60
    print()
    print("=" * width)
    print(f"  {text}")
    print("=" * width)


def run_stage(label: str, cmd: list[str], dry_run: bool) -> None:
    """
    Run a subprocess stage. Prints the command, streams output live,
    and raises SystemExit on non-zero return code.
    """
    banner(f"STAGE: {label}")
    print(f"  $ {' '.join(cmd)}\n")

    if dry_run:
        print("  [dry-run: skipping execution]")
        return

    result = subprocess.run(cmd)   # inherits stdout/stderr → live output
    if result.returncode != 0:
        print(f"\n  ERROR: '{label}' exited with code {result.returncode}. "
              f"Pipeline halted.", file=sys.stderr)
        sys.exit(result.returncode)


def launch_digest(dry_run: bool, no_browser: bool) -> None:
    """
    Launch Streamlit as a background process, then open the browser.
    Returns immediately — Streamlit keeps running independently.
    """
    banner("STAGE: Launch digest")
    cmd = [PYTHON, PYTHON_VER, "-m", "streamlit", "run", DIGEST,
           "--server.headless", "true"]
    print(f"  $ {' '.join(cmd)}")
    print(f"  Digest will be available at {STREAMLIT_URL}")

    if dry_run:
        print("  [dry-run: skipping execution]")
        return

    # Launch detached — we don't wait for it to finish.
    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if not no_browser:
        print(f"\n  Waiting {STREAMLIT_STARTUP_WAIT}s for Streamlit to start...")
        time.sleep(STREAMLIT_STARTUP_WAIT)
        webbrowser.open(STREAMLIT_URL)
        print(f"  Browser opened → {STREAMLIT_URL}")
    else:
        print("  --no-browser set: digest running but browser not opened.")

    print("\n  Streamlit is running in the background.")
    print("  To stop it: find and kill the 'streamlit' process, or close its terminal.")


# ---- MAIN -------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fetch → Score → Digest in one command.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--limit", type=int, default=None, metavar="N",
        help="Pass --limit N to the scorer (score only first N papers). "
             "Useful for quick smoke tests without fetching fewer papers.",
    )
    p.add_argument(
        "--skip-fetch", action="store_true",
        help="Skip the fetcher stage and score the existing arxiv_papers.csv.",
    )
    p.add_argument(
        "--no-browser", action="store_true",
        help="Launch the digest but don't open the browser automatically.",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Print the commands that would be run without executing them.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    # Verify we're in the right directory
    if not Path(FETCHER).exists() or not Path(SCORER).exists():
        print(
            f"ERROR: Could not find {FETCHER} or {SCORER} in the current directory.\n"
            f"Run this script from the trend-engine project folder.",
            file=sys.stderr,
        )
        return 1

    start = time.time()
    print("\nTrend Engine Pipeline")
    print(f"  dry-run={args.dry_run}  skip-fetch={args.skip_fetch}  "
          f"limit={args.limit}  no-browser={args.no_browser}")

    # Stage 1: Fetch
    if not args.skip_fetch:
        run_stage(
            "Fetch papers from arXiv",
            [PYTHON, PYTHON_VER, FETCHER],
            dry_run=args.dry_run,
        )
    else:
        banner("STAGE: Fetch papers from arXiv")
        print("  --skip-fetch set: using existing arxiv_papers.csv")

    # Stage 2: Score
    scorer_cmd = [PYTHON, PYTHON_VER, SCORER, "--input", "arxiv_papers.csv"]
    if args.limit is not None:
        scorer_cmd += ["--limit", str(args.limit)]
    run_stage(
        "Score papers with Claude",
        scorer_cmd,
        dry_run=args.dry_run,
    )

    # Stage 3: Digest
    launch_digest(dry_run=args.dry_run, no_browser=args.no_browser)

    elapsed = time.time() - start
    banner(f"Pipeline complete in {elapsed:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
