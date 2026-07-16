"""Reddit JSON source — REAL (zero auth, public).

Tier: real (works without OAuth)

Reddit exposes JSON via .json suffix on any URL. Free, no auth.
Search: https://www.reddit.com/search.json?q=need+plumber+nyc
Subs:   https://www.reddit.com/r/HomeImprovement/new.json

We hit the public JSON endpoint with a User-Agent header (Reddit
blocks unidentified bots). Free, but limited to ~10 req/min unauth.

Target subs: r/HomeImprovement, r/Plumbing, r/HVAC, r/DIY
Plus city subs: r/nyc, r/LosAngeles, r/chicago, r/Dallas, etc.

Each request post = explicit "need help with X" = ready-to-buy lead.
"""
import re
import time
import requests
from typing import Iterator
from pathlib import Path

from empire_os.lead_sources import LeadCandidate, SourceInfo


UA = "Mozilla/5.0 (EmpireOS-Crawler/1.0; +https://empire-ai.co.uk/bot)"

# Niche + city search patterns
SEARCHES = [
    # (query, metro, niche)
    ("need plumber NYC", "NYC", "plumbing"),
    ("need plumber new york", "NYC", "plumbing"),
    ("plumbing emergency NYC", "NYC", "emergency_plumbing"),
    ("roof repair NYC", "NYC", "roofing"),
    ("AC broke NYC", "NYC", "hvac"),
    ("need electrician NYC", "NYC", "electrical"),
    ("need plumber LA", "LAX", "plumbing"),
    ("roof repair Los Angeles", "LAX", "roofing"),
    ("AC repair LA", "LAX", "hvac"),
    ("need plumber Chicago", "CHI", "plumbing"),
    ("roof repair Chicago", "CHI", "roofing"),
    ("furnace broken Chicago", "CHI", "hvac"),
    ("need plumber Dallas", "DFW", "plumbing"),
    ("AC repair Dallas", "DFW", "hvac"),
    ("roof repair DC", "WDC", "roofing"),
    ("plumber Boston", "BOS", "plumbing"),
    ("need plumber Seattle", "SEA", "plumbing"),
    ("AC repair Phoenix", "PHX", "hvac"),
    ("roof repair Atlanta", "ATL", "roofing"),
]

EXCLUDE_FLAIRS = ["[Question]", "[Meta]", "[Discussion]"]


def _read_token() -> str:
    env_path = Path("/root/empire_os/.env")
    try:
        with open(env_path) as f:
            for line in f:
                if line.startswith("REDDIT_CLIENT_ID="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


def _scrape_post(url: str) -> str:
    """Get the JSON for a post URL (used to fetch comments and OP profile)."""
    try:
        r = requests.get(url + ".json", headers={"User-Agent": UA}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) > 0:
                post = data[0]["data"]["children"][0]["data"]
                author = post.get("author", "")
                title = post.get("title", "")
                selftext = (post.get("selftext", "") or "")[:300]
                return f"{title}\n{selftext}\n(OP: u/{author})"
        return ""
    except Exception:
        return ""


def run(metro: str = None) -> Iterator[LeadCandidate]:
    for query, m, niche in SEARCHES:
        if metro and metro != m:
            continue

        try:
            # Use old.reddit.com for stable search
            r = requests.get(
                "https://old.reddit.com/search.json",
                params={"q": query, "sort": "new", "limit": 5,
                       "restrict_sr": "off", "t": "week"},
                headers={"User-Agent": UA},
                timeout=15,
            )
            if r.status_code != 200:
                continue
            data = r.json()
        except Exception:
            continue

        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            if not post:
                continue

            # Skip if non-recent
            title = post.get("title", "") or ""
            selftext = post.get("selftext", "") or ""
            text = (title + " " + selftext).lower()
            if any(flair.strip("[]").lower() in text for flair in EXCLUDE_FLAIRS):
                continue

            author = post.get("author", "") or "[deleted]"
            permalink = "https://old.reddit.com" + post.get("permalink", "")
            ts = post.get("created_utc", 0)

            # Skip bot, deleted, or auto-mod
            if author in ("[deleted]", "AutoModerator", "") or author.endswith("-bot"):
                continue

            scrape = _scrape_post(permalink.split("?")[0])

            yield LeadCandidate(
                name=f"u/{author} ({m})",
                phone="",
                niche=niche,
                metro=m,
                state="",
                details=f"Reddit post: {title[:100]}. {scrape[:200]}",
                source="reddit_json",
                lead_score=70,
                url=permalink,
                raw=post,
            )

        time.sleep(2)  # be polite to reddit


def register_source(reg):
    reg(SourceInfo(
        name="reddit",
        tier="real",
        requires=[],  # works without OAuth
        description="Reddit JSON — /r/HomeImprovement, /r/HVAC, city subs, free",
        run_fn=run,
    ))
