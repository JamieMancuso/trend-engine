"""
Week 1: arXiv Paper Fetcher (Multi-Domain Version)
---------------------------------------------------
Goal: Pull recent papers across 8 research domains from arXiv and save
      them to a dated CSV snapshot with a domain tag.

Domains covered:
  AI, Bio, Health, Space, Quantum, Robotics, Energy, Climate

Each paper gets tagged with its domain so you can filter later.

Output:
  - snapshots/arxiv_papers_YYYY-MM-DD.csv  (canonical dated record — never overwritten)
  - arxiv_papers.csv                       (convenience pointer to latest snapshot)

Snapshots are append-only by design. Downstream scripts (eval set, scoring)
read from arxiv_papers.csv for a stable path, but the dated snapshots are
the real data store. If you run the script twice in one day, the second run
saves to a timestamped file so nothing is lost.

Install requirements (one-time):
    py -3.14 -m pip install feedparser --user

Run:
    py -3.14 week1_arxiv_fetcher.py

Note: With 8 domains and a 3-second pause between API calls
(required by arXiv's usage guidelines), this script takes about
25-30 seconds to run. That's normal.
"""

import feedparser
import csv
import os
import re
import shutil
from datetime import datetime, timedelta, timezone
import urllib.parse
import time


# ---- CONFIGURATION ---------------------------------------------------------
# Dictionary mapping domain name -> list of arXiv categories
# You can add/remove categories anytime. Full taxonomy:
#   https://arxiv.org/category_taxonomy
#
# Notes on each choice:
#   AI:
#     cs.AI = Artificial Intelligence (broad)
#     cs.LG = Machine Learning
#     cs.CL = Computation and Language (LLMs, NLP)
#   Bio (pure biology):
#     q-bio.BM = Biomolecules (protein folding, drug discovery)
#     q-bio.GN = Genomics
#     q-bio.QM = Quantitative Methods (bio + ML crossover)
#   Health & Medicine:
#     q-bio.NC = Neurons and Cognition (BCIs, Alzheimer's, mental health)
#     q-bio.TO = Tissues and Organs
#     q-bio.PE = Populations and Evolution (epidemiology)
#     NOTE: For serious clinical/medical research we'll add medRxiv
#     in a later week. arXiv's medical coverage is thin.
#   Space:
#     astro-ph.EP = Earth and Planetary Astrophysics (exoplanets)
#     astro-ph.IM = Instrumentation and Methods
#     astro-ph.HE = High Energy Astrophysics (black holes, neutron stars)
#     astro-ph.SR = Solar and Stellar Astrophysics
#   Quantum:
#     quant-ph = Quantum Physics (computing, cryptography, sensing)
#   Robotics:
#     cs.RO = Robotics (autonomy, humanoids, manipulation)
#   Energy & Materials:
#     cond-mat.mtrl-sci = Materials Science (batteries, solar, catalysts)
#     cond-mat.supr-con = Superconductivity
#     physics.app-ph    = Applied Physics
#   Climate:
#     physics.ao-ph = Atmospheric and Oceanic Physics
DOMAINS = {
    "AI":       ["cs.AI", "cs.LG", "cs.CL"],
    "Bio":      ["q-bio.BM", "q-bio.GN", "q-bio.QM"],
    "Health":   ["q-bio.NC", "q-bio.TO", "q-bio.PE"],
    "Space":    ["astro-ph.EP", "astro-ph.IM", "astro-ph.HE", "astro-ph.SR"],
    "Quantum":  ["quant-ph"],
    "Robotics": ["cs.RO"],
    "Energy":   ["cond-mat.mtrl-sci", "cond-mat.supr-con", "physics.app-ph"],
    "Climate":  ["physics.ao-ph"],
}

# Reverse lookup built once at import time: arXiv category -> our domain name.
# Used by canonical_domain() to figure out which domain bucket a cross-listed
# paper actually belongs in (based on its primary arXiv category, with
# fall-through to secondaries if the primary isn't in any DOMAINS entry).
CATEGORY_TO_DOMAIN: dict[str, str] = {
    cat: domain for domain, cats in DOMAINS.items() for cat in cats
}

# How many papers to fetch per domain (so one domain can't dominate).
MAX_RESULTS_PER_DOMAIN = 30

# Filter to papers submitted in the last N days.
# Set to 7 (whole-week net) rather than 2 because arXiv has no weekend
# announcements: papers submitted Fri 2pm ET through Mon 2pm ET batch into
# Monday's 8pm ET announcement. A 2-day window run on Monday morning
# returns zero papers. 7 days guarantees coverage on any day of the week
# at ~3.5x the scoring cost vs. 2 days. Revisit if API spend pressures.
RECENCY_DAYS = 7

