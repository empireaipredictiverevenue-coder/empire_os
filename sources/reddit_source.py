"""Reddit source for local contractor leads.

Scans subreddits for contractor discussions, recommendations, service requests.
Uses Reddit API (public) or Pushshift for historical data.
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


class RedditSource:
    """Reddit API — scan for contractor mentions, recommendations, service requests."""

    source_name = "reddit"
    API_BASE = "https://www.reddit.com"
    USER_AGENT = "EmpireOS/1.0 (+https://empire-ai.co.uk)"

    # Subreddits by niche
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

    # Keywords that indicate a business mention or recommendation
    BUSINESS_KEYWORDS = [
        "recommend", "recommendation", "contractor", "company", "business",
        "service", "hire", "hired", "used", "call", "contact", "quote",
        "estimate", "license", "insured", "bonded", "owner", "owner operated",
    ]

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        self.client_id = client_id or os.environ.get("REDDIT_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("REDDIT_CLIENT_SECRET")
        self._access_token = None

    @property
    def supported_niches(self) -> List[str]:
        return list(self.SUBREDDITS.keys())

    def _get_token(self) -> Optional[str]:
        if self._access_token:
            return self._access_token
        if not self.client_id or not self.client_secret:
            return None
        auth = urllib.parse.urlencode({"grant_type": "client_credentials"})
        url = "https://www.reddit.com/api/v1/access_token"
        headers = {"User-Agent": self.USER_AGENT}
        try:
            req = urllib.request.Request(
                url, data=auth.encode(), headers=headers, method="POST"
            )
            # Add basic auth
            import base64
            creds = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
            req.add_header("Authorization", f"Basic {creds}")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            self._access_token = data.get("access_token")
            return self._access_token
        except Exception:
            return None

    def _search_subreddit(self, subreddit: str, query: str, limit: int = 25) -> List[Dict]:
        token = self._get_token()
        headers = {"User-Agent": self.USER_AGENT}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        params = {
            "q": query,
            "restrict_sr": "true",
            "sort": "relevance",
            "limit": limit,
            "t": "month",
        }
        url = f"{self.API_BASE}/r/{subreddit}/search.json?{urllib.parse.urlencode(params)}"

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode())
            return data.get("data", {}).get("children", [])
        except Exception:
            return []

    def _extract_business_info(self, text: str, niche: str) -> Optional[Dict]:
        """Extract business name, phone, location from reddit post/comment."""
        # Look for patterns like "Company Name - (555) 123-4567" or "Call John at 555-123-4567"
        phone_match = re.search(r'(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})', text)
        phone = f"({phone_match.group(1)}) {phone_match.group(2)}-{phone_match.group(3)}" if phone_match else None

        # Look for business name patterns
        # "I recommend X Company" or "X Company did great work" or "Call X Company"
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

        # Location hints
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

        for subreddit in subreddits:
            if count >= limit:
                break
            for query in queries:
                if count >= limit:
                    break

                results = self._search_subreddit(subreddit, query, limit=min(25, limit - count))
                for item in results:
                    if count >= limit:
                        break

                    post = item.get("data", {})
                    text = f"{post.get('title', '')} {post.get('selftext', '')}"
                    text = text[:2000]  # limit text length

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

                    cand = LeadCandidate(
                        source=self.source_name,
                        source_ref=f"reddit:{post.get('id', '')}",
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
                            "title": post.get("title", ""),
                            "score": post.get("score", 0),
                            "permalink": post.get("permalink", ""),
                            "created_utc": post.get("created_utc"),
                        },
                    )
                    count += 1
                    yield cand


if __name__ == "__main__":
    src = RedditSource()
    print(f"Source: {src.source_name}")
    print(f"Supported niches: {src.supported_niches}")
    print(f"API credentials configured: {bool(src.client_id and src.client_secret)}")

    for lead in src.fetch("roofing", "CA", "Los Angeles", limit=2):
        print(f"  {lead.business_name} | {lead.city}, {lead.state} | phone: {lead.phone}")