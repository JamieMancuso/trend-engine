"""
Week 7 Macro/Political RSS Fetcher
-----------------------------------
Companion to week7_news_fetcher.py (HN). Pulls macro and political news from
RSS feeds — the source class HN doesn't carry. Sized to feed the v0.2 news
rubric's market_impact axis with the kind of stories operator was missing.

SOURCES (revised 2026-05-11 after first run discovered dead URLs):
  - NPR Top News + Politics       — wire-service quality replacement for Reuters/AP
  - Reuters via Google News RSS   — workaround since Reuters retired direct RSS
  - Federal Reserve press + speeches — primary source for Fed policy

ORIGINAL SOURCES THAT FAILED:
  - feeds.reuters.com/* — Reuters retired their public RSS system years ago.
    Subdomain no longer resolves. Substituted via Google News RSS query.
  - feeds.apnews.com/* — AP restructured RSS; subdomain unreachable.
    Substituted with NPR which has comparable wire-service quality.

DESIGN MIRRORS week7_news_fetcher.py:
  - 48h recency window (matches research-layer cadence)
  - Same OUTPUT_COLUMNS so week7_news_scoring.py runs unchanged on this output
  - ID namespaced as <source>:<guid_hash> to prevent collision with HN IDs
  - No popularity score in RSS (vs. HN's score) — those columns are blank

NOT IN THIS VERSION:
  - URL canonicalization / cross-source dedup (deferred per scoping doc;
    revisit when the same Reuters story shows up via 3 syndications).
  - Full-article fetch / readability extraction (scoring runs on title +
    summary; if Haiku needs more context for some sources we'd add it later).
  - HTTP caching with ETag/Last-Modified (RSS feeds support it; small win).

RUN:
    py -3.14 -m pip install feedparser --user        # one-time
    py -3.14 week7_news_fetcher_rss.py
    py -3.14 week7_news_fetcher_rss.py --recency-hours 24
    py -3.14 week7_news_fetcher_rss.py --sources reuters,fed   # subset
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser


# ---- CONFIG -----------------------------------------------------------------
# RSS feed URLs. Keep this dict the source of truth; --sources filters by key.
# If a feed URL changes, update here. If a 404 starts happening, the per-feed
# error handler skips that feed without taking down the whole run.
FEEDS: dict[str, list[tuple[str, str]]] = {
    # source_key -> list of (label, url)
    "npr": [
        # NPR's RSS lives at feeds.npr.org with numeric topic codes.
        # 1001 = Top Stories, 1014 = Politics. Active and reliable.
        ("NPR Top Stories", "https://feeds.npr.org/1001/rss.xml"),
        ("NPR Politics",    "https://feeds.npr.org/1014/rss.xml"),
    ],
    "reuters_via_google": [
        # Reuters retired direct RSS. Google News RSS lets us proxy a query.
        # Two queries: general world/business + politics-flavored. Google
        # serves these as Atom but feedparser handles both transparently.
        ("Reuters via Google (Top)",
         "https://news.google.com/rss/search?q=site:reuters.com&hl=en-US&gl=US&ceid=US:en"),
        ("Reuters via Google (Politics)",
         "https://news.google.com/rss/search?q=site:reuters.com+politics+OR+economy+OR+fed&hl=en-US&gl=US&ceid=US:en"),
    ],
    "fed": [
        ("Fed Press Releases", "https://www.federalreserve.gov/feeds/press_all.xml"),
        ("Fed Speeches",       "https://www.federalreserve.gov/feeds/speeches.xml"),
    ],
}

# Per-source recency override. Fed releases are low-volume (1-3/week) so a
# tight 48h window catches almost nothing on most days. Wire services post
# constantly, so 48h is plenty there.
SOURCE_RECENCY_HOURS: dict[str, int] = {
    "fed": 168,   # 7 days — catches every Fed release without flooding
}

DEFAULT_RECENCY_HOURS = 48
HTTP_TIMEOUT = 15

# Same OUTPUT_COLUMNS as the HN fetcher so the scorer is source-agnostic.
# RSS-only fields go into hn_score / hn_comments slots: blank (RSS has no
# popularity metric). Keeping the column name `hn_score` is mildly ugly but
# avoids a schema fork; we can rename at v0.3 if it bothers us.
OUTPUT_COLUMNS = [
    "id", "source", "title", "url", "author",
    "posted_at", "hn_score", "hn_comments", "fetched_at",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch macro/political RSS feeds to CSV.")
    p.add_argument("--recency-hours", type=int, default=DEFAULT_RECENCY_HOURS,
                   help=f"Drop items older than this. Default {DEFAULT_RECENCY_HOURS}h.")
    p.add_argument("--sources", default=None,
                   help=f"Comma-separated subset of {list(FEEDS.keys())}. Default: all.")
    p.add_argument("--output", default=None,
                   help="Output CSV. Default: news_rss_YYYY-MM-DD_HHMMSS.csv.")
    return p.parse_args()


def parse_published(entry) -> datetime | None:
    """
    Try to extract a published datetime from a feedparser entry.
    feedparser normalizes most date variants into entry.published_parsed
    (a time.struct_time). Falls back to updated_parsed if published is missing.
    Returns timezone-aware UTC datetime, or None if unparseable.
    """
    for key in ("published_parsed", "updated_parsed"):
        t = getattr(entry, key, None) or entry.get(key)
        if t:
            try:
                return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)
            except (TypeError, ValueError, OverflowError):
                continue
    return None


def clean_html(text: str) -> str:
    """Strip HTML tags from RSS summary fields. Naive but adequate for headlines."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def make_id(source_key: str, entry) -> str:
    """
    Stable ID for a feed entry. RSS guid is preferred but inconsistent across
    feeds; falling back to URL hash. Hashing keeps IDs short and predictable.
    """
    raw = entry.get("id") or entry.get("guid") or entry.get("link") or entry.get("title", "")
    h = hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]
    return f"{source_key}:{h}"


