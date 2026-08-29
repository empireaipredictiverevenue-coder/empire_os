"""
Empire OS v3 — Bing Local custom scraper (browser-rendered, no key)
====================================================================
Custom flow: render Bing search, parse algo cards, resolve Bing's
redirect wrapper (bing.com/ck/a?u=a1<base64>) to the real business
domain, extract phone/address from the snippet. Far higher yield +
verified domains vs the generic state-portal fill which JS-walls.

Yields empire_os.lead_sources.models.LeadCandidate.
"""
from __future__ import annotations
import base64
import datetime
import re
from typing import Iterator, List, Optional

from empire_os.lead_sources.models import LeadCandidate


class BingLocalScraper:
    source_name = "bing_local"
    # generic trade keywords -> bing query terms
    NICHE_TERMS = {
        "roofing": "roofing contractor",
        "hvac": "hvac contractor",
        "plumbing": "plumbing contractor",
        "electrical": "electrician",
        "solar": "solar installer",
        "general_contractor": "general contractor",
        "fence": "fence contractor",
        "pool": "pool service",
        "concrete": "concrete contractor",
        "windows": "window contractor",
        "siding": "siding contractor",
        "landscaping": "landscaping company",
        "painting": "painting contractor",
    }

    def __init__(self, headless: bool = True):
        self.headless = headless

    @property
    def supported_niches(self) -> List[str]:
        return list(self.NICHE_TERMS.keys())

    @staticmethod
    def _resolve_bing_redirect(href: Optional[str]) -> Optional[str]:
        """Bing wraps results: https://www.bing.com/ck/a?...&u=a1<base64url>"""
        if not href or "bing.com/ck/a" not in href:
            return href or None
        m = re.search(r"[?&]u=a1([^&]+)", href)
        if not m:
            return None
        s = m.group(1)
        s += "=" * (-len(s) % 4)  # pad
        try:
            dec = base64.urlsafe_b64decode(s).decode("utf-8", "ignore")
            # format: "https://domain\0extra"; take up to first NUL/space
            return dec.split("\x00")[0].split(" ")[0]
        except Exception:
            return None

    @staticmethod
    def _parse_snippet(text: str):
        phone = ""
        m = re.search(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)
        if m:
            phone = m.group(0)
        # city, ST pattern
        city_state = None
        cm = re.search(r"([A-Z][a-zA-Z .]+),?\s+([A-Z]{2})\b", text)
        if cm:
            city_state = (cm.group(1).strip(), cm.group(2))
        return phone, city_state

    def fetch(self, niche: str, state: str, city: Optional[str] = None,
              limit: int = 50) -> Iterator[LeadCandidate]:
        from empire_os.browser_tool import get_tool
        from bs4 import BeautifulSoup

        term = self.NICHE_TERMS.get(niche, niche)
        # Quoted query pins geo + business intent so Bing stops returning
        # far-flung "best of" aggregators.
        if city:
            q = f'\"{term}\" \"{city}, {state}\"'
        else:
            q = f'\"{term}\" \"{state}\"'
        import urllib.parse
        url = "https://www.bing.com/search?q=" + urllib.parse.quote(q) + "&count=50"

        tool = get_tool()
        html = tool.get_html(url, wait="domcontentloaded", extra_sleep=2)
        if not html or html.startswith("<error>"):
            return
        soup = BeautifulSoup(html, "html.parser")
        seen = set()
        for card in soup.select("li.b_algo")[:limit]:
            name_el = card.select_one("h2 a")
            name = name_el.get_text(strip=True) if name_el else ""
            if not name or len(name) < 3:
                continue
            href = name_el.get("href", "") if name_el else ""
            website = self._resolve_bing_redirect(href)
            if not website or website.startswith("https://www.bing"):
                continue
            # Drop aggregators / directories / social — not contractor leads
            AGG = ("yelp.com", "bbb.org", "angieslist", "homeadvisor", "yellowpages",
                   "yp.com", "tripadvisor", "facebook.com", "linkedin.com", "thumbtack",
                   "porch.com", "nextdoor", "citysearch", "manta.com", "chamberofcommerce",
                   "angi.com", "houzz", "yahoo.com", "wikipedia", "buzzfile", "findthecompany",
                   "ontoplist", "expertise.com", "buildzoom", "homeguide", "improv.com",
                   ".directory", "toprated", "trustpilot", "angie")
            if any(a in website.lower() for a in AGG):
                continue
            if name.lower().startswith(("the best", "top 10", "best 10", "bbb accredited",
                                         "top rated", "list of")):
                continue
            caption = card.select_one("div.b_caption p, div.b_lineclamp")
            snippet = caption.get_text(" ", strip=True) if caption else ""
            phone, city_state = self._parse_snippet(snippet)
            cstate = city_state[1] if city_state else state.upper()
            ccity = city_state[0] if city_state else (city or "")
            key = (name.lower(), website or "")
            if key in seen:
                continue
            seen.add(key)
            yield LeadCandidate(
                name=name,
                niche=niche,
                metro=ccity or "",
                state=cstate,
                details=f"{term} | {phone or 'no phone'} | {snippet[:140]}",
                source=self.source_name,
                lead_score=55,
                url=website or "",
                raw={"snippet": snippet[:200], "query": q, "phone": phone},
            )


# Registry-compatible runner: iterates all niches across a metro.
_METROS = ["Houston, TX", "Dallas, TX", "Los Angeles, CA", "Chicago, IL",
           "Miami, FL", "Phoenix, AZ", "New York, NY", "Atlanta, GA"]

def run(metro: str = None, limit: int = 50) -> Iterator[LeadCandidate]:
    scraper = BingLocalScraper()
    metros = [metro] if metro else _METROS
    per = max(5, limit // (len(metros) * len(scraper.supported_niches)) + 2)
    for m in metros:
        parts = [p.strip() for p in m.split(",")]
        city, state = (parts[0], parts[1]) if len(parts) == 2 else (None, m)
        for niche in scraper.supported_niches:
            try:
                yield from scraper.fetch(niche, state, city, per)
            except Exception:
                continue


def _probe() -> bool:
    """Verify-gate: one real Bing query must return >=1 business."""
    try:
        scraper = BingLocalScraper()
        leads = list(scraper.fetch("roofing", "TX", "Houston", 5))
        return len(leads) >= 1
    except Exception:
        return False


def register_source(register):
    from empire_os.lead_sources.models import SourceInfo
    register(SourceInfo(
        name="bing_local",
        tier="real",
        requires=[],
        description="Bing local business search (browser-rendered, no key)",
        run_fn=run,
        probe=_probe,
    ))


if __name__ == "__main__":
    s = BingLocalScraper()
    for lead in s.fetch("roofing", "TX", "Houston", limit=10):
        print(f"  {lead.name} | {lead.metro}, {lead.state} | {lead.url}")
