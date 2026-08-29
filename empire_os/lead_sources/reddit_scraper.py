"""Self-hosted Reddit scraper — no API key, Playwright-based."""

from __future__ import annotations
from typing import Iterator, Optional
from empire_os.lead_sources.models import LeadCandidate
from empire_os.lead_sources import register

import sys
sys.path.insert(0, '/root/empire_os')
from sources.reddit_scraper import RedditScraper

SUBREDDITS = {
    "roofing": ["roofing", "roofingjobs", "contractor"],
    "hvac": ["hvac", "hvactech", "hvacjobs"],
    "plumbing": ["plumbing", "plumbers", "plumbingjobs"],
    "electrical": ["electricians", "electrical", "electrician"],
    "solar": ["solar", "solarinstallers", "solarpower"],
    "general_contractor": ["contractors", "construction", "remodeling"],
    "landscaping": ["landscaping", "lawncare", "hardscaping"],
    "fence": ["fencing", "fence"],
    "pool": ["pools", "poolconstruction"],
    "concrete": ["concrete", "concretework"],
}

def run(metro: str = None, verticals: list = None, limit: int = 100) -> Iterator[LeadCandidate]:
    """Run self-hosted Reddit scraper for given metro/niches."""
    scraper = RedditScraper(headless=True)
    niches = verticals or list(SUBREDDITS.keys())
    
    for niche in niches:
        subs = SUBREDDITS.get(niche, [niche])
        for sub in subs:
            try:
                for lead in scraper.fetch(niche=niche, state=metro or "NY", limit=limit // len(subs)):
                    yield lead
            except Exception as e:
                print(f"[reddit] Error for r/{sub}: {e}")

def register_source(reg):
    from empire_os.lead_sources import SourceInfo
    reg(SourceInfo(
        name="reddit",
        tier="real",
        requires=[],
        description="Self-hosted Reddit scraper (Playwright) — no API key",
        run_fn=run,
    ))