def fetch_feed(label: str, url: str) -> list[dict]:
    """Fetch + parse one feed. Returns list of raw entry dicts (not yet filtered)."""
    parsed = feedparser.parse(url, request_headers={
        "User-Agent": "trend-engine-rss-fetcher/0.1",
    })
    # feedparser returns parsed.bozo=1 for malformed feeds but usually still
    # has usable entries. We surface the error but don't abort.
    if getattr(parsed, "bozo", 0):
        err = getattr(parsed, "bozo_exception", "unknown")
        # Common: HTTP 200 with mild XML quirks. Not worth aborting unless
        # the entries list is empty.
        if not parsed.entries:
            print(f"    {label}: feed error ({err}); 0 entries", file=sys.stderr)
            return []
        else:
            print(f"    {label}: warning ({type(err).__name__}); proceeding with {len(parsed.entries)} entries",
                  file=sys.stderr)
    return parsed.entries


def normalize_entry(source_key: str, label: str, entry, fetched_at: datetime) -> dict | None:
    """Convert a feedparser entry into our OUTPUT_COLUMNS shape. None if unsalvageable."""
    title = (entry.get("title") or "").strip()
    url   = (entry.get("link") or "").strip()
    if not title or not url:
        return None
    posted = parse_published(entry)
    posted_iso = posted.isoformat(timespec="seconds") if posted else ""
    author = entry.get("author", "") or label   # fallback to feed label
    return {
        "id":          make_id(source_key, entry),
        "source":      source_key,             # short key for downstream filtering
        "title":       title,
        "url":         url,
        "author":      author,
        "posted_at":   posted_iso,
        "hn_score":    "",                     # not applicable to RSS
        "hn_comments": "",                     # not applicable to RSS
        "fetched_at":  fetched_at.isoformat(timespec="seconds"),
    }


def is_keepable(item: dict, posted: datetime | None, cutoff: datetime) -> tuple[bool, str]:
    """Filter out items older than cutoff. Items with no parseable date are kept
    (better to over-include than to silently drop a fresh story with bad metadata)."""
    if posted is None:
        return True, "no date (kept)"
    if posted < cutoff:
        age_h = (datetime.now(tz=timezone.utc) - posted).total_seconds() / 3600
        return False, f"too old ({age_h:.1f}h)"
    return True, "ok"


def main() -> int:
    args = parse_args()

    if args.output is None:
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        args.output = f"news_rss_{stamp}.csv"

    selected_sources = (
        [s.strip() for s in args.sources.split(",")] if args.sources else list(FEEDS.keys())
    )
    unknown = [s for s in selected_sources if s not in FEEDS]
    if unknown:
        print(f"ERROR: unknown source(s): {unknown}. Available: {list(FEEDS.keys())}", file=sys.stderr)
        return 2

    fetched_at = datetime.now(tz=timezone.utc)
    now = fetched_at

    print(f"Fetching RSS sources: {selected_sources}  (default recency<{args.recency_hours}h)")
    for src in selected_sources:
        if src in SOURCE_RECENCY_HOURS:
            print(f"  per-source override: {src} = {SOURCE_RECENCY_HOURS[src]}h")

    kept: list[dict] = []
    skipped = 0
    seen_ids: set[str] = set()   # in-run dedup; cross-run dedup is the scorer's job

    for src_key in selected_sources:
        # Per-source recency cutoff — Fed gets a wider window than wire services.
        src_hours = SOURCE_RECENCY_HOURS.get(src_key, args.recency_hours)
        cutoff = now - timedelta(hours=src_hours)
        for label, url in FEEDS[src_key]:
            print(f"  [{src_key}] {label}")
            try:
                entries = fetch_feed(label, url)
            except Exception as e:
                print(f"    fetch failed: {e}", file=sys.stderr)
                continue
            for entry in entries:
                norm = normalize_entry(src_key, label, entry, fetched_at)
                if norm is None:
                    continue
                if norm["id"] in seen_ids:
                    continue   # same item appearing in two feeds of the same source
                posted = parse_published(entry)
                keep, reason = is_keepable(norm, posted, cutoff)
                if not keep:
                    skipped += 1
                    continue
                seen_ids.add(norm["id"])
                kept.append(norm)
            print(f"    fetched {len(entries)}, total kept so far: {len(kept)}")

    print(f"\n{len(kept)} kept, {skipped} skipped (too old)")

    if not kept:
        print("Nothing to write.")
        return 0

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        w.writeheader()
        for row in kept:
            w.writerow(row)

    print(f"Wrote {len(kept)} items to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
