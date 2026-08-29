"""Self-hosted Google Maps/Business scraper — no Apify token needed.

Uses Playwright (headless Chromium) to scrape Google Maps search results.
"""

from __future__ import annotations
import dataclasses
import datetime
import json
import os
import re
import sqlite3
import time
from typing import Iterator, List, Optional, Dict, Any
from pathlib import Path

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


class GMapsScraper:
    """Self-hosted Google Maps scraper using Playwright."""

    source_name = "gmaps"
    BASE_URL = "https://www.google.com/maps/search/"

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

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._browser = None
        self._context = None

    @property
    def supported_niches(self) -> List[str]:
        return list(self.SEARCH_QUERIES.keys())

    def _launch_browser(self):
        """Lazy browser launch."""
        if self._browser is None:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            # Force regular chromium with explicit executable path
            self._browser = self._playwright.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
                executable_path="/root/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome",
            )
            self._context = self._browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
            )
        return self._context

    def _close_browser(self):
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if hasattr(self, "_playwright"):
            self._playwright.stop()
        self._browser = None
        self._context = None

    def _extract_phone(self, text: str) -> Optional[str]:
        if not text:
            return None
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

    def _parse_address(self, address: str) -> Dict[str, Optional[str]]:
        """Parse address into components."""
        result = {"city": None, "state": None, "zip_code": None}
        if not address:
            return result
        # Simple US address parse: "123 Main St, City, ST 12345"
        parts = [p.strip() for p in address.split(",")]
        if len(parts) >= 3:
            result["city"] = parts[-3]
            # Last part: "ST 12345"
            last = parts[-1]
            state_match = re.match(r'([A-Z]{2})\s+(\d{5})', last)
            if state_match:
                result["state"] = state_match.group(1)
                result["zip_code"] = state_match.group(2)
        return result

    def fetch(self, niche: str, state: str, city: Optional[str] = None, limit: int = 100) -> Iterator[LeadCandidate]:
        context = self._launch_browser()
        page = context.new_page()

        queries = self.SEARCH_QUERIES.get(niche, [niche])
        location = f"{city}, {state}" if city else state

        count = 0
        try:
            for query in queries:
                if count >= limit:
                    break

                search_url = f"{self.BASE_URL}{query}+{location}".replace(" ", "+")
                page.goto(search_url, wait_until="networkidle", timeout=60000)
                time.sleep(3)  # let results load

                # Scroll to load more results
                for _ in range(min(5, (limit - count) // 20 + 1)):
                    page.mouse.wheel(0, 3000)
                    time.sleep(1)

                # Extract result cards
                cards = page.query_selector_all('[role="article"]')
                for card in cards:
                    if count >= limit:
                        break

                    try:
                        # Click to open detail panel
                        card.click()
                        time.sleep(1.5)

                        # Wait for detail panel
                        page.wait_for_selector('[role="main"]', timeout=10000)

                        # Extract data from detail panel
                        name_el = page.query_selector('h1[data-attrid="title"]') or page.query_selector('h1.DUwDvf')
                        name = name_el.inner_text().strip() if name_el else ""

                        # Address
                        addr_el = page.query_selector('[data-item-id="address"]') or page.query_selector('.Io6YTe.fontBodyMedium')
                        address = addr_el.inner_text().strip() if addr_el else ""

                        # Phone
                        phone_el = page.query_selector('[data-item-id^="phone"]') or page.query_selector('button[data-item-id*="phone"]')
                        phone = phone_el.inner_text().strip() if phone_el else None

                        # Website
                        web_el = page.query_selector('[data-item-id="authority"]') or page.query_selector('a[data-item-id="authority"]')
                        website = web_el.get_attribute("href") if web_el else None

                        # Rating
                        rating_el = page.query_selector('[role="img"][aria-label*="stars"]') or page.query_selector('.F7nice span')
                        rating = None
                        if rating_el:
                            aria = rating_el.get_attribute("aria-label") or ""
                            r_match = re.search(r'([\d.]+)\s*(?:out of|stars?)', aria)
                            if r_match:
                                rating = float(r_match.group(1))

                        # Review count
                        review_el = page.query_selector('button[data-item-id="reviews"]') or page.query_selector('span[aria-label*="review"]')
                        review_count = None
                        if review_el:
                            text = review_el.inner_text() or review_el.get_attribute("aria-label") or ""
                            rc_match = re.search(r'([\d,]+)\s*reviews?', text, re.I)
                            if rc_match:
                                review_count = int(rc_match.group(1).replace(",", ""))

                        # Categories
                        cat_els = page.query_selector_all('.DkEaL')
                        categories = [el.inner_text().strip() for el in cat_els if el.inner_text().strip()]

                        if not name:
                            continue

                        # Parse address components
                        addr_parts = self._parse_address(address)

                        # Generate source_ref from place ID if available, else name+address
                        place_id = ""
                        try:
                            # Try to get place ID from URL
                            url = page.url
                            if "place/" in url:
                                place_id = url.split("place/")[-1].split("/")[0]
                        except Exception:
                            pass

                        source_ref = f"gmaps:{place_id or name.replace(' ', '_').lower()}"

                        cand = LeadCandidate(
                            source=self.source_name,
                            source_ref=source_ref,
                            niche=niche,
                            sub_niche=categories[0].lower().replace(" ", "_") if categories else niche,
                            business_name=name,
                            phone=self._extract_phone(phone or "") or phone,
                            email=self._extract_email(address + " " + (website or "")),
                            website=website,
                            address=address,
                            city=addr_parts["city"] or city,
                            state=addr_parts["state"] or state.upper(),
                            zip_code=addr_parts["zip_code"],
                            rating=rating,
                            review_count=review_count,
                            raw_data={
                                "query": query,
                                "location": location,
                                "categories": categories,
                                "place_id": place_id,
                                "maps_url": page.url,
                            },
                        )
                        count += 1
                        yield cand

                    except Exception:
                        continue

        finally:
            page.close()
            self._close_browser()


if __name__ == "__main__":
    scraper = GMapsScraper(headless=True)
    print(f"Source: {scraper.source_name}")
    print(f"Supported niches: {scraper.supported_niches}")

    # Test with 1 result
    for lead in scraper.fetch("roofing", "CA", "Los Angeles", limit=1):
        print(f"  {lead.business_name} | {lead.city}, {lead.state} | phone: {lead.phone} | rating: {lead.rating}")