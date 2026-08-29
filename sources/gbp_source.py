"""Google Business Profile source via Apify API.

Uses Apify's Google Maps Scraper to fetch local business leads.
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


class GBPSource:
    """Google Business Profile via Apify Google Maps Scraper."""

    source_name = "gbp"
    APIFY_API_BASE = "https://api.apify.com/v2"
    ACTOR_ID = "compass~google-maps-scraper"  # public Google Maps scraper

    SEARCH_QUERIES = {
        "roofing": ["roofing contractor", "roof repair", "roof installation", "commercial roofing"],
        "hvac": ["HVAC contractor", "air conditioning repair", "heating repair", "furnace installation"],
        "plumbing": ["plumber", "plumbing contractor", "emergency plumber", "drain cleaning"],
        "electrical": ["electrician", "electrical contractor", "electrical repair", "panel upgrade"],
        "solar": ["solar installer", "solar panel installation", "solar company", "PV installation"],
        "general_contractor": ["general contractor", "home renovation", "remodeling contractor", "construction company"],
        "fence": ["fence contractor", "fence installation", "fencing company"],
        "pool": ["pool builder", "pool contractor", "pool installation", "spa installation"],
        "concrete": ["concrete contractor", "concrete driveway", "foundation repair"],
        "windows": ["window installation", "window replacement", "window contractor"],
        "siding": ["siding contractor", "siding installation", "stucco contractor"],
    }

    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or os.environ.get("APIFY_API_TOKEN")

    @property
    def supported_niches(self) -> List[str]:
        return list(self.SEARCH_QUERIES.keys())

    def _run_actor(self, query: str, location: str, max_results: int = 50) -> List[Dict]:
        """Run Apify actor and return results."""
        if not self.api_token:
            return []

        # Start actor run
        run_url = f"{self.APIFY_API_BASE}/acts/{self.ACTOR_ID}/runs?token={self.api_token}"
        payload = json.dumps({
            "searchStringsArray": [f"{query} {location}"],
            "maxResults": max_results,
            "language": "en",
            "countryCode": "US",
            "customMapFunction": """
                function mapItem(item) {
                    return {
                        placeId: item.placeId,
                        name: item.name,
                        address: item.address,
                        phone: item.phone,
                        website: item.website,
                        email: item.email,
                        rating: item.rating,
                        reviewsCount: item.reviewsCount,
                        categories: item.categories,
                        location: item.location,
                        placeUrl: item.placeUrl,
                    };
                }
            """,
        }).encode()

        try:
            req = urllib.request.Request(run_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                run_data = json.loads(resp.read().decode())
        except Exception as e:
            return []

        run_id = run_data.get("data", {}).get("id")
        if not run_id:
            return []

        # Poll for completion
        for _ in range(60):  # max 5 minutes
            time.sleep(5)
            status_url = f"{self.APIFY_API_BASE}/actor-runs/{run_id}?token={self.api_token}"
            try:
                with urllib.request.urlopen(status_url, timeout=10) as resp:
                    status_data = json.loads(resp.read().decode())
                status = status_data.get("data", {}).get("status")
                if status == "SUCCEEDED":
                    break
                elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
                    return []
            except Exception:
                pass
        else:
            return []

        # Fetch results
        dataset_id = status_data.get("data", {}).get("defaultDatasetId")
        if not dataset_id:
            return []

        results_url = f"{self.APIFY_API_BASE}/datasets/{dataset_id}/items?token={self.api_token}&clean=true&limit={max_results}"
        try:
            with urllib.request.urlopen(results_url, timeout=30) as resp:
                items = json.loads(resp.read().decode())
            return items
        except Exception:
            return []

    def fetch(self, niche: str, state: str, city: Optional[str] = None, limit: int = 100) -> Iterator[LeadCandidate]:
        if not self.api_token:
            # Mock for testing without token
            yield LeadCandidate(
                source=self.source_name,
                source_ref=f"gbp:mock:{niche}:{state}",
                niche=niche,
                sub_niche=niche,
                business_name=f"Mock {niche.title()} Business",
                phone="(555) 123-4567",
                website="https://example.com",
                address="123 Main St",
                city=city or "Sample City",
                state=state.upper(),
                zip_code="12345",
                rating=4.5,
                review_count=100,
                raw_data={"mock": True, "niche": niche, "state": state},
            )
            return

        queries = self.SEARCH_QUERIES.get(niche, [niche])
        location = f"{city}, {state}" if city else state

        count = 0
        for query in queries:
            if count >= limit:
                break

            results = self._run_actor(query, location, max_results=min(limit - count, 50))
            for item in results:
                if count >= limit:
                    break

                # Extract data from Apify result
                place_id = item.get("placeId", "")
                name = item.get("name", "")
                address = item.get("address", "")
                phone = item.get("phone")
                website = item.get("website")
                email = item.get("email")
                rating = item.get("rating")
                reviews = item.get("reviewsCount")
                categories = item.get("categories", [])
                location_data = item.get("location", {})

                # Parse address components
                city_parsed = None
                zip_code = None
                if address:
                    # Simple parse - real impl would use proper geocoding
                    parts = address.split(", ")
                    if len(parts) >= 3:
                        city_parsed = parts[-3]
                        zip_match = re.search(r'\b\d{5}\b', parts[-1])
                        if zip_match:
                            zip_code = zip_match.group()

                cand = LeadCandidate(
                    source=self.source_name,
                    source_ref=f"gbp:{place_id}",
                    niche=niche,
                    sub_niche=categories[0].lower().replace(" ", "_") if categories else niche,
                    business_name=name,
                    phone=phone,
                    email=email,
                    website=website,
                    address=address,
                    city=city_parsed or city,
                    state=state.upper(),
                    zip_code=zip_code,
                    latitude=location_data.get("lat") if location_data else None,
                    longitude=location_data.get("lng") if location_data else None,
                    rating=float(rating) if rating else None,
                    review_count=reviews,
                    raw_data=item,
                )
                count += 1
                yield cand


if __name__ == "__main__":
    src = GBPSource()
    print(f"Source: {src.source_name}")
    print(f"Supported niches: {src.supported_niches}")
    print(f"API token configured: {bool(src.api_token)}")

    for lead in src.fetch("roofing", "CA", "Los Angeles", limit=2):
        print(f"  {lead.business_name} | {lead.city}, {lead.state} | rating: {lead.rating}")