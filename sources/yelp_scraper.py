"""Self-hosted Yelp scraper — no API key needed.

Uses Playwright to scrape Yelp search results.
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


class YelpScraper:
    """Self-hosted Yelp scraper using Playwright."""

    source_name = "yelp_scraper"
    BASE_URL = "https://www.yelp.com/search"

    CATEGORY_MAP = {
        "roofing": "roofing",
        "hvac": "hvac",
        "plumbing": "plumbing",
        "electrical": "electricians",
        "solar": "solar_installation",
        "general_contractor": "general_contractors",
        "fence": "fences",
        "pool": "pool_cleaners",
        "concrete": "concrete",
        "windows": "windows_installation",
        "siding": "siding",
    }

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._browser = None
        self._context = None

    @property
    def supported_niches(self) -> List[str]:
        return list(self.CATEGORY_MAP.keys())

    def _launch_browser(self):
        if self._browser is None:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
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

    def fetch(self, niche: str, state: str, city: Optional[str] = None, limit: int = 100) -> Iterator[LeadCandidate]:
        context = self._launch_browser()
        page = context.new_page()

        category = self.CATEGORY_MAP.get(niche, niche)
        location = f"{city}, {state}" if city else state

        count = 0
        try:
            # Build search URL
            params = {
                "find_desc": category.replace("_", " "),
                "find_loc": location,
                "sortby": "rating",
            }
            import urllib.parse
            search_url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"

            page.goto(search_url, wait_until="networkidle", timeout=60000)
            time.sleep(3)

            # Handle potential popup
            try:
                page.wait_for_selector('[role="dialog"]', timeout=3000)
                page.keyboard.press("Escape")
                time.sleep(1)
            except Exception:
                pass

            # Extract business cards
            cards = page.query_selector_all('.container__09f24__mpR8_ .businessName__09f24__HG_pC')
            for card in cards:
                if count >= limit:
                    break

                try:
                    # Get the parent container
                    container = card.evaluate_handle("el => el.closest('.container__09f24__mpR8_')")
                    if not container:
                        continue

                    # Click to open business page
                    card.click()
                    time.sleep(2)

                    # Extract data from business page
                    name_el = page.query_selector('h1.y-css-187y3aj')
                    name = name_el.inner_text().strip() if name_el else ""

                    # Phone
                    phone_el = page.query_selector('[data-testid="phone-number"]') or page.query_selector('.y-css-16r9v9y')
                    phone = phone_el.inner_text().strip() if phone_el else None

                    # Website
                    web_el = page.query_selector('[data-testid="website-link"]') or page.query_selector('a.y-css-187y3aj[href*="http"]')
                    website = web_el.get_attribute("href") if web_el else None

                    # Address
                    addr_el = page.query_selector('[data-testid="address"]') or page.query_selector('.y-css-16r9v9y + div')
                    address = addr_el.inner_text().strip() if addr_el else ""

                    # Rating
                    rating_el = page.query_selector('[aria-label*="star rating"]') or page.query_selector('.y-css-12ly5yx')
                    rating = None
                    if rating_el:
                        aria = rating_el.get_attribute("aria-label") or ""
                        r_match = re.search(r'([\d.]+)', aria)
                        if r_match:
                            rating = float(r_match.group(1))

                    # Review count
                    review_el = page.query_selector('[data-testid="review-count"]') or page.query_selector('.y-css-16r9v9y')
                    review_count = None
                    if review_el:
                        text = review_el.inner_text() or ""
                        rc_match = re.search(r'([\d,]+)\s*reviews?', text, re.I)
                        if rc_match:
                            review_count = int(rc_match.group(1).replace(",", ""))

                    if not name:
                        page.go_back()
                        time.sleep(1)
                        continue

                    # Parse address
                    city_parsed = None
                    state_parsed = None
                    zip_code = None
                    if address:
                        parts = [p.strip() for p in address.split(",")]
                        if len(parts) >= 3:
                            city_parsed = parts[-3]
                            last = parts[-1]
                            state_match = re.match(r'([A-Z]{2})\s+(\d{5})', last)
                            if state_match:
                                state_parsed = state_match.group(1)
                                zip_code = state_match.group(2)

                    # Business ID from URL
                    biz_id = ""
                    try:
                        url = page.url
                        if "/biz/" in url:
                            biz_id = url.split("/biz/")[-1].split("?")[0].split("/")[0]
                    except Exception:
                        pass

                    cand = LeadCandidate(
                        source=self.source_name,
                        source_ref=f"yelp:{biz_id or name.replace(' ', '_').lower()}",
                        niche=niche,
                        sub_niche=category,
                        business_name=name,
                        phone=self._extract_phone(phone or "") or phone,
                        email=None,  # Yelp doesn't show email
                        website=website,
                        address=address,
                        city=city_parsed or city,
                        state=state_parsed or state.upper(),
                        zip_code=zip_code,
                        rating=rating,
                        review_count=review_count,
                        raw_data={
                            "category": category,
                            "location": location,
                            "biz_id": biz_id,
                            "yelp_url": page.url,
                        },
                    )
                    count += 1
                    yield cand

                    page.go_back()
                    time.sleep(1.5)

                except Exception:
                    try:
                        page.go_back()
                        time.sleep(1)
                    except Exception:
                        pass
                    continue

        finally:
            page.close()
            self._close_browser()


if __name__ == "__main__":
    scraper = YelpScraper(headless=True)
    print(f"Source: {scraper.source_name}")
    print(f"Supported niches: {scraper.supported_niches}")

    for lead in scraper.fetch("roofing", "CA", "Los Angeles", limit=1):
        print(f"  {lead.business_name} | {lead.city}, {lead.state} | rating: {lead.rating} | reviews: {lead.review_count}")