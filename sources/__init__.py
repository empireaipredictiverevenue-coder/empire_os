"""Unified lead source factory + runner.

Orchestrates all lead sources: permit, license, gbp, yelp, reddit.
Produces LeadCandidate → stores in si_lead_raw → scout agent validates → routes.
"""

from __future__ import annotations
import dataclasses
import datetime
import json
import os
import sqlite3
import sys
import time
from typing import Dict, List, Iterator, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import all sources
from sources.permit_source import PermitSource, LeadCandidate as PermitLead
from sources.license_source import LicenseSource, LeadCandidate as LicenseLead
from sources.gbp_source import GBPSource, LeadCandidate as GBPLead
from sources.yelp_source import YelpSource, LeadCandidate as YelpLead
from sources.reddit_source import RedditSource, LeadCandidate as RedditLead
# Self-hosted scrapers (no API keys needed)
from sources.gmaps_scraper import GMapsScraper, LeadCandidate as GMapsLead
from sources.yelp_scraper import YelpScraper, LeadCandidate as YelpScraperLead
from sources.reddit_scraper import RedditScraper, LeadCandidate as RedditScraperLead
# Empire OS universal scraper adapter
from sources.universal_adapter import UniversalScraper, LeadCandidate as UniversalLead
# Enhanced universal scraper (Cortex + Enrichment + Market Intel)
from sources.enhanced_universal_scraper import EnhancedUniversalScraper, LeadCandidate as EnhancedUniversalLead

DB = "/root/empire_os/empire_os.db"

# Unified LeadCandidate - use the one from permit_source as base
LeadCandidate = PermitLead

SOURCE_CLASSES = {
    "permit": PermitSource,
    "license": LicenseSource,
    "gbp": GBPSource,
    "yelp": YelpSource,
    "reddit": RedditSource,
    # Self-hosted alternatives
    "gmaps": GMapsScraper,
    "yelp_scraper": YelpScraper,
    "reddit_scraper": RedditScraper,
    # Empire OS universal scraper
    "universal": UniversalScraper,
    # Enhanced universal scraper (Cortex + Enrichment + Market Intel)
    "enhanced_universal": EnhancedUniversalScraper,
}

SOURCE_CONFIG = {
    "permit": {"enabled": True, "priority": 1, "rate_limit": 10},
    "license": {"enabled": True, "priority": 2, "rate_limit": 5},
    "gbp": {"enabled": bool(os.environ.get("APIFY_API_TOKEN")), "priority": 3, "rate_limit": 5},
    "yelp": {"enabled": bool(os.environ.get("YELP_API_KEY")), "priority": 4, "rate_limit": 5},
    "reddit": {"enabled": bool(os.environ.get("REDDIT_CLIENT_ID")), "priority": 5, "rate_limit": 2},
    # Self-hosted - always available
    "gmaps": {"enabled": True, "priority": 6, "rate_limit": 3},
    "yelp_scraper": {"enabled": True, "priority": 7, "rate_limit": 3},
    "reddit_scraper": {"enabled": True, "priority": 8, "rate_limit": 2},
    # Empire OS universal scraper (primary)
    "universal": {"enabled": True, "priority": 3, "rate_limit": 2},
    # Enhanced universal (primary with full Cortex + Enrichment + Market Intel)
    "enhanced_universal": {"enabled": True, "priority": 2, "rate_limit": 1},
}


def get_source(name: str):
    """Get source instance by name."""
    cls = SOURCE_CLASSES.get(name)
    if not cls:
        raise ValueError(f"Unknown source: {name}")
    return cls()


def get_enabled_sources() -> List[str]:
    """Return list of enabled source names sorted by priority."""
    return sorted(
        [name for name, cfg in SOURCE_CONFIG.items() if cfg.get("enabled")],
        key=lambda n: SOURCE_CONFIG[n]["priority"]
    )