# Output: dated snapshots go in SNAPSHOT_DIR; LATEST_FILE is a convenience
# copy of the most recent run so downstream scripts have a stable path.
# The dated snapshot is the canonical record — LATEST_FILE is just a pointer.
SNAPSHOT_DIR = "snapshots"
LATEST_FILE = "arxiv_papers.csv"


# ---- FUNCTIONS -------------------------------------------------------------

def extract_arxiv_id(url):
    """
    Extract the canonical arXiv ID from an entry URL.

    arXiv URLs come in two shapes (per arxiv.org/help/arxiv_identifier):
      - Modern (April 2007+):   http://arxiv.org/abs/2604.18234v1   -> '2604.18234'
                                YYMM.NNNN (4-digit) through Dec 2014,
                                YYMM.NNNNN (5-digit) from Jan 2015 onward.
      - Legacy (pre-Apr 2007):  http://arxiv.org/abs/cs.AI/0501001v2 -> 'cs.AI/0501001'

    The version suffix (v1, v2...) is stripped — we want the canonical
    paper ID, not the version. The base ID is stable forever and joins
    cleanly to Semantic Scholar / OpenAlex / etc.

    Returns None if the URL doesn't match either pattern (defensive — we'd
    rather skip a paper than crash a 144-paper run on one weird URL).
    """
    # Modern format (April 2007+): YYMM.NNNN or YYMM.NNNNN, optionally vN.
    # arXiv's spec caps the suffix at 5 digits (post-Jan 2015). The lookahead
    # ensures we match the full suffix or fail — no silent partial matches.
    m = re.search(r'arxiv\.org/abs/(\d{4}\.\d{4,5})(?=v\d|\D|$)', url)
    if m:
        return m.group(1)
    # Legacy format: subject-class/digits, optionally followed by vN
    m = re.search(r'arxiv\.org/abs/([a-z\-]+(?:\.[A-Z]{2})?/\d+)(?:v\d+)?', url)
    if m:
        return m.group(1)
    return None


def build_arxiv_url(categories, max_results):
    """Builds the arXiv API URL for a given list of categories."""
    category_query = " OR ".join([f"cat:{c}" for c in categories])
    safe_query = urllib.parse.quote(category_query)
    url = (
        f"http://export.arxiv.org/api/query?"
        f"search_query={safe_query}"
        f"&sortBy=submittedDate"
        f"&sortOrder=descending"
        f"&max_results={max_results}"
    )
    return url


# Retry tuning for arXiv fetch. arXiv's stated guideline is one request per
# ~3 seconds for unauthenticated traffic; we use 5s between calls (see
# fetch_all_domains) and retry an empty result up to 2 times with a 5s wait
# in between. This costs ~10s per failed domain in the worst case and recovers
# transient rate-limit / partial-outage cases that previously dropped the
# whole domain silently. See charter 2026-05-19 / 2026-05-30 entries.
MAX_FETCH_RETRIES = 2
RETRY_BACKOFF_SECONDS = 5


def _diagnose_empty(feed) -> str:
    """Best-effort diagnosis when feedparser returns no entries.

    feedparser.parse() does NOT raise on HTTP error - it sets feed.status
    (HTTP code) and feed.bozo / feed.bozo_exception when the response is
    malformed. Without this, "no results" can mean any of:
      - arXiv legitimately returned 0 papers in the window
      - HTTP 429 (rate limit)
      - HTTP 503 (service unavailable)
      - DNS / TCP failure
      - Malformed XML
    Returns a short human-readable tag for logging.
    """
    status = getattr(feed, "status", None)
    bozo = getattr(feed, "bozo", 0)
    bozo_exc = getattr(feed, "bozo_exception", None)
    if status == 429:
        return "HTTP 429 rate-limited"
    if status == 503:
        return "HTTP 503 service unavailable"
    if status and status >= 400:
        return f"HTTP {status}"
    if bozo and bozo_exc is not None:
        return f"malformed response ({type(bozo_exc).__name__}: {bozo_exc})"
    if status == 200:
        return "HTTP 200, 0 entries (likely legitimate empty result)"
    return "no entries, no status (likely network failure)"


