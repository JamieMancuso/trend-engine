"""
week3_semantic_scholar.py

Enriches the Week 2 scored CSV with Semantic Scholar citation metadata.
Adds three columns alongside the existing LLM scores:
  - s2_citations_total: lifetime citation count
  - s2_citations_12mo:  citations in the last 12 months (the velocity signal)
  - s2_influential_citations: S2's "influential" flag count

Design notes:
  - Public S2 endpoint, ~1 req/sec shared pool. Script self-rate-limits and
    handles 429 with exponential backoff.
  - Disk cache in .s2_cache/ keyed by arXiv ID. Delete to force refresh.
  - Failures populate s2_error and leave numeric columns as None — they don't
    abort the run.
  - 12-month velocity is computed locally from each citation's publicationDate
    because S2 doesn't expose a windowed count directly.

Usage:
  python week3_semantic_scholar.py --input scored.csv --output scored_enriched.csv
  python week3_semantic_scholar.py --eval   # runs against the 18-paper eval set
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

# ---- Config ---------------------------------------------------------------

S2_BASE = "https://api.semanticscholar.org/graph/v1"
RATE_LIMIT_SLEEP = 1.1          # seconds between requests; public pool is ~1 rps
MAX_RETRIES = 4                 # for 429 / 5xx
BACKOFF_BASE = 2.0
REQUEST_TIMEOUT = 30
CACHE_DIR = Path(".s2_cache")
ARXIV_COL = "url"               # column in the scored CSV holding the arXiv URL
EVAL_PATH = "eval_set_v1__Scoring.csv"  # adjust if your eval CSV lives elsewhere

# Fields to request on the paper lookup
PAPER_FIELDS = "paperId,title,citationCount,influentialCitationCount,publicationDate"
# Fields to request on each citing paper (for the 12-month window calc)
CITATION_FIELDS = "publicationDate,isInfluential"

# ---- arXiv ID parsing -----------------------------------------------------

# Matches both new-style (2403.12345) and old-style (hep-th/9901001) arXiv IDs,
# with optional version suffix.
_ARXIV_RE = re.compile(
    r"(?:arxiv\.org/abs/)?"
    r"(?P<id>(?:\d{4}\.\d{4,5}|[a-z\-]+(?:\.[a-z\-]+)?/\d{7}))"
    r"(?:v\d+)?"
    r"(?![\d.])",
    re.IGNORECASE,
)


def parse_arxiv_id(value: str) -> Optional[str]:
    """Extract a bare arXiv ID from a URL, versioned ID, or bare ID. Strips version."""
    if not isinstance(value, str):
        return None
    m = _ARXIV_RE.search(value.strip())
    return m.group("id") if m else None


# ---- HTTP layer with caching and backoff ---------------------------------

def _cache_path(arxiv_id: str, suffix: str) -> Path:
    safe = arxiv_id.replace("/", "_")
    return CACHE_DIR / f"{safe}.{suffix}.json"


def _load_cache(arxiv_id: str, suffix: str):
    p = _cache_path(arxiv_id, suffix)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            return None
    return None


def _save_cache(arxiv_id: str, suffix: str, data) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    _cache_path(arxiv_id, suffix).write_text(json.dumps(data))


def _get_with_backoff(url: str, params: dict) -> Optional[dict]:
    """GET with exponential backoff on 429/5xx. Returns None on terminal failure."""
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(BACKOFF_BASE ** attempt)
            continue

        if r.status_code == 200:
            return r.json()
        if r.status_code == 404:
            return None  # paper not in S2; not retryable
        if r.status_code in (429, 500, 502, 503, 504):
            wait = BACKOFF_BASE ** attempt
            # Honor Retry-After if present
            ra = r.headers.get("Retry-After")
            if ra and ra.isdigit():
                wait = max(wait, int(ra))
            time.sleep(wait)
            continue
        # Other 4xx: bail
        r.raise_for_status()
    return None


# ---- S2 fetchers ----------------------------------------------------------

def fetch_paper(arxiv_id: str) -> Optional[dict]:
    """Look up paper by arXiv ID. Cached. Returns S2 paper dict or None."""
    cached = _load_cache(arxiv_id, "paper")
    if cached is not None:
        return cached

    url = f"{S2_BASE}/paper/arXiv:{arxiv_id}"
    data = _get_with_backoff(url, {"fields": PAPER_FIELDS})
    time.sleep(RATE_LIMIT_SLEEP)
    if data is not None:
        _save_cache(arxiv_id, "paper", data)
    return data


def fetch_citations(paper_id: str, arxiv_id: str) -> Optional[list]:
    """
    Fetch citing papers (paginated). Cached by arxiv_id.
    Returns a list of {publicationDate, isInfluential} dicts, or None on failure.
    Caps at 1000 citations to bound API cost — papers with >1000 cites are
    already obviously high-attention and don't need exact counts for the gate.
    """
    cached = _load_cache(arxiv_id, "citations")
    if cached is not None:
        return cached

    out = []
    offset = 0
    page_size = 1000  # S2 max
    cap = 1000
    while True:
        url = f"{S2_BASE}/paper/{paper_id}/citations"
        data = _get_with_backoff(
            url,
            {"fields": CITATION_FIELDS, "offset": offset, "limit": page_size},
        )
        time.sleep(RATE_LIMIT_SLEEP)
        if data is None:
            return None
        for item in data.get("data", []):
            cp = item.get("citingPaper", {})
            out.append(
                {
                    "publicationDate": cp.get("publicationDate"),
                    "isInfluential": item.get("isInfluential", False),
                }
            )
        if len(out) >= cap or "next" not in data:
            break
        offset = data["next"]

    _save_cache(arxiv_id, "citations", out)
    return out


# ---- Velocity computation -------------------------------------------------

def citations_in_last_n_months(citations: list, months: int = 12) -> int:
    """Count citations whose publicationDate falls within the last `months`."""
    if not citations:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)
    n = 0
    for c in citations:
        pd_str = c.get("publicationDate")
        if not pd_str:
            continue
        try:
            d = datetime.strptime(pd_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if d >= cutoff:
            n += 1
    return n


# ---- Main enrichment loop -------------------------------------------------

def enrich_row(arxiv_url: str) -> dict:
    """Returns dict with s2_* columns for one paper."""
    result = {
        "s2_paper_id": None,
        "s2_citations_total": None,
        "s2_citations_12mo": None,
        "s2_influential_citations": None,
        "s2_error": None,
    }
    arxiv_id = parse_arxiv_id(arxiv_url)
    if arxiv_id is None:
        result["s2_error"] = f"could not parse arxiv id from: {arxiv_url!r}"
        return result

    try:
        paper = fetch_paper(arxiv_id)
    except Exception as e:
        result["s2_error"] = f"paper lookup failed: {e}"
        return result
    if paper is None:
        result["s2_error"] = "paper not found in S2"
        return result

    result["s2_paper_id"] = paper.get("paperId")
    result["s2_citations_total"] = paper.get("citationCount")
    result["s2_influential_citations"] = paper.get("influentialCitationCount")

    # Skip the citations call if there are zero citations — saves API budget
    if paper.get("citationCount", 0) == 0:
        result["s2_citations_12mo"] = 0
        return result

    try:
        cites = fetch_citations(paper["paperId"], arxiv_id)
    except Exception as e:
        result["s2_error"] = f"citations lookup failed: {e}"
        return result
    if cites is None:
        result["s2_error"] = "citations fetch returned None"
        return result

    result["s2_citations_12mo"] = citations_in_last_n_months(cites, months=12)
    return result


def enrich_csv(input_path: Path, output_path: Path) -> None:
    df = pd.read_csv(input_path)
    if ARXIV_COL not in df.columns:
        sys.exit(
            f"Error: expected column {ARXIV_COL!r} in {input_path}. "
            f"Found: {list(df.columns)}"
        )

    print(f"Enriching {len(df)} papers from {input_path}", file=sys.stderr)
    enriched = []
    for i, url in enumerate(df[ARXIV_COL], 1):
        row = enrich_row(url)
        enriched.append(row)
        status = row["s2_error"] or f"cites={row['s2_citations_total']} 12mo={row['s2_citations_12mo']}"
        print(f"  [{i}/{len(df)}] {url} -> {status}", file=sys.stderr)

    enriched_df = pd.DataFrame(enriched)
    out = pd.concat([df.reset_index(drop=True), enriched_df], axis=1)
    out.to_csv(output_path, index=False)

    n_ok = enriched_df["s2_error"].isna().sum()
    print(f"\nDone. {n_ok}/{len(df)} enriched successfully -> {output_path}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", type=Path, help="Path to scored CSV")
    ap.add_argument("--output", type=Path, help="Path to write enriched CSV")
    ap.add_argument("--eval", action="store_true", help=f"Run against eval set ({EVAL_PATH})")
    args = ap.parse_args()

    if args.eval:
        input_path = Path(EVAL_PATH)
        output_path = Path(EVAL_PATH).with_name(Path(EVAL_PATH).stem + "_enriched.csv")
    else:
        if not args.input or not args.output:
            ap.error("--input and --output are required unless --eval is passed")
        input_path = args.input
        output_path = args.output

    if not input_path.exists():
        sys.exit(f"Input not found: {input_path}")

    enrich_csv(input_path, output_path)


if __name__ == "__main__":
    main()