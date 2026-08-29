"""Enhanced Universal Scraper — Empire OS v3
==========================================
Wires together: universal_scraper + cortex API + enrichment waterfall + market intelligence.

Sources (14+ no-key):
  Google Maps, Bing Places, Yelp, YellowPages, BBB, State Registry, Home Services,
  Business Directories, Facebook Pages, LinkedIn, Job Boards, News, Social Intent, Permits

Integrates:
  • Cortex Brain Loop strategic decisions (niche pivots, price changes, score boosts)
  • Cortex API for real-time niche heat + competitor data
  • Enrichment Waterfall (website_scraper → DDG → Bing → Google → WHOIS → BBB → pattern → Hunter/Apollo/Prospeo)
  • Waterfall orchestrator for contact validation
  • Predictive revenue + market gaps for source prioritization
"""

from __future__ import annotations
import dataclasses
import datetime
import json
import logging
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterator, Optional, List, Dict, Any, Callable

# Add empire_os to path
sys.path.insert(0, "/root/empire_os")

# Import existing Empire OS modules
try:
    from empire_os.lead_sources.universal_scraper import (
        run as universal_run,
        LeadCandidate as UniversalLeadModel,
    )
    from empire_os.lead_sources.models import LeadCandidate as UniversalLeadModel2
    from empire_os.enrichment import (
        website_scraper, ddg_search, bing_search, google_search,
        bbb_lookup, whois_lookup, email_pattern,
        linkedin_guess, social_footprint,
    )
    from empire_os.waterfall import (
        Waterfall, WaterfallResult, LeadContact,
        build_default_waterfall,
        RegistryScraperProvider, SiteCrawlerProvider,
        ApolloProvider, PeopleDataLabsProvider, HunterProvider,
    )
    from empire_os.cortex_api import _niche_heat, _fetch_blueprint, _competitor_breakdown
    from empire_os.cortex_brain_loop import gather_live_state, run_predictive_analysis
    from empire_os.predictive import detect_market_gaps
    from empire_os.cortex_scorer import get_niche_score
except ImportError as e:
    logging.warning(f"Import warning: {e}")

# Local LeadCandidate (compatible with factory)
@dataclasses.dataclass
class LeadCandidate:
    source: str
    source_ref: str
    niche: str
    sub_niche: str
    business_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    license_number: Optional[str] = None
    license_status: Optional[str] = None
    license_expiry: Optional[str] = None
    permit_number: Optional[str] = None
    permit_type: Optional[str] = None
    permit_value: Optional[float] = None
    permit_date: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    years_in_business: Optional[int] = None
    employee_count: Optional[int] = None
    raw_data: Dict[str, Any] = dataclasses.field(default_factory=dict)
    fetched_at: str = dataclasses.field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

    # Cortex enhancements
    cortex_heat_score: Optional[int] = None
    cortex_tier: Optional[str] = None
    cortex_competitors: List[Dict] = dataclasses.field(default_factory=list)
    cortex_blueprint: Optional[Dict] = None
    enrichment_waterfall_result: Optional[Dict] = None
    market_gap_type: Optional[str] = None  # hot, unsaturated, dead
    predictive_score: Optional[float] = None
    buyer_scoring_boost: int = 0


DB = "/root/empire_os/empire_os.db"
CORTEX_CACHE = Path("/run/cortex_niche_scores.json")


