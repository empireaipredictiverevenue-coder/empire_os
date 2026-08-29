"""Lead source adapter base + county building permits source.

Each source produces LeadCandidate dataclass → funnel scout validates → routes → stores.
"""

from __future__ import annotations
import abc
import dataclasses
import datetime
import json
import os
import re
import sqlite3
import time
import urllib.request
import urllib.error
from typing import Optional, Iterator, List, Dict, Any
from pathlib import Path

DB = "/root/empire_os/empire_os.db"


@dataclasses.dataclass
class LeadCandidate:
    """Normalized lead from any source. Scout agent validates/enriches before storage."""
    source: str                    # "permit", "license", "gbp", "yelp", "reddit"
    source_ref: str                # source-specific unique ID (permit number, license ID, place_id, etc.)
    niche: str                     # "roofing", "hvac", "solar", "plumbing", etc.
    sub_niche: str                 # "residential_roofing", "commercial_hvac", etc.
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

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


class LeadSource(abc.ABC):
    """Abstract base for lead sources."""

    @property
    @abc.abstractmethod
    def source_name(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def supported_niches(self) -> List[str]:
        pass

    @abc.abstractmethod
    def fetch(self, niche: str, state: str, city: Optional[str] = None, limit: int = 100) -> Iterator[LeadCandidate]:
        """Yield LeadCandidate objects for given niche/location."""
        pass

    def _store_raw(self, candidates: List[LeadCandidate]) -> int:
        """Store raw candidates in si_lead_raw for audit/reprocessing."""
        if not candidates:
            return 0
        con = sqlite3.connect(DB, timeout=30)
        try:
            c = con.cursor()
            for cand in candidates:
                c.execute(
                    """INSERT OR IGNORE INTO si_lead_raw
                    (source, source_ref, niche, sub_niche, raw_json, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (cand.source, cand.source_ref, cand.niche, cand.sub_niche,
                     json.dumps(cand.raw_data), cand.fetched_at)
                )
            con.commit()
            return c.rowcount
        finally:
            con.close()


class PermitSource(LeadSource):
    """County building permits — public APIs in 30+ counties."""

    source_name = "permit"

    # Map of county -> API endpoint config
    COUNTY_APIS = {
        "CA-Los_Angeles": {
            "url": "https://data.lacounty.gov/resource/8jvj-p83p.json",
            "params": {"$limit": 1000, "$order": "issue_date DESC"},
            "niche_map": {"BUILDING": "general_contractor", "ELECTRICAL": "electrical", "PLUMBING": "plumbing", "MECHANICAL": "hvac"},
        },
        "CA-San_Diego": {
            "url": "https://data.sandiego.gov/resource/pi6j-8z2j.json",
            "params": {"$limit": 1000, "$order": "issued_date DESC"},
        },
        "CA-Santa_Clara": {
            "url": "https://data.sccgov.org/resource/8v3m-y5e7.json",
            "params": {"$limit": 1000, "$order": "issue_date DESC"},
        },
        "TX-Harris": {
            "url": "https://data.harriscountytx.gov/resource/3y6a-7q9j.json",
            "params": {"$limit": 1000, "$order": "permit_issued_date DESC"},
        },
        "TX-Travis": {
            "url": "https://data.austintexas.gov/resource/3syk-45ze.json",
            "params": {"$limit": 1000, "$order": "issue_date DESC"},
        },
        "FL-Miami_Dade": {
            "url": "https://miamidade.gov/api/permits",
            "params": {"limit": 1000},
        },
        "FL-Broward": {
            "url": "https://data.browardcountyfl.gov/resource/permits.json",
            "params": {"$limit": 1000},
        },
        "IL-Cook": {
            "url": "https://data.cityofchicago.org/resource/ydr8-5enu.json",
            "params": {"$limit": 1000, "$order": "issue_date DESC"},
        },
        "NY-New_York": {
            "url": "https://data.cityofnewyork.us/resource/ipu4-2q9a.json",
            "params": {"$limit": 1000, "$order": "issuance_date DESC"},
        },
        "WA-King": {
            "url": "https://data.kingcounty.gov/resource/5p6t-8j5j.json",
            "params": {"$limit": 1000, "$order": "issue_date DESC"},
        },
        # Add more counties as needed — 30+ available
    }

    NORMALIZED_NICHES = {
        "roofing": ["roof", "roofing", "reroof"],
        "hvac": ["hvac", "heating", "cooling", "air conditioning", "mechanical"],
        "plumbing": ["plumb", "plumbing", "water heater", "sewer"],
        "electrical": ["electric", "electrical", "wiring", "panel"],
        "solar": ["solar", "photovoltaic", "pv system"],
        "general_contractor": ["building", "construction", "remodel", "addition", "new construction"],
        "fence": ["fence", "fencing"],
        "pool": ["pool", "spa"],
        "concrete": ["concrete", "masonry", "foundation"],
        "windows": ["window", "windows", "glazing"],
        "siding": ["siding", "stucco", "exterior"],
    }

    def __init__(self):
        self._session = None

    @property
    def supported_niches(self) -> List[str]:
        return list(self.NORMALIZED_NICHES.keys())

    def _normalize_niche(self, permit_type: str, description: str = "") -> str:
        text = f"{permit_type} {description}".lower()
        for niche, keywords in self.NORMALIZED_NICHES.items():
            if any(kw in text for kw in keywords):
                return niche
        return "general_contractor"

    def _extract_phone(self, text: str) -> Optional[str]:
        if not text:
            return None
        # US phone patterns
        matches = re.findall(r'(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})', text)
        if matches:
            return f"({matches[0][0]}) {matches[0][1]}-{matches[0][2]}"
        return None

    def _extract_email(self, text: str) -> Optional[str]:
        if not text:
            return None
        matches = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        if matches:
            return matches[0]
        return None

    def fetch(self, niche: str, state: str, city: Optional[str] = None, limit: int = 100) -> Iterator[LeadCandidate]:
        # Find matching county APIs for this state
        state_prefix = state.upper()[:2]
        matching_counties = {k: v for k, v in self.COUNTY_APIS.items() if k.startswith(state_prefix)}

        if not matching_counties:
            return

        count = 0
        for county_key, config in matching_counties.items():
            if count >= limit:
                break

            url = config["url"]
            params = config.get("params", {}).copy()
            params["$limit"] = min(limit - count, 500)

            # Build query string
            if params:
                qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
                full_url = f"{url}?{qs}"
            else:
                full_url = url

            try:
                req = urllib.request.Request(full_url, headers={"User-Agent": "EmpireOS/1.0"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode())
            except Exception as e:
                continue

            for record in data:
                if count >= limit:
                    break

                # Normalize record fields (varies by county API)
                permit_num = record.get("permit_number") or record.get("record_num") or record.get("permit_id") or ""
                permit_type = record.get("permit_type") or record.get("work_type") or record.get("permit_class") or ""
                description = record.get("description") or record.get("work_description") or record.get("description_of_work") or ""
                business_name = record.get("contractor_name") or record.get("applicant_name") or record.get("owner_name") or ""
                address = record.get("address") or record.get("site_address") or record.get("job_address") or ""
                city_rec = record.get("city") or record.get("job_city") or city or ""
                zip_code = record.get("zip") or record.get("zip_code") or record.get("postal_code") or ""
                phone = record.get("phone") or record.get("contractor_phone") or record.get("applicant_phone") or self._extract_phone(description)
                email = record.get("email") or record.get("contractor_email") or self._extract_email(description)
                license_num = record.get("license_number") or record.get("contractor_license") or record.get("state_license") or ""
                permit_value = record.get("valuation") or record.get("permit_valuation") or record.get("job_value")
                permit_date = record.get("issue_date") or record.get("issued_date") or record.get("permit_date") or ""

                if not business_name or not permit_num:
                    continue

                normalized_niche = self._normalize_niche(permit_type, description)
                if niche != "all" and normalized_niche != niche:
                    continue

                cand = LeadCandidate(
                    source=self.source_name,
                    source_ref=f"{county_key}:{permit_num}",
                    niche=normalized_niche,
                    sub_niche=permit_type.lower().replace(" ", "_") if permit_type else normalized_niche,
                    business_name=business_name.strip(),
                    phone=phone,
                    email=email,
                    address=address.strip() if address else None,
                    city=city_rec.strip() if city_rec else None,
                    state=state.upper(),
                    zip_code=zip_code,
                    license_number=license_num or None,
                    permit_number=permit_num,
                    permit_type=permit_type,
                    permit_value=float(permit_value) if permit_value else None,
                    permit_date=permit_date,
                    raw_data=record,
                )
                count += 1
                yield cand


# Register source
SOURCE_REGISTRY = {
    "permit": PermitSource,
}

def get_source(name: str) -> LeadSource:
    cls = SOURCE_REGISTRY.get(name)
    if not cls:
        raise ValueError(f"Unknown source: {name}")
    return cls()


if __name__ == "__main__":
    # Quick test
    src = PermitSource()
    print(f"Source: {src.source_name}")
    print(f"Supported niches: {src.supported_niches}")
    print(f"County APIs configured: {len(src.COUNTY_APIS)}")

    # Test CA roofing
    count = 0
    for lead in src.fetch("roofing", "CA", limit=5):
        print(f"  {lead.business_name} | {lead.city}, {lead.state} | {lead.permit_number} | {lead.niche}")
        count += 1
    print(f"Fetched {count} test leads")