"""
Registry Scraper — pulls company info from public business registries.

Built-in sources:
- BBB (Better Business Bureau) — public search, no key
- SunBiz (Florida Secretary of State) — free, authoritative

Each source returns a normalised RegistryRecord. Designed to be cheap,
parallelisable, and respectful of robots.txt / rate limits.
"""
from __future__ import annotations

import logging
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger("registry_scraper")


USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 "
    "(Empire-OS/3.0; +https://empire-os.local)"
)


@dataclass
class RegistryRecord:
    """One record from a registry."""
    company_name: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""
    owner_name: str = ""
    source: str = ""
    source_url: str = ""
    confidence: float = 0.0
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RegistryResult:
    """Outcome of a registry search."""
    records: list = field(default_factory=list)
    sources_tried: list = field(default_factory=list)
    error: str = ""

    @property
    def best(self) -> Optional[RegistryRecord]:
        if not self.records:
            return None
        return max(self.records, key=lambda r: r.confidence)


class RegistryScraper:
    """Queries public business registries for company info."""

    def __init__(self, timeout: int = 10, rate_limit_seconds: float = 1.0):
        self.timeout = timeout
        self.rate_limit = rate_limit_seconds

    def search(self, company_name: str, state: str = "") -> RegistryResult:
        """Try multiple registries, return all records found."""
        result = RegistryResult()
        if not company_name:
            result.error = "no company name"
            return result

        # BBB search
        try:
            time.sleep(self.rate_limit)
            recs = self._search_bbb(company_name, state)
            result.records.extend(recs)
            result.sources_tried.append("bbb")
        except Exception as e:
            logger.debug("BBB search failed: %s", e)

        # SunBiz (Florida-specific, free, authoritative)
        if not state or state.upper() in ("FL", "FLORIDA"):
            try:
                time.sleep(self.rate_limit)
                rec = self._search_sunbiz(company_name)
                if rec:
                    result.records.append(rec)
                    result.sources_tried.append("sunbiz")
            except Exception as e:
                logger.debug("SunBiz search failed: %s", e)

        return result

    def _search_bbb(self, company_name: str, state: str = "") -> list:
        """Query BBB's public search endpoint."""
        records = []
        params = {
            "find_text": company_name,
            "find_type": "Business",
            "find_loc": state,
            "find_entity": "All",
        }
        url = "https://www.bbb.org/search?" + urllib.parse.urlencode(params)
        html = self._fetch(url)
        if not html:
            return records

        # Parse BBB result blocks
        block_pat = re.compile(
            r'<div[^>]*class="[^"]*result[^"]*"[^>]*>(.*?)</div>\s*</div>',
            re.S | re.I,
        )
        for m in block_pat.finditer(html):
            block = m.group(1)
            if len(records) >= 5:
                break
            name_m = re.search(r"<h3[^>]*>(.*?)</h3>", block, re.S)
            if not name_m:
                continue
            phone_m = re.search(r"(\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})", block)
            addr_m = re.search(
                r'<p[^>]*class="[^"]*address[^"]*"[^>]*>(.*?)</p>',
                block, re.S,
            )
            records.append(RegistryRecord(
                company_name=re.sub(r"<[^>]+>", "", name_m.group(1)).strip(),
                phone=phone_m.group(1).strip() if phone_m else "",
                address=re.sub(r"<[^>]+>", "", addr_m.group(1)).strip() if addr_m else "",
                state=state,
                source="bbb",
                source_url=url,
                confidence=0.85,
                raw={"snippet": block[:500]},
            ))
        return records

    def _search_sunbiz(self, company_name: str) -> Optional[RegistryRecord]:
        """Query Florida's SunBiz registry (simplified)."""
        url = "https://search.sunbiz.org/Inquiry/corporationsearch/SearchResults"
        params = {"searchName": company_name, "searchType": "startsWith"}
        encoded = urllib.parse.urlencode(params)
        html = self._fetch(f"{url}?{encoded}")
        if not html:
            return None
        # Look for the first matching entity
        name_m = re.search(r"<td[^>]*>([^<]*LLC[^<]*)</td>", html, re.I)
        if not name_m:
            name_m = re.search(r"<td[^>]*>([^<]*Inc[^<]*)</td>", html, re.I)
        if name_m:
            return RegistryRecord(
                company_name=name_m.group(1).strip(),
                state="FL",
                source="sunbiz",
                source_url=url,
                confidence=0.95,
            )
        return None

    def _fetch(self, url: str) -> Optional[str]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                ct = resp.headers.get("content-type", "")
                if "html" not in ct.lower() and "json" not in ct.lower():
                    return None
                return resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            logger.debug("fetch failed for %s: %s", url, e)
            return None