class EnhancedUniversalScraper:
    """Enhanced universal scraper with Cortex + Enrichment + Market Intelligence."""

    source_name = "universal_enhanced"

    SUPPORTED_NICHES = [
        "roofing", "hvac", "plumbing", "electrical", "landscaping",
        "solar", "pest_control", "painting", "fencing", "windows",
        "flooring", "concrete", "excavation", "tree_service", "pool",
        "general_contractor", "siding", "masonry", "foundation",
    ]

    def __init__(self, enable_enrichment: bool = True, enable_cortex: bool = True, enable_predictive: bool = True):
        self.enable_enrichment = enable_enrichment
        self.enable_cortex = enable_cortex
        self.enable_predictive = enable_predictive
        self._waterfall = None
        self._state_cache = None
        self._state_cache_ts = 0

    @property
    def supported_niches(self) -> List[str]:
        return self.SUPPORTED_NICHES

    def _get_waterfall(self):
        if self._waterfall is None:
            self._waterfall = build_default_waterfall()
        return self._waterfall

    def _get_cached_state(self) -> Dict[str, Any]:
        """Get cached market intelligence state (refresh every 5 min)."""
        if time.time() - self._state_cache_ts > 300:
            self._state_cache = gather_live_state()
            self._state_cache_ts = time.time()
        return self._state_cache

    def _get_cortex_data(self, niche: str, metro: str) -> Dict[str, Any]:
        """Fetch Cortex niche heat, blueprint, competitors."""
        if not self.enable_cortex:
            return {}

        try:
            heat = _niche_heat(niche, metro)
            tier = "hot" if heat >= 75 else "warm" if heat >= 60 else "cold"
            bp = _fetch_blueprint(niche, limit=1)
            comps = _competitor_breakpoint(niche)
            return {
                "heat_score": heat,
                "tier": tier,
                "blueprint": bp,
                "competitors": comps,
            }
        except Exception as e:
            logging.debug(f"Cortex data fetch failed: {e}")
            return {}

    def _get_market_gap(self, niche: str, state: str) -> Optional[str]:
        """Determine market gap type for niche+state."""
        if not self.enable_predictive:
            return None
        try:
            state_data = self._get_cached_state()
            lanes = [dict(r) for r in state_data.get("lanes", [])]
            leads = [dict(r) for r in state_data.get("leads", [])]
            gaps = detect_market_gaps(lanes, leads)

            # Check if this niche+state is in hot/unsaturated/dead
            for gap in gaps.get("hot_gaps", []):
                if niche.lower() in gap.get("niche_metro", "").lower() and state.upper() in gap.get("niche_metro", "").upper():
                    return "hot"
            for gap in gaps.get("unsaturated", []):
                if niche.lower() in gap.get("niche_metro", "").lower() and state.upper() in gap.get("niche_metro", "").upper():
                    return "unsaturated"
            for gap in gaps.get("dead", []):
                if niche.lower() in gap.get("niche_metro", "").lower() and state.upper() in gap.get("niche_metro", "").upper():
                    return "dead"
        except Exception as e:
            logging.debug(f"Market gap check failed: {e}")
        return None

    def _enrich_lead(self, lead: LeadCandidate) -> LeadCandidate:
        """Run full enrichment waterfall on a lead."""
        if not self.enable_enrichment:
            return lead

        # Prepare lead info for waterfall
        lead_info = {
            "company": lead.business_name,
            "website": lead.website or "",
            "phone": lead.phone or "",
            "email": lead.email or "",
            "city": lead.city or "",
            "state": lead.state or "",
            "niche": lead.niche,
        }

        # Run enrichment providers (free ones first)
        enriched = {}
        try:
            # 1. Website scraper
            res = website_scraper(lead_info)
            enriched.update(res)

            # 2. DDG search
            res = ddg_search(lead_info)
            for k, v in res.items():
                if k not in enriched or not enriched[k]:
                    enriched[k] = v

            # 3. Bing search
            res = bing_search(lead_info)
            for k, v in res.items():
                if k not in enriched or not enriched[k]:
                    enriched[k] = v

            # 4. BBB lookup
            res = bbb_lookup(lead_info)
            enriched.update(res)

            # 5. WHOIS
            res = whois_lookup(lead_info)
            enriched.update(res)

            # 6. Email pattern
            res = email_pattern(lead_info)
            enriched.update(res)

            # 7. LinkedIn guess
            res = linkedin_guess(lead_info)
            enriched.update(res)

            # 8. Social footprint
            res = social_footprint(lead_info)
            enriched.update(res)

            # Apply enriched fields to lead
            for field in ["email", "phone", "website", "address", "city", "state", "zip_code",
                          "rating", "review_count", "years_in_business", "employee_count",
                          "linkedin_guess", "social_links", "bbb_rating", "year_founded", "domain_created"]:
                if enriched.get(field) and not getattr(lead, field, None):
                    setattr(lead, field, enriched[field])

            # Run waterfall for contact validation
            wf_result = self._get_waterfall().enrich(lead_info)
            lead.enrichment_waterfall_result = wf_result.to_dict()

            if wf_result.success and wf_result.contact:
                if wf_result.contact.email and not lead.email:
                    lead.email = wf_result.contact.email
                if wf_result.contact.phone and not lead.phone:
                    lead.phone = wf_result.contact.phone

        except Exception as e:
            logging.debug(f"Enrichment failed for {lead.business_name}: {e}")

        return lead

    def _apply_cortex_intel(self, lead: LeadCandidate, metro: str) -> LeadCandidate:
        """Apply Cortex strategic intelligence to lead."""
        if not self.enable_cortex:
            return lead

        cortex_data = self._get_cortex_data(lead.niche, metro)
        if cortex_data:
            lead.cortex_heat_score = cortex_data.get("heat_score")
            lead.cortex_tier = cortex_data.get("tier")
            lead.cortex_competitors = cortex_data.get("competitors", [])
            lead.cortex_blueprint = cortex_data.get("blueprint")

            # Apply buyer scoring boost from cortex_brain_loop
            try:
                score = get_niche_score(lead.niche, metro)
                lead.buyer_scoring_boost = max(0, int(score.get("boost", 0))) if isinstance(score, dict) else 0
            except Exception:
                pass

        return lead

    def _apply_market_intel(self, lead: LeadCandidate, state: str) -> LeadCandidate:
        """Apply predictive market intelligence to lead."""
        if not self.enable_predictive:
            return lead

        gap_type = self._get_market_gap(lead.niche, state)
        if gap_type:
            lead.market_gap_type = gap_type
            # Boost score based on gap type
            if gap_type == "hot":
                lead.buyer_scoring_boost += 15
                lead.predictive_score = 0.85
            elif gap_type == "unsaturated":
                lead.buyer_scoring_boost += 10
                lead.predictive_score = 0.7
            elif gap_type == "dead":
                lead.predictive_score = 0.3

        return lead

    def _map_state_to_metro(self, state: str) -> str:
        metro_map = {
            "CA": "LAX", "NY": "NYC", "IL": "CHI", "TX": "DFW",
            "FL": "MIA", "GA": "ATL", "AZ": "PHX", "PA": "PHL",
            "WA": "SEA", "MA": "BOS", "CO": "DEN", "MI": "DET",
            "DC": "WDC", "VA": "WDC", "MD": "WDC",
        }
        return metro_map.get(state.upper(), "LAX")

    def fetch(self, niche: str, state: str, city: Optional[str] = None, limit: int = 100) -> Iterator[LeadCandidate]:
        metro = self._map_state_to_metro(state)

        # Run universal scraper
        if universal_run is not None:
            for uni_lead in universal_run(metro=metro, niches=[niche], limit=limit):
                # Convert to our LeadCandidate
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
                    raw_data=uni_lead.raw if uni_lead.raw else {"source": uni_lead.source, "lead_score": uni_lead.lead_score, "details": uni_lead.details, "metro": uni_lead.metro},
                    fetched_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                )

                # Apply Cortex intelligence
                cand = self._apply_cortex_intel(cand, metro)

                # Apply Market Intelligence
                cand = self._apply_market_intel(cand, state)

                # Run Enrichment Waterfall
                cand = self._enrich_lead(cand)

                yield cand


if __name__ == "__main__":
    scraper = EnhancedUniversalScraper()
    print(f"Source: {scraper.source_name}")
    print(f"Supported niches: {scraper.supported_niches}")
    print(f"Enrichment: {scraper.enable_enrichment}")
    print(f"Cortex: {scraper.enable_cortex}")
    print(f"Predictive: {scraper.enable_predictive}")

    for lead in scraper.fetch("roofing", "CA", "Los Angeles", limit=2):
        print(f"  {lead.business_name} | {lead.city}, {lead.state}")
        print(f"    Cortex: heat={lead.cortex_heat_score}, tier={lead.cortex_tier}, gap={lead.market_gap_type}")
        print(f"    Enriched: email={lead.email}, phone={lead.phone}, waterfall={lead.enrichment_waterfall_result.get('success') if lead.enrichment_waterfall_result else 'N/A'}")