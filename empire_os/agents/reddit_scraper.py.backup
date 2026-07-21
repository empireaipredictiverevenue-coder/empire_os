#!/usr/bin/env python3
"""reddit_scraper.py — find buyer intent posts on Reddit via PullPush.io.

PullPush.io is a free archive of Reddit submissions (no API key, no auth).

Strategy:
  1. For each niche, search relevant subreddits
  2. Score posts by: buyer-intent keywords + recency + post quality
  3. Output ranked prospects with author + permalink
  4. Cache to /root/feedback/reddit_prospects.jsonl
"""
from __future__ import annotations
import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PULLPUSH_BASE = "https://api.pullpush.io/reddit/search/submission/"
USER_AGENT = "EmpireOS/1.0 (+https://empire-ai.co.uk)"

# Keywords that signal buyer intent
BUYER_KEYWORDS = {
    "high": ["looking for", "need a", "anyone know", "recommend", "recommendation",
             "hire", "hiring", "searching for", "find a", "wanted"],
    "med":  ["any good", "suggestions for", "who do you use", "best way to find",
             "looking to", "trying to find"],
}

# Subreddit map (lowercase, multiple per niche)
SUBREDDITS = {
    "roofing":       ["roofing", "roofers", "HomeImprovement"],
    "hvac":          ["hvac", "hvacadvice", "HomeImprovement"],
    "plumbing":      ["plumbing", "plumbingadvice", "HomeImprovement"],
    "solar":         ["solar", "RenewableEnergy"],
    "electrical":    ["electricians", "ElectricalEngineering"],
    "water_damage":  ["HomeImprovement"],
    "general":       ["Construction", "Contractor", "HomeImprovement", "DIY"],
}

CACHE_FILE = Path("/root/feedback/reddit_prospects.jsonl")


def _request(url: str, timeout: int = 30, max_retries: int = 3) -> dict | list:
    """PullPush-friendly request: 429 retries with exponential backoff."""
    for attempt in range(max_retries):
        req = Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except HTTPError as e:
            if e.code == 429:  # Too Many Requests
                wait = (attempt + 1) * 30  # 30s, 60s, 90s
                time.sleep(wait)
                continue
            return {"error": f"HTTP {e.code}: {e.read().decode()[:100]}"}
        except (URLError, json.JSONDecodeError) as e:
            return {"error": str(e)[:200]}
    return {"error": "max retries exceeded"}


def search_subreddit(
    subreddit: str,
    size: int = 50,
    sort: str = "desc",
    sort_type: str = "score",  # default to score (popular posts have more buyer intent)
    query: str | None = None,
    after_utc: int | None = None,
) -> list[dict[str, Any]]:
    """Fetch posts from a subreddit via PullPush.

    after_utc: only posts created after this epoch second (filter for recency).
    """
    params = [f"subreddit={subreddit}", f"size={size}",
              f"sort={sort}", f"sort_type={sort_type}"]
    if query: params.append(f"title={query}")
    if after_utc: params.append(f"after={after_utc}")
    url = PULLPUSH_BASE + "?" + "&".join(params)
    result = _request(url)
    if isinstance(result, dict):
        if "error" in result:
            return []
        return result.get("data", [])
    return result if isinstance(result, list) else []


def score_intent(title: str, selftext: str) -> tuple[int, str | None]:
    """Return (intent_score, matched_keyword). Higher = better."""
    text = (title + " " + (selftext or "")).lower()
    for kw in BUYER_KEYWORDS["high"]:
        if kw in text:
            return 10, kw
    for kw in BUYER_KEYWORDS["med"]:
        if kw in text:
            return 5, kw
    return 0, None


def find_prospects(
    niches: list[str],
    days_back: int = 30,
    min_intent: int = 5,
    max_per_sub: int = 50,
) -> list[dict[str, Any]]:
    """Find prospects across niches. Returns scored list."""
    after_utc = int(time.time()) - (days_back * 86400)
    seen_ids = set()
    results = []

    for niche in niches:
        subs = SUBREDDITS.get(niche, ["HomeImprovement"])
        for sub in subs:
            posts = search_subreddit(sub, size=max_per_sub, after_utc=after_utc)
            for post in posts:
                pid = post.get("id", "")
                if not pid or pid in seen_ids:
                    continue
                title = post.get("title", "")
                selftext = post.get("selftext", "")
                score, kw = score_intent(title, selftext)
                if score < min_intent:
                    continue
                seen_ids.add(pid)
                results.append({
                    "niche": niche,
                    "subreddit": sub,
                    "post_id": pid,
                    "title": title,
                    "selftext_preview": (selftext or "")[:300],
                    "author": post.get("author", ""),
                    "score": post.get("score", 0),
                    "num_comments": post.get("num_comments", 0),
                    "permalink": post.get("permalink", ""),
                    "url": "https://reddit.com" + post.get("permalink", ""),
                    "created_utc": post.get("created_utc", 0),
                    "intent_score": score,
                    "intent_keyword": kw,
                })
            time.sleep(5)  # PullPush rate limit: be polite
    # Sort: intent desc, then score desc, then comments desc
    results.sort(key=lambda p: (p["intent_score"], p["score"], p["num_comments"]), reverse=True)
    return results


def save_prospects(prospects: list[dict]) -> int:
    """Append to /root/feedback/reddit_prospects.jsonl, returns count appended."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing = set()
    if CACHE_FILE.exists():
        for line in CACHE_FILE.read_text().splitlines():
            try:
                existing.add(json.loads(line).get("post_id"))
            except Exception:
                pass
    appended = 0
    with open(CACHE_FILE, "a") as f:
        for p in prospects:
            if p["post_id"] not in existing:
                f.write(json.dumps(p) + "\n")
                existing.add(p["post_id"])
                appended += 1
    return appended


def main():
    import sys
    niches = sys.argv[1:] if len(sys.argv) > 1 else ["roofing", "hvac", "plumbing"]
    print(f"Searching {niches} (last 30 days)...")
    prospects = find_prospects(niches, days_back=30, min_intent=5)
    print(f"Found {len(prospects)} buyer-intent posts")
    for p in prospects[:10]:
        print(f"  [{p['intent_score']}] r/{p['subreddit']} | score={p['score']} | {p['title'][:60]}")
        print(f"    author: {p['author']} | kw='{p['intent_keyword']}' | {p['url']}")
    saved = save_prospects(prospects)
    print(f"Appended {saved} new prospects to {CACHE_FILE}")


if __name__ == "__main__":
    main()