def fetch_papers_for_domain(domain_name, categories, max_results):
    """
    Fetches papers for a single domain and tags each with the domain name.
    Returns a list of paper dictionaries.

    Retries up to MAX_FETCH_RETRIES times if the response is empty,
    distinguishing legitimate empty results from rate-limits / outages.
    """
    print(f"  Fetching {domain_name}...", end=" ", flush=True)

    url = build_arxiv_url(categories, max_results)
    feed = None
    diag = None
    for attempt in range(MAX_FETCH_RETRIES + 1):
        feed = feedparser.parse(url)
        if feed.entries:
            break
        diag = _diagnose_empty(feed)
        # If it's a clean "HTTP 200, 0 entries" result, don't bother retrying:
        # arXiv really did say zero. Retries are for rate-limits / transient.
        if "likely legitimate empty result" in diag:
            break
        if attempt < MAX_FETCH_RETRIES:
            print(f"empty ({diag}); retry {attempt+1}/{MAX_FETCH_RETRIES} in {RETRY_BACKOFF_SECONDS}s...",
                  end=" ", flush=True)
            time.sleep(RETRY_BACKOFF_SECONDS)

    if not feed.entries:
        print(f"no results ({diag})")
        return []

    papers = []
    for entry in feed.entries:
        arxiv_id = extract_arxiv_id(entry.link)
        if arxiv_id is None:
            print(f"\n    skipping paper with unparseable URL: {entry.link}")
            continue
        paper = {
            "id": arxiv_id,          # canonical arXiv ID, stable across versions
            "domain": domain_name,   # <-- tag for filtering later (may be overridden in dedup_papers())
            "title": entry.title.replace("\n", " ").strip(),
            "authors": ", ".join(author.name for author in entry.authors),
            "published": entry.published,
            "abstract": entry.summary.replace("\n", " ").strip(),
            "url": entry.link,
            "categories": ", ".join(tag.term for tag in entry.tags),
        }
        papers.append(paper)

    print(f"got {len(papers)} papers")
    return papers


def canonical_domain(categories_str: str, fallback_domain: str) -> str:
    """
    Pick the canonical domain for a paper based on its arXiv `categories` field.

    Why this exists:
      An arXiv paper can be cross-listed in multiple categories (e.g. a paper
      with primary cs.RO and secondary cs.LG belongs to both Robotics and AI
      queries). Before this dedup pass, such a paper was being fetched twice
      and ended up in the corpus twice with different `domain` tags — causing
      duplicate rows in results_*.csv that masked as a scorer bug for weeks
      (see charter 2026-05-15 / 2026-05-16 entries).

    Rule:
      Walk the `categories` list in arXiv's published order. The FIRST
      category is the paper's primary classification per arXiv convention.
      Return the domain of the first category that appears in any DOMAINS
      entry. If none of the categories match a known domain (defensive — the
      paper got fetched, so SOMETHING in its categories must match), fall
      back to whichever domain originally fetched it.

    This means the assigned domain is determined by the paper's own primary
    classification, not by the accident of which domain query happened to
    return it first. A cs.RO-primary paper is always tagged Robotics, even
    if AI's cs.LG query also caught it.

    Args:
        categories_str: comma-separated arXiv categories ("cs.RO, cs.LG, ...")
        fallback_domain: the domain that originally fetched the paper; used
                         only if no category matches any DOMAINS entry

    Returns:
        Domain name from DOMAINS keys.
    """
    if not categories_str:
        return fallback_domain
    for cat in (c.strip() for c in categories_str.split(",")):
        if cat in CATEGORY_TO_DOMAIN:
            return CATEGORY_TO_DOMAIN[cat]
    return fallback_domain


def dedup_papers(papers: list[dict]) -> list[dict]:
    """
    Collapse duplicate arXiv IDs in the fetched paper list.

    A paper cross-listed in categories belonging to multiple DOMAINS entries
    gets fetched once per matching domain query. This function keeps one row
    per arXiv ID and reassigns its `domain` field via canonical_domain()
    based on the paper's actual category list.

    Order is preserved: the first occurrence of each ID stays in its
    original position in the list (predictable for downstream group-by /
    preview ordering).

    Returns a new list; does not mutate the input.
    """
    seen: set[str] = set()
    out: list[dict] = []
    collisions = 0
    for paper in papers:
        pid = paper.get("id")
        if not pid:
            # No ID extracted (already warned about during fetch); keep as-is
            # so we don't silently lose unparseable rows.
            out.append(paper)
            continue
        if pid in seen:
            collisions += 1
            continue
        seen.add(pid)
        # Reassign domain based on primary category. For papers that weren't
        # cross-listed (the vast majority), canonical_domain returns the same
        # value already in `domain` — no-op.
        chosen = canonical_domain(paper.get("categories", ""), paper["domain"])
        if chosen != paper["domain"]:
            # Don't mutate the caller's dict; copy then update.
            paper = {**paper, "domain": chosen}
        out.append(paper)
    if collisions:
        print(f"Deduplicated {collisions} cross-listed paper "
              f"{'copy' if collisions == 1 else 'copies'} "
              f"(kept {len(out)} unique).")
    return out


