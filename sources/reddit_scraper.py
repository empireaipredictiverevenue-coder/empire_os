"""Self-hosted Reddit scraper — no API credentials needed.

Uses Playwright to scrape Reddit search results for contractor mentions.
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
import urllib.parse

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


class RedditScraper:
    """Self-hosted Reddit scraper using Playwright."""

    source_name = "reddit_scraper"
    BASE_URL = "https://www.reddit.com"

    SUBREDDITS = {
        "roofing": ["roofing", "HomeImprovement", "AskContractors", "Construction"],
        "hvac": ["HVAC", "HomeImprovement", "AskContractors", "homeowners"],
        "plumbing": ["Plumbing", "HomeImprovement", "AskContractors", "homeowners"],
        "electrical": ["electricians", "HomeImprovement", "AskContractors", "Construction"],
        "solar": ["solar", "SolarDIY", "renewableenergy", "HomeImprovement"],
        "general_contractor": ["HomeImprovement", "Construction", "AskContractors", "renovation"],
        "fence": ["fencing", "HomeImprovement", "landscaping"],
        "pool": ["pools", "HomeImprovement", "PoolOwners"],
        "concrete": ["Concrete", "Construction", "HomeImprovement"],
        "windows": ["Windows", "HomeImprovement", "Construction"],
        "siding": ["siding", "HomeImprovement", "Construction"],
    }

    BUSINESS_KEYWORDS = [
        "recommend", "recommendation", "contractor", "company", "business",
        "service", "hire", "hired", "used", "call", "contact", "quote",
        "estimate", "license", "insured", "bonded", "owner", "owner operated",
    ]

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._browser = None
        self._context = None

    @property
    def supported_niches(self) -> List[str]:
        return list(self.SUBREDDITS.keys())

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

    def _extract_business_info(self, text: str, niche: str) -> Optional[Dict]:
        phone = self._extract_phone(text)

        name_patterns = [
            r'(?:recommend|hired|used|call|contact)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b',
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\s+(?:Roofing|HVAC|Plumbing|Electrical|Solar|Construction|Contractors?|Services?))\b',
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\s+(?:Inc|LLC|Ltd|Corp|Company))\b',
        ]
        business_name = None
        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                business_name = match.group(1).strip()
                break

        city_match = re.search(r'\b(in|near|around)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', text)
        city = city_match.group(2) if city_match else None

        if not business_name and not phone:
            return None

        return {
            "business_name": business_name or f"Reddit {niche.title()} Mention",
            "phone": phone,
            "city": city,
        }

    def fetch(self, niche: str, state: str, city: Optional[str] = None, limit: int = 100) -> Iterator[LeadCandidate]:
        context = self._launch_browser()
        page = context.new_page()

        subreddits = self.SUBREDDITS.get(niche, [niche])
        queries = [
            f"{niche} contractor {state}",
            f"{niche} recommendation {state}",
            f"best {niche} {state}",
            f"{niche} company {state}",
        ]
        if city:
            queries = [f"{q} {city}" for q in queries]

        count = 0
        seen_names = set()

        try:
            for subreddit in subreddits:
                if count >= limit:
                    break
                for query in queries:
                    if count >= limit:
                        break

                    search_url = f"{self.BASE_URL}/r/{subreddit}/search/?q={urllib.parse.quote(query)}&restrict_sr=1&sort=relevance&t=month"
                    page.goto(search_url, wait_until="networkidle", timeout=60000)
                    time.sleep(3)

                    # Scroll for more results
                    for _ in range(3):
                        page.mouse.wheel(0, 3000)
                        time.sleep(1)

                    # Extract posts
                    posts = page.query_selector_all('[data-testid="post-container"]')
                    for post in posts:
                        if count >= limit:
                            break

                        try:
                            # Get post text
                            title_el = post.query_selector('[data-testid="post-title"]') or post.query_selector('h3')
                            title = title_el.inner_text().strip() if title_el else ""

                            body_el = post.query_selector('[data-testid="post-content"]') or post.query_selector('.md')
                            body = body_el.inner_text().strip() if body_el else ""

                            text = f"{title} {body}"[:2000]

                            # Check for business keywords
                            if not any(kw.lower() in text.lower() for kw in self.BUSINESS_KEYWORDS):
                                continue

                            extracted = self._extract_business_info(text, niche)
                            if not extracted:
                                continue

                            biz_name = extracted["business_name"]
                            if biz_name in seen_names:
                                continue
                            seen_names.add(biz_name)

                            # Get post ID for source_ref
                            post_id = ""
                            try:
                                link_el = post.query_selector('a[data-testid="post-title"]') or post.query_selector('a[href*="/comments/"]')
                                if link_el:
                                    href = link_el.get_attribute("href")
                                    if "/comments/" in href:
                                        post_id = href.split("/comments/")[1].split("/")[0]
                            except Exception:
                                pass

                            cand = LeadCandidate(
                                source=self.source_name,
                                source_ref=f"reddit:{post_id or biz_name.replace(' ', '_').lower()}",
                                niche=niche,
                                sub_niche=niche,
                                business_name=biz_name,
                                phone=extracted["phone"],
                                email=None,
                                website=None,
                                address=None,
                                city=extracted["city"] or city,
                                state=state.upper(),
                                zip_code=None,
                                raw_data={
                                    "subreddit": subreddit,
                                    "query": query,
                                    "title": title,
                                    "body": body[:500],
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
    scraper = RedditScraper(headless=True)
    print(f"Source: {scraper.source_name}")
    print(f"Supported niches: {scraper.supported_niches}")

    for lead in scraper.fetch("roofing", "CA", "Los Angeles", limit=1):
        print(f"  {lead.business_name} | {lead.city}, {lead.state} | phone: {lead.phone}")