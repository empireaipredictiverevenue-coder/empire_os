"""Adapter to make UniversalScraper compatible with factory pattern."""

from __future__ import annotations
import dataclasses
import datetime
import os
import sys
from typing import Iterator, List, Optional, Dict, Any

# Add empire_os to path
sys.path.insert(0, "/root/empire_os")

try:
    from empire_os.lead_sources.universal_scraper import run as universal_run
    from empire_os.lead_sources.models import LeadCandidate as UniversalLeadModel
except ImportError:
    universal_run = None
    UniversalLeadModel = None

from sources.permit_source import LeadCandidate as BaseLeadCandidate

# Reuse the LeadCandidate from permit_source
LeadCandidate = BaseLeadCandidate


class UniversalScraper:
    """Adapter wrapper for Empire OS universal_scraper.run()"""

    source_name = "universal"

    # Niches supported by universal_scraper
    SUPPORTED_NICHES = [
        "roofing", "hvac", "plumbing", "electrical", "landscaping",
        "solar", "pest_control", "painting", "fencing", "windows",
        "flooring", "concrete", "excavation", "tree_service", "pool",
        "general_contractor", "siding", "concrete", "masonry", "foundation",
    ]

    def __init__(self):
        pass

    @property
    def supported_niches(self) -> List[str]:
        return self.SUPPORTED_NICHES

    def fetch(self, niche: str, state: str, city: Optional[str] = None, limit: int = 100) -> Iterator[LeadCandidate]:
        if universal_run is None:
            return

        # Map state to metro
        metro_map = {
            "CA": "LAX",
            "NY": "NYC",
            "IL": "CHI",
            "TX": "DFW",
            "FL": "MIA",
            "GA": "ATL",
            "AZ": "PHX",
            "PA": "PHL",
            "WA": "SEA",
            "MA": "BOS",
            "CO": "DEN",
            "MI": "DET",
            "DC": "WDC",
            "VA": "WDC",
            "MD": "WDC",
        }
        metro = metro_map.get(state.upper(), "LAX")

        # Run universal scraper
        for uni_lead in universal_run(metro=metro, niches=[niche], limit=limit):
            # Convert UniversalLeadModel to our LeadCandidate
            cand = LeadCandidate(
                source=self.source_name,
                source_ref=f"universal:{uni_lead.source}:{uni_lead.name.replace(' ', '_').lower()}",
                niche=uni_lead.niche,
                sub_niche=uni_lead.niche,
                business_name=uni_lead.name,
                phone=uni_lead.phone,
                email=uni_lead.email,
                website=uni_lead.url,
                address=None,
                city=city,
                state=state.upper(),
                zip_code=None,
                latitude=None,
                longitude=None,
                license_number=None,
                license_status=None,
                license_expiry=None,
                permit_number=None,
                permit_type=None,
                permit_value=None,
                permit_date=None,
                rating=None,
                review_count=None,
                years_in_business=None,
                employee_count=None,
                raw_data=uni_lead.raw if uni_lead.raw else {"source": uni_lead.source, "lead_score": uni_lead.lead_score, "details": uni_lead.details, "metro": uni_lead.metro},
                fetched_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )
            yield cand


if __name__ == "__main__":
    scraper = UniversalScraper()
    print(f"Source: {scraper.source_name}")
    print(f"Supported niches: {scraper.supported_niches}")
    print(f"Universal runner available: {universal_run is not None}")

    for lead in scraper.fetch("roofing", "CA", limit=2):
        print(f"  {lead.business_name} | {lead.city}, {lead.state} | source: {lead.raw_data.get('source')}")