# Interval between domain fetches. arXiv asks for >=3s; we use 5s as a
# defensive margin since the previous 3s setting was correlating with
# silent rate-limit cascades (see charter 2026-05-30 entry).
INTER_DOMAIN_SLEEP_SECONDS = 5


def fetch_all_domains(domains, max_per_domain):
    """
    Loops through every domain and fetches papers for each one.
    Sleeps INTER_DOMAIN_SLEEP_SECONDS BEFORE each call (except the first) per
    arXiv's API guidelines.

    Sleeping BEFORE rather than AFTER matters: the previous arrangement let
    the FIRST request fire with no pacing, which is fine in isolation but
    bad if a prior fetch (manual run, parallel task) had recently hit the
    same IP. Pre-call sleep guarantees pacing even across script invocations
    that happen close in time.

    Cross-listed papers (returned by more than one domain query) are
    collapsed by dedup_papers() before return, so the result has exactly
    one row per arXiv ID with a canonical domain assignment.
    """
    print("Fetching papers across all domains...")
    all_papers = []
    for i, (domain_name, categories) in enumerate(domains.items()):
        if i > 0:
            time.sleep(INTER_DOMAIN_SLEEP_SECONDS)   # Be a good API citizen
        papers = fetch_papers_for_domain(domain_name, categories, max_per_domain)
        all_papers.extend(papers)
    print(f"Total fetched: {len(all_papers)} papers (pre-dedup)")
    all_papers = dedup_papers(all_papers)
    print(f"After dedup:   {len(all_papers)} unique papers\n")
    return all_papers


def filter_recent_papers(papers, days):
    """Keeps only papers submitted in the last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    recent = []
    for paper in papers:
        published_date = datetime.fromisoformat(
            paper["published"].replace("Z", "+00:00")
        )
        if published_date >= cutoff:
            recent.append(paper)
    print(f"Kept {len(recent)} papers from the last {days} days.\n")
    return recent


def save_to_csv(papers, snapshot_dir, latest_file):
    """
    Saves papers as a dated snapshot in snapshot_dir/arxiv_papers_YYYY-MM-DD.csv,
    and copies it to latest_file as a convenience pointer for downstream scripts.

    Dated snapshots are the canonical record — we never overwrite them.
    If today's snapshot already exists (e.g., you ran the script twice in one
    day), it's versioned with a timestamp suffix so nothing is lost.
    """
    if not papers:
        print("No papers to save.")
        return

    # Ensure the snapshot directory exists
    os.makedirs(snapshot_dir, exist_ok=True)

    # Build today's snapshot filename
    today = datetime.now().strftime("%Y-%m-%d")
    snapshot_path = os.path.join(snapshot_dir, f"arxiv_papers_{today}.csv")

    # If today's snapshot already exists, don't overwrite — add a time suffix.
    # This catches the "ran twice in one day" case without losing the first run.
    if os.path.exists(snapshot_path):
        timestamp = datetime.now().strftime("%H%M%S")
        snapshot_path = os.path.join(
            snapshot_dir, f"arxiv_papers_{today}_{timestamp}.csv"
        )
        print(f"Today's snapshot already exists — writing to {snapshot_path}")

    # Write the snapshot (the canonical record)
    fieldnames = papers[0].keys()
    with open(snapshot_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(papers)
    print(f"Saved {len(papers)} papers to '{snapshot_path}' (snapshot)")

    # Copy snapshot to the "latest" pointer for downstream scripts.
    # shutil.copy2 preserves metadata; overwriting this file is fine because
    # the real record lives in the snapshot directory.
    shutil.copy2(snapshot_path, latest_file)
    print(f"Updated '{latest_file}' (points to latest snapshot)")


def print_preview(papers):
    """Prints a preview grouped by domain so you can eyeball what you got."""
    print("\n--- Preview (top 2 per domain) ---\n")
    by_domain = {}
    for paper in papers:
        by_domain.setdefault(paper["domain"], []).append(paper)

    for domain, domain_papers in by_domain.items():
        print(f"=== {domain} ({len(domain_papers)} total) ===")
        for i, paper in enumerate(domain_papers[:2], start=1):
            print(f"  {i}. {paper['title']}")
            print(f"     {paper['url']}")
            print(f"     {paper['abstract'][:180]}...\n")


# ---- MAIN ------------------------------------------------------------------
if __name__ == "__main__":
    all_papers = fetch_all_domains(DOMAINS, MAX_RESULTS_PER_DOMAIN)
    recent_papers = filter_recent_papers(all_papers, RECENCY_DAYS)
    save_to_csv(recent_papers, SNAPSHOT_DIR, LATEST_FILE)
    print_preview(recent_papers)
