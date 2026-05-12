"""
Week 7 News Fetcher — Hacker News top stories → CSV
----------------------------------------------------
First source for the news layer (per week6_news_layer_scoping.md). Pulls the
top N stories from the HN API, filters to fresh + linkable items, and writes
to a dated CSV for downstream scoring by week7_news_scoring.py.

DESIGN NOTES:
- HN API has no auth, no rate limit in practice, but each item is a separate
  HTTP call. ~30-60 items × 1 call each = a few seconds wall time.
- We filter:
    - type == 'story'             (drop comments, jobs, polls)
    - has 'url' field             (drop Ask-HN self-posts; we want external links)
    - score >= MIN_SCORE          (drop dead-on-arrival posts)
    - posted within RECENCY_HOURS (avoid re-fetching old items)
- We do NOT scrape article bodies here. Scoring runs on title + url + author +
  HN score. If we want full-text scoring later, that's a separate enrichment pass
  (Newspaper3k / readability) so the fetcher stays simple and stateless.

OUTPUT SCHEMA (matches what week7_news_scoring.py expects):
    id, source, title, url, author, posted_at, hn_score, hn_comments,
    fetched_at

RUN:
    py -3.14 week7_news_fetcher.py                          # default top 30
    py -3.14 week7_news_fetcher.py --top 50                 # wider net
    py -3.14 week7_news_fetcher.py --recency-hours 48       # match scorer cadence
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


# ---- CONFIG -----------------------------------------------------------------
HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"

DEFAULT_TOP_N = 30           # how many top stories to consider
DEFAULT_RECENCY_HOURS = 48   # match research-layer 2-day cadence
DEFAULT_MIN_SCORE = 20       # filter dead posts; HN front page is ~50+
HTTP_TIMEOUT = 10            # seconds per item fetch
HTTP_RETRY = 2               # retry once on transient failure

OUTPUT_COLUMNS = [
    "id", "source", "title", "url", "author",
    "posted_at", "hn_score", "hn_comments", "fetched_at",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch top Hacker News stories to CSV.")
    p.add_argument("--top", type=int, default=DEFAULT_TOP_N,
                   help=f"How many top stories to consider. Default {DEFAULT_TOP_N}.")
    p.add_argument("--recency-hours", type=int, default=DEFAULT_RECENCY_HOURS,
                   help=f"Drop items older than this. Default {DEFAULT_RECENCY_HOURS}h.")
    p.add_argument("--min-score", type=int, default=DEFAULT_MIN_SCORE,
                   help=f"Drop items below this HN score. Default {DEFAULT_MIN_SCORE}.")
    p.add_argument("--output", default=None,
                   help="Output CSV path. Default: news_hn_YYYY-MM-DD_HHMMSS.csv.")
    return p.parse_args()


def http_get_json(url: str) -> dict | list:
    """GET a URL and parse the JSON response. Retries once on network error."""
    last_err: Exception | None = None
    for attempt in range(HTTP_RETRY + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "trend-engine-news-fetcher/0.1"},
            )
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
            last_err = e
            if attempt < HTTP_RETRY:
                time.sleep(1.5 ** attempt)
    raise last_err  # type: ignore[misc]


def fetch_top_story_ids(n: int) -> list[int]:
    """Return the first n IDs from /topstories.json."""
    data = http_get_json(HN_TOP_URL)
    if not isinstance(data, list):
        raise ValueError(f"Expected list from topstories.json, got {type(data)}")
    return data[:n]


def fetch_item(item_id: int) -> dict | None:
    """Fetch a single HN item. Returns None if the API returns null (deleted item)."""
    data = http_get_json(HN_ITEM_URL.format(id=item_id))
    if data is None or not isinstance(data, dict):
        return None
    return data


def normalize_item(item: dict) -> dict:
    """Flatten an HN item dict into our OUTPUT_COLUMNS shape."""
    posted = datetime.fromtimestamp(item.get("time", 0), tz=timezone.utc)
    return {
        "id":          f"hn:{item['id']}",   # namespace prefix so news/research IDs never collide
        "source":      "hackernews",
        "title":       item.get("title", "").strip(),
        "url":         item.get("url", "").strip(),
        "author":      item.get("by", ""),
        "posted_at":   posted.isoformat(timespec="seconds"),
        "hn_score":    item.get("score", 0),
        "hn_comments": item.get("descendants", 0),
        "fetched_at":  datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
    }


def is_keepable(item: dict, recency_cutoff: datetime, min_score: int) -> tuple[bool, str]:
    """Return (keep, reason) for a single fetched HN item."""
    if item.get("type") != "story":
        return False, f"type={item.get('type')}"
    if not item.get("url"):
        return False, "no url (self-post)"
    if item.get("score", 0) < min_score:
        return False, f"score={item.get('score')} < {min_score}"
    posted = datetime.fromtimestamp(item.get("time", 0), tz=timezone.utc)
    if posted < recency_cutoff:
        age_h = (datetime.now(tz=timezone.utc) - posted).total_seconds() / 3600
        return False, f"too old ({age_h:.1f}h)"
    return True, "ok"


def main() -> int:
    args = parse_args()

    if args.output is None:
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        args.output = f"news_hn_{stamp}.csv"

    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=args.recency_hours)
    print(f"Fetching top {args.top} HN stories (recency<{args.recency_hours}h, score>={args.min_score})...")

    try:
        ids = fetch_top_story_ids(args.top)
    except Exception as e:
        print(f"ERROR fetching top stories: {e}", file=sys.stderr)
        return 1

    kept: list[dict] = []
    skipped = 0
    for i, item_id in enumerate(ids, start=1):
        try:
            raw = fetch_item(item_id)
        except Exception as e:
            print(f"  [{i:>3}/{len(ids)}] #{item_id} fetch failed: {e}", file=sys.stderr)
            continue
        if raw is None:
            print(f"  [{i:>3}/{len(ids)}] #{item_id} (deleted)")
            continue
        keep, reason = is_keepable(raw, cutoff, args.min_score)
        if not keep:
            skipped += 1
            title_preview = (raw.get("title") or "")[:50]
            print(f"  [{i:>3}/{len(ids)}] skip ({reason:<22}) {title_preview}")
            continue
        kept.append(normalize_item(raw))
        print(f"  [{i:>3}/{len(ids)}] keep score={raw.get('score',0):>4} {raw['title'][:60]}")

    print(f"\n{len(kept)} kept, {skipped} skipped, {len(ids) - len(kept) - skipped} other (deleted/error)")

    if not kept:
        print("Nothing to write.")
        return 0

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        w.writeheader()
        for row in kept:
            w.writerow(row)

    print(f"Wrote {len(kept)} stories to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
