"""Yelp Fusion API source for local business leads.

Uses Yelp Fusion API to fetch business data with ratings, reviews, contact info.
"""

from __future__ import annotations
import dataclasses
import datetime
import json
import os
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


class YelpSource:
    """Yelp Fusion API — business search with ratings/reviews."""

    source_name = "yelp"
    API_BASE = "https://api.yelp.com/v3"
    SEARCH_ENDPOINT = "/businesses/search"
    BUSINESS_ENDPOINT = "/businesses/{id}"

    # Yelp category aliases for our niches
    CATEGORY_MAP = {
        "roofing": ["roofing"],
        "hvac": ["hvac", "heating_air_conditioning"],
        "plumbing": ["plumbing"],
        "electrical": ["electricians"],
        "solar": ["solar_installation"],
        "general_contractor": ["general_contractors", "home_inspectors"],
        "fence": ["fences"],
        "pool": ["pool_cleaners", "pool_repair"],
        "concrete": ["concrete"],
        "windows": ["windows_installation"],
        "siding": ["siding"],
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("YELP_API_KEY")

    @property
    def supported_niches(self) -> List[str]:
        return list(self.CATEGORY_MAP.keys())

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    def _search(self, term: str, location: str, categories: List[str], limit: int = 50) -> List[Dict]:
        if not self.api_key:
            return []

        params = {
            "term": term,
            "location": location,
            "categories": ",".join(categories),
            "limit": min(limit, 50),
            "sort_by": "rating",
            "attributes": "hot_and_new",
        }
        url = f"{self.API_BASE}{self.SEARCH_ENDPOINT}?{urllib.parse.urlencode(params)}"

        try:
            req = urllib.request.Request(url, headers=self._headers())
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
            return data.get("businesses", [])
        except Exception:
            return []

    def _get_business_details(self, business_id: str) -> Optional[Dict]:
        if not self.api_key:
            return None
        url = f"{self.API_BASE}{self.BUSINESS_ENDPOINT.format(id=business_id)}"
        try:
            req = urllib.request.Request(url, headers=self._headers())
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except Exception:
            return None

    def fetch(self, niche: str, state: str, city: Optional[str] = None, limit: int = 100) -> Iterator[LeadCandidate]:
        if not self.api_key:
            # Mock for testing
            yield LeadCandidate(
                source=self.source_name,
                source_ref=f"yelp:mock:{niche}:{state}",
                niche=niche,
                sub_niche=niche,
                business_name=f"Mock {niche.title()} Yelp Business",
                phone="(555) 987-6543",
                website="https://yelp.example.com",
                address="456 Oak Ave",
                city=city or "Sample City",
                state=state.upper(),
                zip_code="67890",
                rating=4.2,
                review_count=75,
                raw_data={"mock": True, "niche": niche, "state": state},
            )
            return

        categories = self.CATEGORY_MAP.get(niche, [niche])
        location = f"{city}, {state}" if city else state
        term = niche.replace("_", " ")

        results = self._search(term, location, categories, limit=limit)

        for biz in results:
            # Get detailed info
            details = self._get_business_details(biz.get("id", ""))
            data = details or biz

            # Extract location
            loc = data.get("location", {})
            coords = data.get("coordinates", {})

            # Yelp doesn't provide email directly - would need website scrape
            phone = data.get("phone")
            if phone and phone.startswith("+"):
                # Format: +1XXXXXXXXXX -> (XXX) XXX-XXXX
                digits = re.sub(r'\D', '', phone)
                if len(digits) == 11 and digits[0] == "1":
                    phone = f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"

            cand = LeadCandidate(
                source=self.source_name,
                source_ref=f"yelp:{data.get('id', '')}",
                niche=niche,
                sub_niche=categories[0] if categories else niche,
                business_name=data.get("name", ""),
                phone=phone,
                email=None,  # Yelp doesn't expose email
                website=data.get("url"),
                address=" ".join(loc.get("display_address", [])) if loc.get("display_address") else None,
                city=loc.get("city"),
                state=loc.get("state"),
                zip_code=loc.get("zip_code"),
                latitude=coords.get("latitude"),
                longitude=coords.get("longitude"),
                rating=data.get("rating"),
                review_count=data.get("review_count"),
                raw_data=data,
            )
            yield cand


if __name__ == "__main__":
    src = YelpSource()
    print(f"Source: {src.source_name}")
    print(f"Supported niches: {src.supported_niches}")
    print(f"API key configured: {bool(src.api_key)}")

    for lead in src.fetch("roofing", "CA", "Los Angeles", limit=2):
        print(f"  {lead.business_name} | {lead.city}, {lead.state} | rating: {lead.rating} | reviews: {lead.review_count}")