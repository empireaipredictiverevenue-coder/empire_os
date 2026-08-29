"""Enhanced Universal Scraper — Cortex + Enrichment + Market Intel."""

from __future__ import annotations
from typing import Iterator, Optional
from empire_os.lead_sources.models import LeadCandidate
from empire_os.lead_sources import register

import sys
sys.path.insert(0, '/root/empire_os')
from sources.enhanced_universal_scraper import EnhancedUniversalScraper

def run(metro: str = None, verticals: list = None, limit: int = 100) -> Iterator[LeadCandidate]:
    """Run enhanced universal scraper (Cortex + Enrichment + Market Intel)."""
    scraper = EnhancedUniversalScraper()
    niches = verticals or ["roofing", "hvac", "plumbing", "electrical", "solar", "general_contractor"]
    state = metro or "NY"
    
    for niche in niches:
        try:
            for lead in scraper.fetch(niche=niche, state=state, limit=limit // len(niches)):
                yield lead
        except Exception as e:
            print(f"[enhanced_universal] Error for {niche} in {state}: {e}")

def register_source(reg):
    from empire_os.lead_sources import SourceInfo
    reg(SourceInfo(
        name="enhanced_universal",
        tier="real",
        requires=[],
        description="Enhanced Universal Scraper (Cortex + Enrichment + Market Intel) — self-hosted",
        run_fn=run,
    ))