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


def fetch_papers_for_domain(domain_name, categories, max_results):
    """
    Fetches papers for a single domain and tags each with the domain name.
    Returns a list of paper dictionaries.
    """
    print(f"  Fetching {domain_name}...", end=" ", flush=True)

    url = build_arxiv_url(categories, max_results)
    feed = feedparser.parse(url)

    if not feed.entries:
        print("no results (check internet connection)")
        return []

    papers = []
    for entry in feed.entries:
        arxiv_id = extract_arxiv_id(entry.link)
        if arxiv_id is None:
            print(f"\n    skipping paper with unparseable URL: {entry.link}")
            continue
        paper = {
            "id": arxiv_id,          # canonical arXiv ID, stable across versions
            "domain": domain_name,   # <-- tag for filtering later
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


def fetch_all_domains(domains, max_per_domain):
    """
    Loops through every domain and fetches papers for each one.
    Sleeps 3 seconds between calls per arXiv's API guidelines.
    """
    print("Fetching papers across all domains...")
    all_papers = []
    for domain_name, categories in domains.items():
        papers = fetch_papers_for_domain(domain_name, categories, max_per_domain)
        all_papers.extend(papers)
        time.sleep(3)   # Be a good API citizen
    print(f"Total fetched: {len(all_papers)} papers\n")
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