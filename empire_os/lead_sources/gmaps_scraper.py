"""Self-hosted Google Maps scraper — no API keys, Playwright-based."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Iterator, Optional
from empire_os.lead_sources.models import LeadCandidate
from empire_os.lead_sources import register

# Import the self-hosted scraper
import sys
sys.path.insert(0, '/root/empire_os')
from sources.gmaps_scraper import GMapsScraper

SEARCH_QUERIES = {
    "roofing": ["roofing contractor", "roof repair", "roof installation"],
    "hvac": ["HVAC contractor", "air conditioning repair", "heating repair"],
    "plumbing": ["plumber", "plumbing contractor", "emergency plumber"],
    "electrical": ["electrician", "electrical contractor", "electrical repair"],
    "solar": ["solar installer", "solar panel installation", "solar company"],
    "general_contractor": ["general contractor", "home renovation", "remodeling contractor"],
    "fence": ["fence contractor", "fence installation"],
    "pool": ["pool builder", "pool contractor"],
    "concrete": ["concrete contractor", "concrete driveway"],
    "windows": ["window installation", "window replacement"],
    "siding": ["siding contractor", "siding installation"],
}

def run(metro: str = None, verticals: list = None, limit: int = 100) -> Iterator[LeadCandidate]:
    """Run self-hosted Google Maps scraper for given metro/niches."""
    scraper = GMapsScraper(headless=True)
    niches = verticals or list(SEARCH_QUERIES.keys())
    state = metro or "NY"
    
    for niche in niches:
        queries = SEARCH_QUERIES.get(niche, [niche])
        for query in queries:
            try:
                for lead in scraper.fetch(niche=niche, state=state, limit=limit // len(queries)):
                    yield lead
            except Exception as e:
                print(f"[gmaps] Error for {query} in {state}: {e}")

def register_source(reg):
    from empire_os.lead_sources import SourceInfo
    reg(SourceInfo(
        name="gmaps",
        tier="real",
        requires=[],
        description="Self-hosted Google Maps scraper (Playwright) — no API key",
        run_fn=run,
    ))