"""
rescore_top11.py — One-off re-score of top 11 papers with v0.4 prompt
----------------------------------------------------------------------
Scores a fixed list of arXiv IDs using the current prompt (v0.3), which
adds the Horizon dimension and longshot flag. Bypasses global dedup so
these papers get scored even though they exist in previous results CSVs.

Output: results_top11_rescore.csv — load this in the digest to preview
the new Horizon scores before committing to a full re-score.

RUN:
    py -3.14 rescore_top11.py

Takes ~2 minutes and costs ~$0.10-0.15.
"""

import csv
import os
import sys
import time
from pathlib import Path

# IDs to re-score — top 11 real arXiv papers by final score
TARGET_IDS = [
    "2605.00416",  # Fleet-Scale RL for Generalist Robot Policies (Robotics, 6.0 watchlist)
    "2605.00214",  # Tunable Entanglement from Thin-Film Lithium Niobate (Quantum, 4.5)
    "2605.00471",  # Stereo Multistage Spatial Attention (Robotics, 4.5)
    "2604.28057",  # Autonomous Delivery Vehicles Marshaling Yard (Robotics, 4.5)
    "2605.00464",  # Vertical GaN Devices on Silicon Wafers (Energy, 4.5)
    "2604.25559",  # ECMWF AIFS Surface Ocean (Climate, 4.5)
    "2605.00817",  # LLMs Stop Following Steps (AI, 4.0)
    "2605.00793",  # Denoising Low Dose Liver CT (AI, 4.0)
    "2605.00789",  # LVLM KV Cache Lightweight (AI, 4.0)
    "2605.00782",  # GeoContra GIS Code (AI, 4.0)
    "2605.00754",  # Themis Multilingual Code Reward (AI, 4.0)
]

OUTPUT_FILE = "results_top11_rescore.csv"


def main() -> int:
    # Change to project dir so relative imports and file paths work
    project_dir = Path(__file__).resolve().parent
    os.chdir(project_dir)
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from week2_run_scoring import (
        load_papers, score_paper, OUTPUT_COLUMNS,
        DEFAULT_MODEL, PROMPT_VERSION, MODEL_PRICING, API_SLEEP_SECONDS,
    )
    from anthropic import Anthropic

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set.", file=sys.stderr)
        return 2

    # Load papers from all results CSVs — abstracts are preserved there even
    # after papers age out of the 7-day arxiv_papers.csv fetch window.
    import glob as _glob
    target_set = set(TARGET_IDS)
    seen_ids: set[str] = set()
    to_score: list[dict] = []

    for path in sorted(_glob.glob("results_*.csv")):
        try:
            papers = load_papers(path, limit=None)
            for p in papers:
                if p["id"] in target_set and p["id"] not in seen_ids:
                    to_score.append(p)
                    seen_ids.add(p["id"])
        except Exception:
            pass

    missing = target_set - seen_ids
    if missing:
        print(f"WARNING: {len(missing)} IDs not found in any results CSV: {missing}")

    print(f"Prompt version: {PROMPT_VERSION}")
    print(f"Scoring {len(to_score)} papers → {OUTPUT_FILE}\n")

    client = Anthropic()
    total_cost = 0.0
    ok = failed = 0

    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()

        for i, paper in enumerate(to_score, start=1):
            print(f"  [{i:>2}/{len(to_score)}] {paper['domain']:<8} {paper['title'][:55]}...",
                  end=" ", flush=True)
            try:
                row = score_paper(client, paper, DEFAULT_MODEL)
                writer.writerow(row)
                f.flush()
                total_cost += row["cost_usd"]
                ok += 1
                hrz = row.get("llm_horizon", "?")
                print(f"final={row['llm_final']} hrz={hrz} flag={row['llm_flag']} (${row['cost_usd']:.4f})")
            except Exception as e:
                failed += 1
                print(f"FAILED: {e}")
            time.sleep(API_SLEEP_SECONDS)

    print(f"\nDone. Scored {ok}, failed {failed}. Total cost: ${total_cost:.4f}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"\nTo view in digest: open the app and set the CSV path to '{OUTPUT_FILE}'")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
