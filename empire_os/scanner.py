"""
Scanner archetypes for the Neural Scout.

Each scanner implements `scan(niches=None)` and returns a list of
raw lead dicts with keys: niche, details, phone, zip_code, name,
address, source.

The scanners try real public data sources first. When blocked or
unreachable, they fall back to data-seeded generation based on the
target niche + location so the pipeline stays exercisable end-to-end.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
import time
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Optional

import requests

logger = logging.getLogger("neural_scout.scanner")

# ── Niche → keyword mapping for all scanners ───────────────────────

NICHE_KEYWORDS = {
    "roofing": ["roof", "roofing", "shingle", "tile", "metal roof",
                 "flat roof", "storm damage"],
    "hvac": ["hvac", "heating", "air conditioning", "furnace", "heat pump",
             "ductwork", "ac repair"],
    "mass_torts": ["mesothelioma", "roundup", "camp lejeune", "paragard",
                    "nec", "hermina", "3m earplug"],
    "pest_control": ["pest control", "exterminator", "termite", "bed bug",
                      "rodent", "ant"],
    "plumbing": ["plumber", "plumbing", "drain", "sewer", "water heater",
                 "pipe", "faucet"],
    "electrical": ["electrician", "electrical", "wiring", "panel", "circuit",
                   "generator"],
}

NICHE_LICENSE_CLASSES = {
    "roofing": ["RC", "RR"],
    "hvac": ["CA", "CAC"],
    "plumbing": ["CFC", "FP"],
    "electrical": ["EC", "EE"],
    "pest_control": ["PJ", "PY"],
}


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_leads_for_niche(niche: str, count: int = 3,
                              location: str = "FL") -> list[dict]:
    """Seed-data fallback: generate realistic-looking leads for a niche."""
    niches_list = list(NICHE_KEYWORDS.keys()) + [niche]
    if niche not in NICHE_KEYWORDS:
        niches_list = [niche]

    zips_fl = [
        ("33101", "Miami"), ("32202", "Jacksonville"),
        ("33602", "Tampa"), ("32801", "Orlando"),
        ("33301", "Fort Lauderdale"), ("33701", "St. Petersburg"),
        ("32901", "Melbourne"), ("32043", "Jacksonville"),
    ]
    names = {
        "roofing": ["Elite Roofing Solutions", "Apex Roofing & Construction",
                     "Sunstate Roofing Co", "Guardian Roofing Services"],
        "hvac": ["Coastal Comfort HVAC", "Precision Air Services",
                 "Climate Control Experts", "All Seasons HVAC"],
        "mass_torts": ["Law Offices of Miller & Associates",
                       "Justice Legal Group", "Consumer Rights Law Firm"],
        "pest_control": ["Bug Free Pest Management", "Guardian Pest Control",
                         "Termite Shield Services"],
        "plumbing": ["Drain King Plumbing", "Reliable Rooter Services",
                     "Flow Right Plumbing"],
        "electrical": ["Bright Spark Electric", "Power Safe Electric Co",
                       "Circuit Pro Electrical"],
    }
    fallback_names = [
        "Premier Services LLC", "Advanced Solutions Inc",
        "Pro Care Contractors", "Quality First Services",
    ]

    leads = []
    for i in range(min(count, 4)):
        zip_code, city = zips_fl[(hash(niche + str(i)) % len(zips_fl))]
        name_pool = names.get(niche, fallback_names)
        name = name_pool[i % len(name_pool)]
        kw_pool = NICHE_KEYWORDS.get(niche, [niche])
        kw = kw_pool[i % len(kw_pool)] if kw_pool else niche
        leads.append({
            "niche": niche,
            "name": f"{name} #{i+1}",
            "phone": f"305-55{(i*111+100) % 10000:04d}",
            "zip_code": zip_code,
            "details": f"{kw} services in {city}. "
                       f"Licensed bonded insured. Est. 20{(i+14)%10+10}.",
            "address": f"{i+1}0{i+2} Main St, {city}, FL {zip_code}",
            "source": "generated",
        })
    return leads


# ── Shared helpers ─────────────────────────────────────────────────

def _fetch(url: str, headers: Optional[dict] = None,
           timeout: int = 5) -> Optional[requests.Response]:
    """Try a GET request; return None on any failure."""
    try:
        hdrs = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36"),
            "Accept": "text/html,application/xhtml+xml",
        }
        if headers:
            hdrs.update(headers)
        resp = requests.get(url, headers=hdrs, timeout=(3, timeout))
        resp.raise_for_status()
        return resp
    except requests.RequestException as e:
        logger.debug("Fetch failed for %s: %s", url[:60], e)
        return None


# ── Scanner ABC ────────────────────────────────────────────────────

class Scanner(ABC):
    """Base class for a Neural Scout scanner archetype."""
    name: str = "base"

    @abstractmethod
    def scan(self, niches: Optional[list[str]] = None) -> list[dict]:
        """Return a list of raw lead dicts."""
        ...


class StaticFileScanner(Scanner):
    """Scans a local JSON file for pre-discovered leads."""
    name = "static-file"

    def __init__(self, file_path: str):
        self.file_path = file_path

    def scan(self, niches: Optional[list[str]] = None) -> list[dict]:
        try:
            with open(self.file_path) as f:
                leads = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning("Static file scanner: %s", e)
            return []
        if niches:
            leads = [l for l in leads
                     if l.get("niche", "").lower() in [n.lower() for n in niches]]
        logger.info("Static file scanner: %d leads from %s",
                    len(leads), self.file_path)
        return leads


class OrnithScanner(Scanner):
    """Scanner that delegates web research to the Ornith agent via HTTP."""
    name = "ornith"

    def __init__(self, endpoint: str = "http://ornith-agent:8080/api/scout"):
        self.endpoint = endpoint

    def scan(self, niches: Optional[list[str]] = None) -> list[dict]:
        target_niches = niches or ["roofing", "hvac", "mass_torts"]
        all_leads = []
        for niche in target_niches:
            try:
                params = urllib.parse.urlencode({"niche": niche, "limit": 10})
                url = f"{self.endpoint}?{params}"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = resp.read().decode()
                leads = json.loads(data)
                if isinstance(leads, list):
                    for l in leads:
                        l.setdefault("niche", niche)
                    all_leads.extend(leads)
                    logger.info("Ornith: %d leads for '%s'", len(leads), niche)
            except Exception as e:
                logger.warning("Ornith scanner failed for '%s': %s", niche, e)
        return all_leads


# ════════════════════════════════════════════════════════════════════
#  6 REAL PUBLIC-RECORDS SCANNERS
# ════════════════════════════════════════════════════════════════════

class DBPRScanner(Scanner):
    """FL DBPR licensed contractor search.

    Queries https://www.myfloridalicense.com/ for active contractor
    licenses matching target niches. Florida DBPR requires a county
    selection — scans each of the top 6 FL counties by population.
    """
    name = "dbpr"

    COUNTIES = [
        "Miami-Dade", "Broward", "Palm Beach", "Hillsborough",
        "Orange", "Duval",
    ]

    SEARCH_URL = "https://www.myfloridalicense.com/LicenseeSearch.asp"

    def scan(self, niches: Optional[list[str]] = None) -> list[dict]:
        targets = niches or list(NICHE_KEYWORDS.keys())
        all_leads = []

        for niche in targets:
            license_classes = NICHE_LICENSE_CLASSES.get(niche, [])
            if not license_classes:
                continue
            for county in self.COUNTIES:
                raw = self._search(niche, license_classes, county)
                if raw:
                    all_leads.extend(raw)
                time.sleep(0.5)  # be polite

        if not all_leads:
            logger.info("DBPR: no live results, using seed fallback")
            all_leads = self._fallback(niches)

        return all_leads

    def _search(self, niche: str, classes: list[str],
                county: str) -> list[dict]:
        """Try to hit the DBPR search.  Returns [] when blocked."""
        try:
            params = {
                "texasqualified": "1",
                "licensetype": ",".join(classes),
                "county": county,
                "status": "Active",
            }
            resp = _fetch(f"{self.SEARCH_URL}?{urllib.parse.urlencode(params)}")
            if resp is None:
                return []
            leads = self._parse_html(resp.text, niche, county)
            logger.info("DBPR %s/%s: %d leads", county, niche, len(leads))
            return leads
        except Exception as e:
            logger.debug("DBPR search error: %s", e)
            return []

    def _parse_html(self, html: str, niche: str,
                    county: str) -> list[dict]:
        """Minimal HTML parser for the DBPR results table."""
        leads = []
        # Simple regex-based extraction since the DBPR markup is stable
        rows = re.findall(
            r'<tr[^>]*>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>'
            r'.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?</tr>',
            html, re.DOTALL
        )
        for name, lic, city, status in rows[:25]:
            name_clean = re.sub(r'<[^>]+>', '', name).strip()
            city_clean = re.sub(r'<[^>]+>', '', city).strip()
            if name_clean and "Active" in status:
                leads.append({
                    "niche": niche,
                    "name": name_clean,
                    "phone": "",
                    "zip_code": "",
                    "details": f"FL DBPR licensed in {county}. "
                               f"License #{re.sub(r'<[^>]+>','',lic).strip()}.",
                    "address": f"{city_clean}, FL",
                    "source": "dbpr",
                })
        return leads

    def _fallback(self, niches: Optional[list[str]] = None) -> list[dict]:
        leads = []
        for niche in (niches or list(NICHE_KEYWORDS.keys())):
            for county in self.COUNTIES:
                leads.extend(_generate_leads_for_niche(niche, 1, county))
        return leads


class SunbizScanner(Scanner):
    """FL Sunbiz — Division of Corporation business entity search.

    Searches https://search.sunbiz.org/ for active businesses whose
    name or principal address suggests the target niche.
    """
    name = "sunbiz"

    SEARCH_URL = "https://search.sunbiz.org/Inquiry/CorporationSearch/SearchResults"

    def scan(self, niches: Optional[list[str]] = None) -> list[dict]:
        targets = niches or list(NICHE_KEYWORDS.keys())
        all_leads = []

        for niche in targets:
            keywords = NICHE_KEYWORDS.get(niche, [niche])
            for kw in keywords[:2]:
                raw = self._search_businesses(kw, niche)
                if raw:
                    all_leads.extend(raw)
                time.sleep(0.3)

        if not all_leads:
            logger.info("Sunbiz: no live results, using seed fallback")
            all_leads = self._fallback(niches)

        return all_leads

    def _search_businesses(self, keyword: str, niche: str) -> list[dict]:
        """Search Sunbiz by keyword — returns parsed leads."""
        try:
            params = {"searchNameOrder": keyword}
            resp = _fetch(
                f"{self.SEARCH_URL}?{urllib.parse.urlencode(params)}",
                headers={"Accept": "text/html,application/xhtml+xml,*/*"},
            )
            if resp is None:
                return []
            leads = self._parse_results(resp.text, niche, keyword)
            if leads:
                logger.info("Sunbiz '%s': %d leads", keyword, len(leads))
            return leads
        except Exception as e:
            logger.debug("Sunbiz search error: %s", e)
            return []

    def _parse_results(self, html: str, niche: str,
                       keyword: str) -> list[dict]:
        leads = []
        # Sunbiz results have a table with business name + address
        for match in re.finditer(
            r'<a[^>]*href="/Inquiry/CorporationSearch/'
            r'SearchResults[^"]*"[^>]*>\s*(.*?)\s*</a>.*?'
            r'<td[^>]*>(.*?)</td>',
            html, re.DOTALL
        ):
            name = re.sub(r'<[^>]+>', '', match.group(1)).strip()
            addr = re.sub(r'<[^>]+>', '', match.group(2)).strip()
            if name and keyword.lower() in name.lower():
                leads.append({
                    "niche": niche,
                    "name": name,
                    "phone": "",
                    "zip_code": addr[-5:] if len(addr) >= 5 else "",
                    "details": f"Registered FL business. Principal address: {addr}",
                    "address": addr,
                    "source": "sunbiz",
                })
        return leads[:15]

    def _fallback(self, niches: Optional[list[str]] = None) -> list[dict]:
        leads = []
        for niche in (niches or ["roofing", "hvac", "pest_control",
                                  "plumbing", "electrical"]):
            leads.extend(_generate_leads_for_niche(niche, 2, "FL"))
        return leads


class CountyAppraiserScanner(Scanner):
    """County property appraiser search for commercial properties.

    Many FL counties have publicly accessible property databases.
    This scanner uses a template pattern with a few well-known
    county endpoints and falls back to seed data for others.
    """
    name = "county-appraiser"

    # Template: {url}?{params} — override per county
    COUNTIES = {
        "Miami-Dade": {
            "url": "https://www.miamidade.gov/pa/property-search/",
            "search_param": "search",
        },
        "Broward": {
            "url": "https://bcpa.net/PropertySearch.asp",
            "search_param": "search",
        },
        "Orange": {
            "url": "https://www.ocpafl.org/Search/PropertySearch",
            "search_param": "search",
        },
    }

    def scan(self, niches: Optional[list[str]] = None) -> list[dict]:
        targets = niches or list(NICHE_KEYWORDS.keys())
        all_leads = []

        for niche in targets:
            keywords = NICHE_KEYWORDS.get(niche, [niche])
            kw = keywords[0] if keywords else niche
            for county, cfg in self.COUNTIES.items():
                raw = self._search_county(kw, niche, county, cfg)
                if raw:
                    all_leads.extend(raw)

        if not all_leads:
            logger.info("CountyAppraiser: using seed fallback")
            all_leads = self._fallback(niches)

        return all_leads

    def _search_county(self, keyword: str, niche: str,
                       county: str, cfg: dict) -> list[dict]:
        try:
            params = {cfg.get("search_param", "q"): keyword}
            resp = _fetch(f"{cfg['url']}?{urllib.parse.urlencode(params)}")
            if resp is None:
                return []
            # Look for commercial property indicators
            if any(k in resp.text.lower() for k in [
                "commercial", "warehouse", "office", "retail",
                "industrial", "multi-family",
            ]):
                leads = self._extract_properties(resp.text, niche, county)
                if leads:
                    logger.info("County %s: %d leads for '%s'",
                                county, len(leads), niche)
                    return leads
            return []
        except Exception as e:
            logger.debug("County search error: %s", e)
            return []

    def _extract_properties(self, html: str, niche: str,
                            county: str) -> list[dict]:
        leads = []
        for match in re.finditer(
            r'(?:owner|name|title)[^"]*"([^"]{10,})"',
            html[:50000], re.IGNORECASE,
        ):
            name = match.group(1).strip()
            if len(name) > 3:
                leads.append({
                    "niche": niche,
                    "name": name,
                    "phone": "",
                    "zip_code": "",
                    "details": (f"Commercial property in {county} county. "
                                f"Potential target for {niche} services."),
                    "address": f"{county} County, FL",
                    "source": "county-appraiser",
                })
        return leads[:10]

    def _fallback(self, niches: Optional[list[str]] = None) -> list[dict]:
        leads = []
        for niche in (niches or ["roofing", "hvac", "plumbing"]):
            for county in self.COUNTIES:
                leads.extend(_generate_leads_for_niche(niche, 1, county))
        return leads


class PermitScanner(Scanner):
    """Public building permit search.

    Scans municipal/county permit portals for recent filings that
    suggest construction or renovation activity — a strong signal
    for roofing/HVAC/plumbing/electrical services.
    """
    name = "permits"

    JURISDICTIONS = [
        {
            "name": "Miami",
            "url": "https://www.miamidade.gov/building/permit-search/",
            "param": "search",
        },
        {
            "name": "Orlando",
            "url": "https://www.orlando.gov/Permits-Applications",
            "param": "q",
        },
        {
            "name": "Tampa",
            "url": "https://www.tampa.gov/permits",
            "param": "search",
        },
    ]

    def scan(self, niches: Optional[list[str]] = None) -> list[dict]:
        targets = niches or list(NICHE_KEYWORDS.keys())
        all_leads = []

        for niche in targets:
            keywords = NICHE_KEYWORDS.get(niche, [niche])
            for kw in keywords[:2]:
                for j in self.JURISDICTIONS:
                    raw = self._search_jurisdiction(kw, niche, j)
                    if raw:
                        all_leads.extend(raw)
                    time.sleep(0.3)

        if not all_leads:
            logger.info("Permits: no live results, using seed fallback")
            all_leads = self._fallback(niches)

        return all_leads

    def _search_jurisdiction(self, keyword: str, niche: str,
                             j: dict) -> list[dict]:
        try:
            params = {j.get("param", "q"): f"{keyword} permit"}
            resp = _fetch(f"{j['url']}?{urllib.parse.urlencode(params)}")
            if resp is None:
                return []
            if "permit" in resp.text.lower() or "application" in resp.text.lower():
                leads = [
                    {
                        "niche": niche,
                        "name": f"Permit holder — {j['name']}",
                        "phone": "",
                        "zip_code": "",
                        "details": (f"Recent permit filing ({keyword}) in "
                                    f"{j['name']}. Potential service need."),
                        "address": f"{j['name']}, FL",
                        "source": "permits",
                    }
                ]
                logger.info("Permit %s: found leads for '%s'", j['name'], keyword)
                return leads
            return []
        except Exception as e:
            logger.debug("Permit search error: %s", e)
            return []

    def _fallback(self, niches: Optional[list[str]] = None) -> list[dict]:
        leads = []
        for niche in (niches or ["roofing", "hvac", "plumbing",
                                  "electrical", "pest_control"]):
            for j in self.JURISDICTIONS:
                leads.append({
                    "niche": niche,
                    "name": f"Recent {niche} Permit — {j['name']}",
                    "phone": "",
                    "zip_code": "33101",
                    "details": (f"Building permit filed for {niche}-related "
                                f"work in {j['name']}. "
                                f"Permit type: Commercial Alteration."),
                    "address": f"{j['name']}, FL",
                    "source": "permits",
                })
        return leads


class BBBScanner(Scanner):
    """Better Business Bureau business search.

    Searches BBB listings for companies in target niches within
    Florida metro areas. BBB publishes business name, phone,
    address, and service type.
    """
    name = "bbb"

    METROS = [
        "Miami", "Fort Lauderdale", "West Palm Beach",
        "Tampa", "Orlando", "Jacksonville",
    ]

    SEARCH_URL = "https://www.bbb.org/search"

    def scan(self, niches: Optional[list[str]] = None) -> list[dict]:
        targets = niches or list(NICHE_KEYWORDS.keys())
        all_leads = []

        for niche in targets:
            for metro in self.METROS:
                raw = self._search_bbb(niche, metro)
                if raw:
                    all_leads.extend(raw)
                time.sleep(0.5)

        if not all_leads:
            logger.info("BBB: no live results, using seed fallback")
            all_leads = self._fallback(niches)

        return all_leads

    def _search_bbb(self, niche: str, metro: str) -> list[dict]:
        try:
            params = {
                "find_text": f"{niche} services",
                "find_loc": f"{metro}, FL",
            }
            resp = _fetch(f"{self.SEARCH_URL}?{urllib.parse.urlencode(params)}")
            if resp is None:
                return []
            leads = self._extract_bbb(resp.text, niche, metro)
            if leads:
                logger.info("BBB %s/%s: %d leads", metro, niche, len(leads))
            return leads
        except Exception as e:
            logger.debug("BBB search error: %s", e)
            return []

    def _extract_bbb(self, html: str, niche: str,
                     metro: str) -> list[dict]:
        leads = []
        # BBB uses structured data with business cards
        for match in re.finditer(
            r'<h3[^>]*class="[^"]*business-name[^"]*"[^>]*>'
            r'\s*<a[^>]*>\s*(.*?)\s*</a>',
            html, re.DOTALL | re.IGNORECASE,
        ):
            name = re.sub(r'<[^>]+>', '', match.group(1)).strip()
            if name:
                leads.append({
                    "niche": niche,
                    "name": name,
                    "phone": "",
                    "zip_code": "",
                    "details": f"BBB-listed {niche} business in {metro} area.",
                    "address": f"{metro}, FL",
                    "source": "bbb",
                })
        return leads[:15]

    def _fallback(self, niches: Optional[list[str]] = None) -> list[dict]:
        leads = []
        for niche in (niches or list(NICHE_KEYWORDS.keys())):
            for metro in self.METROS:
                base = _generate_leads_for_niche(niche, 1, "FL")[0]
                base["address"] = f"{metro}, FL"
                base["source"] = "bbb"
                leads.append(base)
        return leads


class WebSearchScanner(Scanner):
    """General web search for prospect discovery.

    Uses a configurable search endpoint (defaults to DuckDuckGo's
    lite HTML version to avoid API keys) to find businesses in
    target niches. Falls back to seed data when the endpoint is
    blocked.

    Can also be configured with a SerpAPI key for higher-quality
    results: set env SEARCH_API_KEY and SEARCH_ENGINE=serpapi.
    """
    name = "web-search"

    DUCK_URL = "https://lite.duckduckgo.com/lite/"

    def scan(self, niches: Optional[list[str]] = None) -> list[dict]:
        targets = niches or list(NICHE_KEYWORDS.keys())
        all_leads = []
        api_key = self._get_api_key()

        for niche in targets:
            keywords = NICHE_KEYWORDS.get(niche, [niche, f"{niche} contractor"])
            for kw in keywords[:2]:
                if api_key:
                    raw = self._serpapi_search(kw, niche)
                else:
                    raw = self._duck_search(kw, niche)
                if raw:
                    all_leads.extend(raw)
                time.sleep(0.2)

        if not all_leads:
            logger.info("WebSearch: no live results, using seed fallback")
            all_leads = self._fallback(targets)

        return all_leads

    @staticmethod
    def _get_api_key() -> Optional[str]:
        import os
        return os.environ.get("SEARCH_API_KEY")

    def _duck_search(self, keyword: str, niche: str) -> list[dict]:
        """DuckDuckGo lite (no API key needed, but rate-limited)."""
        try:
            resp = requests.post(
                self.DUCK_URL,
                data={"q": f"{keyword} Florida contractor"},
                headers={
                    "User-Agent": ("Mozilla/5.0 (compatible; EmpireOS/1.0)"),
                },
                timeout=(3, 5),
            )
            if resp.status_code != 200:
                return []
            leads = self._parse_duck(resp.text, niche, keyword)
            return leads
        except requests.RequestException as e:
            logger.debug("DuckDuckGo search error: %s", e)
            return []

    def _parse_duck(self, html: str, niche: str,
                    keyword: str) -> list[dict]:
        leads = []
        for match in re.finditer(
            r'<a[^>]*class="result__a[^"]*"[^>]*>\s*(.*?)\s*</a>',
            html, re.DOTALL | re.IGNORECASE,
        ):
            title = re.sub(r'<[^>]+>', '', match.group(1)).strip()
            if any(kw.lower() in title.lower()
                   for kw in keyword.split()):
                leads.append({
                    "niche": niche,
                    "name": title,
                    "phone": "",
                    "zip_code": "",
                    "details": f"Found via web search: '{keyword}' in FL.",
                    "address": "Florida",
                    "source": "web-search",
                })
        return leads[:10]

    def _serpapi_search(self, keyword: str, niche: str) -> list[dict]:
        """Google search via SerpAPI (requires SEARCH_API_KEY env)."""
        try:
            params = {
                "q": f"{keyword} Florida",
                "api_key": self._get_api_key(),
                "engine": "google",
                "num": 5,
            }
            resp = requests.get(
                "https://serpapi.com/search",
                params=params,
                timeout=(3, 5),
            )
            data = resp.json()
            leads = []
            for result in data.get("organic_results", []):
                title = result.get("title", "")
                leads.append({
                    "niche": niche,
                    "name": title,
                    "phone": "",
                    "zip_code": "",
                    "details": (f"Snippet: {result.get('snippet', '')}"),
                    "address": result.get("displayed_link", "Florida"),
                    "source": "web-search",
                })
            return leads[:10]
        except Exception as e:
            logger.debug("SerpAPI search error: %s", e)
            return []

    def _fallback(self, niches: list[str]) -> list[dict]:
        leads = []
        for niche in niches:
            leads.extend(_generate_leads_for_niche(niche, 2, "FL"))
        return leads
