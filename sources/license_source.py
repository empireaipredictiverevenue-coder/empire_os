"""State contractor license source adapter.

Fetches from state licensing board APIs/public records.
"""

from __future__ import annotations
import dataclasses
import datetime
import json
import re
import sqlite3
import urllib.parse
import urllib.request
import urllib.error
from typing import Iterator, List, Optional, Dict, Any

DB = "/root/empire_os/empire_os.db"


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


class LicenseSource:
    """State contractor license boards — public search APIs."""

    source_name = "license"

    # State license board endpoints (simplified - real APIs vary)
    STATE_APIS = {
        "CA": {
            "url": "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/CheckLicense.aspx",
            "search_url": "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/SearchLicense.aspx",
            "license_types": {
                "C-39": "roofing",
                "C-20": "hvac",
                "C-36": "plumbing",
                "C-10": "electrical",
                "C-46": "solar",
                "B": "general_contractor",
            },
        },
        "TX": {
            "url": "https://www.tdlr.texas.gov/licensesearch/",
            "license_types": {
                "ROOF": "roofing",
                "ACR": "hvac",
                "PLB": "plumbing",
                "ELC": "electrical",
                "SOL": "solar",
            },
        },
        "FL": {
            "url": "https://www.myfloridalicense.com/CheckLicense/",
            "license_types": {
                "CBC": "roofing",
                "CAC": "hvac",
                "CFC": "plumbing",
                "EC": "electrical",
                "SLC": "solar",
                "CRC": "general_contractor",
            },
        },
        "AZ": {
            "url": "https://roc.az.gov/contractor-search",
            "license_types": {
                "R-11": "roofing",
                "C-39": "hvac",
                "C-37": "plumbing",
                "C-11": "electrical",
            },
        },
        "NV": {
            "url": "https://www.nvcontractorsboard.com/license-search",
            "license_types": {
                "C-15": "roofing",
                "C-21": "hvac",
                "C-01": "plumbing",
                "C-02": "electrical",
            },
        },
    }

    NICHE_TO_LICENSE = {
        "roofing": ["roof", "roofing", "C-39", "CBC", "ROOF", "R-11", "C-15"],
        "hvac": ["hvac", "heating", "cooling", "air conditioning", "C-20", "CAC", "ACR", "C-39", "C-21"],
        "plumbing": ["plumb", "plumbing", "C-36", "CFC", "PLB", "C-37", "C-01"],
        "electrical": ["electric", "electrical", "C-10", "EC", "ELC", "C-11", "C-02"],
        "solar": ["solar", "photovoltaic", "C-46", "SLC", "SOL"],
        "general_contractor": ["general", "building", "B", "CRC", "CBC"],
    }

    def __init__(self):
        pass

    @property
    def supported_niches(self) -> List[str]:
        return list(self.NICHE_TO_LICENSE.keys())

    def _match_niche(self, license_class: str, business_name: str = "") -> str:
        text = f"{license_class} {business_name}".lower()
        for niche, keywords in self.NICHE_TO_LICENSE.items():
            if any(kw.lower() in text for kw in keywords):
                return niche
        return "general_contractor"

    def _extract_phone(self, text: str) -> Optional[str]:
        if not text:
            return None
        matches = re.findall(r'(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})', text)
        if matches:
            return f"({matches[0][0]}) {matches[0][1]}-{matches[0][2]}"
        return None

    def fetch(self, niche: str, state: str, city: Optional[str] = None, limit: int = 100) -> Iterator[LeadCandidate]:
        state = state.upper()
        config = self.STATE_APIS.get(state)
        if not config:
            return

        license_types = config.get("license_types", {})
        relevant_types = {k: v for k, v in license_types.items() if v == niche or niche == "all"}

        # Note: Most state license boards don't have open APIs.
        # This is a template - real implementation would:
        # 1. Use Selenium/Playwright for web scraping
        # 2. Use FOIA requests for bulk data
        # 3. Purchase from data aggregators (e.g., StateBook, LicenseLogix)
        # 4. Use state open data portals where available

        # Placeholder: yield mock data structure for integration testing
        # In production, replace with actual API/scraper calls
        for lic_type, lic_niche in relevant_types.items():
            # Mock candidate - replace with real fetch
            cand = LeadCandidate(
                source=self.source_name,
                source_ref=f"{state}:{lic_type}:sample",
                niche=lic_niche,
                sub_niche=lic_type,
                business_name=f"Sample {lic_niche.title()} Contractor",
                phone=None,
                email=None,
                address=None,
                city=city,
                state=state,
                zip_code=None,
                license_number=lic_type,
                license_status="active",
                license_expiry=None,
                raw_data={"license_type": lic_type, "state": state, "source": "mock"},
            )
            yield cand
            break  # only one mock per type for demo


if __name__ == "__main__":
    src = LicenseSource()
    print(f"Source: {src.source_name}")
    print(f"Supported niches: {src.supported_niches}")
    print(f"State APIs: {list(src.STATE_APIS.keys())}")

    for lead in src.fetch("roofing", "CA", limit=3):
        print(f"  {lead.business_name} | {lead.state} | lic: {lead.license_number} | {lead.niche}")