def fetch_from_source(source_name: str, niche: str, state: str, city: Optional[str], limit: int) -> List[LeadCandidate]:
    """Fetch leads from a single source with error handling."""
    try:
        src = get_source(source_name)
        return list(src.fetch(niche, state, city, limit))
    except Exception as e:
        print(f"[{source_name}] ERROR: {e}", file=sys.stderr)
        return []


def store_leads(candidates: List[LeadCandidate]) -> int:
    """Store leads in crm_leads table (raw stage)."""
    if not candidates:
        return 0
    con = sqlite3.connect(DB, timeout=30)
    try:
        c = con.cursor()
        stored = 0
        for cand in candidates:
            c.execute(
                """INSERT OR IGNORE INTO crm_leads
                (lead_uid, source, business_name, phone, email, website, street, city, state, zip,
                 niche, sub_niche, license_no, license_state, status, created_at, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'raw', ?, ?)""",
                (f"{cand.source}:{cand.source_ref}", cand.source, cand.business_name,
                 cand.phone, cand.email, cand.website, cand.address, cand.city,
                 cand.state, cand.zip_code, cand.niche, cand.sub_niche,
                 cand.license_number, cand.state, cand.fetched_at, json.dumps(cand.raw_data))
            )
            if c.rowcount > 0:
                stored += 1
        con.commit()
        return stored
    finally:
        con.close()


def run_harvest(
    niches: List[str],
    states: List[str],
    cities: Optional[Dict[str, List[str]]] = None,
    limit_per_source: int = 50,
    max_workers: int = 3,
) -> Dict[str, int]:
    """
    Run harvest across all enabled sources.

    Args:
        niches: List of niches to harvest (e.g., ["roofing", "hvac", "plumbing"])
        states: List of states (e.g., ["CA", "TX", "FL"])
        cities: Optional dict state -> list of cities (e.g., {"CA": ["Los Angeles", "San Diego"]})
        limit_per_source: Max leads per source per niche/state/city combo
        max_workers: Parallel workers for source fetching

    Returns:
        Dict with stats: {"total_fetched": N, "total_stored": N, "by_source": {...}}
    """
    enabled = get_enabled_sources()
    print(f"[harvest] Enabled sources: {enabled}")
    print(f"[harvest] Niches: {niches}")
    print(f"[harvest] States: {states}")

    total_fetched = 0
    total_stored = 0
    by_source = {s: 0 for s in enabled}

    # Build target combinations
    targets = []
    for niche in niches:
        for state in states:
            city_list = cities.get(state, [None]) if cities else [None]
            for city in city_list:
                targets.append((niche, state, city))

    print(f"[harvest] Target combos: {len(targets)}")

    for niche, state, city in targets:
        print(f"[harvest] Processing: niche={niche} state={state} city={city or 'all'}")

        # Fetch from all sources in parallel
        all_candidates = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(fetch_from_source, src, niche, state, city, limit_per_source): src
                for src in enabled
            }
            for future in as_completed(futures):
                src_name = futures[future]
                try:
                    candidates = future.result(timeout=60)
                    all_candidates.extend(candidates)
                    by_source[src_name] += len(candidates)
                    total_fetched += len(candidates)
                    print(f"  [{src_name}] fetched {len(candidates)} leads")
                except Exception as e:
                    print(f"  [{src_name}] ERROR: {e}")

        # Store batch
        if all_candidates:
            stored = store_leads(all_candidates)
            total_stored += stored
            print(f"  Stored {stored} new leads (deduped)")

    return {
        "total_fetched": total_fetched,
        "total_stored": total_stored,
        "by_source": by_source,
    }


if __name__ == "__main__":
    # Quick test
    print("=== Lead Source Factory Test ===")
    print(f"Enabled sources: {get_enabled_sources()}")
    for name in get_enabled_sources():
        src = get_source(name)
        print(f"  {name}: niches={src.supported_niches}")

    # Test harvest (mock - no API keys)
    result = run_harvest(
        niches=["roofing"],
        states=["CA"],
        limit_per_source=2,
        max_workers=2,
    )
    print(f"\nResult: {result}")