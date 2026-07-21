#!/usr/bin/env python3
"""reddit_scraper.py — find buyer intent posts on Reddit via PullPush.io.

PullPush.io is a free archive of Reddit submissions (no API key, no auth).

Strategy:
  1. For each niche, search relevant subreddits
  2. Score posts by: buyer-intent keywords + recency + post quality
  3. CORTEX BOOST: score each post via omega_os.qualify_prospect (8-dim score)
  4. Output ranked prospects with author + permalink + omega + grade
  5. Cache to /root/feedback/reddit_prospects.jsonl
"""
from __future__ import annotations
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Cortex Omega integration (graceful fallback if not importable)
try:
    sys.path.insert(0, "/root/empire_os")
    from empire_os import omega_os
    _HAS_OMEGA = True
except Exception:
    omega_os = None
    _HAS_OMEGA = False


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


def _grade_for(omega: float) -> str:
    """omega is 0-1 (total/100). Map to A/B/C/D — matches eval_product.grade_for."""
    if omega >= 0.75:
        return "A"
    if omega >= 0.55:
        return "B"
    if omega >= 0.35:
        return "C"
    return "D"


def _score_with_omega(post: dict, niche: str) -> dict:
    """CORTEX BOOST: run omega_os on the post content.

    Returns {"omega": float|None, "grade": str|None, "tier": str|None,
             "total_score": int|None} — all None if omega unavailable.
    Falls back gracefully on any exception so the scraper never breaks.
    """
    if not _HAS_OMEGA or omega_os is None:
        return {"omega": None, "grade": None, "tier": None, "total_score": None}
    try:
        # Build a prospect dict from the Reddit post for Omega
        details = (post.get("selftext") or post.get("title") or "").strip()
        res = omega_os.qualify_prospect(  # type: ignore[union-attr]
            backend=None,
            prospect_id=f"reddit_{post.get('id', int(time.time()))}",
            tort_key=niche,  # use niche as tort_key proxy
            details=details,
            source=f"reddit_{post.get('subreddit', 'unknown')}",
            name=post.get("author", ""),
            phone="",
            zip_code="",
        )
        total = float(res.get("total", 0.0))
        omega = round(total / 100.0, 4)
        return {
            "omega": omega,
            "grade": _grade_for(omega),
            "tier": res.get("tier", ""),
            "total_score": int(total),
        }
    except Exception:
        return {"omega": None, "grade": None, "tier": None, "total_score": None}


def find_prospects(
    niches: list[str],
    days_back: int = 30,
    min_intent: int = 5,
    max_per_sub: int = 50,
    min_grade: str | None = None,
) -> list[dict[str, Any]]:
    """Find prospects across niches. Returns scored list.

    min_grade: drop prospects below this letter ('A'/'B'/'C'/'D').
      - None (default): keep everything, sort by intent
      - 'D' or lower: drop only junk (omega < 0.35)
      - 'C': drop D-grade (recommended for outreach — keeps A/B/C)
      - 'B': drop C/D (premium only)
    """
    _GRADE_RANK = {"A": 4, "B": 3, "C": 2, "D": 1}
    rank_cutoff = _GRADE_RANK.get(min_grade, 0) if min_grade else 0
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
                result = {
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
                }
                # CORTEX BOOST: add omega + grade if available
                omega_data = _score_with_omega(post, niche)
                result.update(omega_data)
                # Grade filter (only applies when cortex scored the post)
                if rank_cutoff and result.get("grade"):
                    if _GRADE_RANK.get(result["grade"], 0) < rank_cutoff:
                        continue
                results.append(result)
            time.sleep(5)  # PullPush rate limit: be polite
    # Sort: intent desc, then omega desc (preferring A/B/C), then score desc
    results.sort(
        key=lambda p: (
            p["intent_score"],
            p.get("omega") or 0.0,
            p["score"],
            p["num_comments"],
        ),
        reverse=True,
    )
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


def write_to_eval_ledger(prospects: list[dict]) -> int:
    """Push A/B/C-grade prospects into evaluation_ledger so they're billable.

    Each row creates an 'awaiting_buyer' evaluation record tied to the
    post's niche. When a buyer later submits an API key claiming this
    prospect, record_conversion() charges $2.50.

    Returns count written.
    """
    import sqlite3, time as _time
    billable = [p for p in prospects if p.get("grade") in ("A", "B", "C")]
    if not billable:
        return 0
    db = "/root/empire_os/empire_os.db"
    try:
        c = sqlite3.connect(db, timeout=30)
    except Exception:
        return 0
    try:
        # ensure schema (eval product manages its own; rely on it)
        c.execute(
            """CREATE TABLE IF NOT EXISTS evaluation_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                buyer TEXT,
                lead_ref TEXT,
                niche TEXT,
                omega REAL,
                grade TEXT,
                price_usd REAL,
                billing TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT
            )"""
        )
        c.commit()
        now = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())
        rows = [
            (
                "",  # buyer filled when claimed
                f"reddit_{p['post_id']}",
                p.get("niche", "unknown"),
                p.get("omega", 0.0),
                p.get("grade", ""),
                0.0,  # outcome mode: 0 until conversion
                "outcome",
                "awaiting_buyer",
                now,
            )
            for p in billable
        ]
        # INSERT OR IGNORE on lead_ref avoids duplicates if rerun
        c.executemany(
            "INSERT OR IGNORE INTO evaluation_ledger "
            "(buyer, lead_ref, niche, omega, grade, price_usd, billing, status, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            rows,
        )
        c.commit()
        return len(rows)
    except Exception:
        return 0
    finally:
        c.close()


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Reddit buyer-intent scraper (cortex-boosted)")
    ap.add_argument("niches", nargs="*", default=["roofing", "hvac", "plumbing"])
    ap.add_argument("--days-back", type=int, default=30)
    ap.add_argument("--min-intent", type=int, default=5)
    ap.add_argument("--min-grade", choices=["A", "B", "C", "D"], default=None,
                    help="Drop prospects below this grade (e.g. 'C' drops D junk)")
    ap.add_argument("--to-ledger", action="store_true",
                    help="Also push A/B/C prospects into evaluation_ledger (billable on claim)")
    ap.add_argument("--test-run", action="store_true", help="Don't save anything")
    args = ap.parse_args()

    print(f"Searching {args.niches} (last {args.days_back}d, min_intent={args.min_intent}, min_grade={args.min_grade})...", flush=True)
    prospects = find_prospects(
        args.niches, days_back=args.days_back,
        min_intent=args.min_intent, min_grade=args.min_grade,
    )
    print(f"Found {len(prospects)} buyer-intent posts", flush=True)
    for p in prospects[:10]:
        omega_str = f"ω={p.get('omega', 0):.2f}/{p.get('grade', '-')}" if p.get('omega') is not None else "ω=N/A"
        print(f"  [{p['intent_score']}] r/{p['subreddit']} | {omega_str} | score={p['score']} | {p['title'][:60]}", flush=True)
        print(f"    author: {p['author']} | kw='{p['intent_keyword']}' | {p['url']}", flush=True)
    if args.test_run:
        return
    saved = save_prospects(prospects)
    print(f"Appended {saved} new prospects to {CACHE_FILE}", flush=True)
    if args.to_ledger:
        ledged = write_to_eval_ledger(prospects)
        print(f"Pushed {ledged} billable (A/B/C) prospects to evaluation_ledger", flush=True)


if __name__ == "__main__":
    main()
