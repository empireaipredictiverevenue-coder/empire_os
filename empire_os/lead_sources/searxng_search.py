#!/usr/bin/env python3
"""
SearXNG Search Lead Source — Self-Hosted Meta-Search Engine
============================================================
Uses a local SearXNG instance (Docker) as a zero-cost, unlimited
meta-search engine. Aggregates Google, Bing, DuckDuckGo, Brave,
Yandex, Mojeek, Qwant, Startpage, and 20+ engines.

No API keys. No rate limits. No fees. Full control.

Deploy: docker run -d -p 8080:8080 searxng/searxng:latest
Or: docker compose -f /root/empire_os/infra/searxng.yml up -d

Then point this module at http://localhost:8080
"""

import json, re, time, urllib.request, urllib.parse, urllib.error
from typing import Iterator, Optional, List, Dict
from pathlib import Path

from empire_os.lead_sources.models import LeadCandidate, SourceInfo
from empire_os.lead_sources.utils import infer_niche

# ──────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────
SEARXNG_URL = "http://localhost:8080"  # Change if different host/port
RATE_LIMIT = 1.0  # seconds between requests
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

_last_req = 0.0

def _polite():
    global _last_req
    wait = RATE_LIMIT - (time.time() - _last_req)
    if wait > 0:
        time.sleep(wait)
    _last_req = time.time()

def _fetch(url: str, headers: dict = None, timeout: int = 20) -> Optional[str]:
    _polite()
    h = {"User-Agent": UA, "Accept": "application/json, text/html"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "ignore")
    except Exception as e:
        print(f"[searxng] fetch failed: {e}")
        return None

# ──────────────────────────────────────────────────────────────────────
# Search Functions
# ──────────────────────────────────────────────────────────────────────

def searxng_search(query: str, categories: str = "general", 
                   language: str = "en", safe_search: int = 1,
                   time_range: str = "", pageno: int = 1, num: int = 10) -> dict:
    """
    Call SearXNG JSON API.
    Returns normalized dict matching Serper schema:
    {"organic": [{"title", "link", "snippet", "position"}], "credits_left": 999999}
    """
    params = {
        "q": query,
        "categories": categories,
        "language": language,
        "safesearch": str(safe_search),
        "time_range": time_range,
        "pageno": str(pageno),
        "format": "json",
    }
    url = f"{SEARXNG_URL}/search?{urllib.parse.urlencode(params)}"
    
    html = _fetch(f"{SEARXNG_URL}/search", headers={"Accept": "application/json"})
    if not html:
        return {"organic": [], "credits_left": 999999, "error": "fetch_failed"}
    
    try:
        data = json.loads(html)
    except json.JSONDecodeError:
        # Try HTML fallback
        return _parse_html(html)
    
    results = []
    for i, r in enumerate(data.get("results", []), 1):
        results.append({
            "title": r.get("title", "")[:200],
            "link": r.get("url", ""),
            "snippet": r.get("content", "")[:300],
            "position": i,
        })
    
    return {
        "organic": results,
        "searchParameters": {"q": data.get("query", ""), "pageno": pageno},
        "credits_left": 999999,
    }

def _parse_html(html: str) -> dict:
    """Fallback HTML parsing for older SearXNG versions."""
    results = []
    for m in re.finditer(r'class="result".*?href="([^"]+)".*?class="title">([^<]+)</a>.*?class="content">([^<]+)', html, re.S):
        link, title, snippet = m.groups()
        results.append({
            "title": title.strip()[:200],
            "link": link,
            "snippet": snippet.strip()[:300],
            "position": len(results) + 1,
        })
    return {"organic": results, "credits_left": 999999}

def searxng_domains(query: str, num: int = 20) -> List[str]:
    """Extract clean domains from SearXNG results."""
    res = searxng_search(query, num=num)
    domains = []
    for r in res.get("organic", []):
        try:
            from urllib.parse import urlparse
            domain = urllib.parse.urlparse(r["link"]).netloc.lower().replace("www.", "")
            if domain and not any(bad in domain for bad in 
                ("google.com","bing.com","duckduckgo.com","yelp.com","facebook.com",
                 "linkedin.com","youtube.com","wikipedia.org","pdf","gov","edu")):
                domains.append(domain)
        except Exception:
            continue
    return list(dict.fromkeys(domains))


# ──────────────────────────────────────────────────────────────────────
# Email Scraping
# ──────────────────────────────────────────────────────────────────────

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

def scrape_emails(domain: str, paths: List[str] = None) -> str:
    """Best-effort email scrape from domain's contact/about pages."""
    if paths is None:
        paths = ["", "/contact", "/contact-us", "/about", "/get-in-touch"]
    
    for path in paths:
        for scheme in ("https://", "http://"):
            url = f"{scheme}{domain}{path}"
            html = _fetch(url)
            if not html:
                continue
            emails = [e for e in EMAIL_RE.findall(html) 
                     if not e.lower().endswith((".png",".jpg",".svg",".webp",".gif"))]
            if emails:
                for e in emails:
                    if e.split("@")[0].lower() in ("info","sales","contact","hello","admin","office","support"):
                        return e
                return emails[0]
    return ""


# ──────────────────────────────────────────────────────────────────────
# Lead Source Runner
# ──────────────────────────────────────────────────────────────────────

VERTICALS = {
    "roofing":     "roofing contractor company contact email",
    "hvac":        "hvac contractor company contact email",
    "plumbing":    "plumbing contractor company contact email",
    "electrical":  "electrician contractor company contact email",
    "solar":       "solar installation company contact email",
    "landscaping": "landscaping company contact email",
    "pest_control": "pest control company contact email",
    "painting":    "painting contractor company contact email",
    "fencing":     "fence company contact email",
    "windows":     "window replacement company contact email",
    "flooring":    "flooring company contact email",
    "concrete":    "concrete contractor company contact email",
    "excavation":  "excavation company contact email",
    "tree":        "tree service company contact email",
    "pool":        "pool service company contact email",
    "cleaning":    "commercial cleaning company contact email",
    "security":    "security guard company contact email",
    "moving":      "moving company contact email",
    "storage":     "self storage company contact email",
    "trucking":    "trucking company contact email",
    "logistics":   "logistics company contact email",
    "warehouse":   "warehouse storage company contact email",
    "manufacturing": "manufacturing company contact email",
    "construction": "construction company contact email",
    "fintech":     "fintech company contact email",
    "ecommerce":   "ecommerce store company contact email",
    "chiropractic": "chiropractic clinic contact email",
    "veterinary":  "veterinary clinic animal hospital contact email",
    "physiotherapy": "physiotherapy clinic contact email",
    "auto":        "auto repair shop dealership contact email",
    "tire":        "tire shop company contact email",
    "title":       "title company real estate closing contact email",
    "mortgage":    "mortgage broker lender contact email",
    "property_mgmt": "property management company contact email",
    "restaurant":  "restaurant group franchise contact email",
    "hotel":       "hotel hospitality company contact email",
    "retail":      "retail store chain company contact email",
    "fitness":     "gym fitness studio contact email",
    "photography": "photography studio company contact email",
    "webdev":      "web development agency contact email",
    "seo":         "seo agency company contact email",
    "consulting":  "business consulting firm contact email",
    "recruiter":   "executive recruiter search firm contact email",
    "courier":     "courier delivery service company contact email",
    "waste":       "waste management junk removal company contact email",
    "equipment":   "heavy equipment rental company contact email",
    "flooring":    "flooring company contact email",
    "painting":    "painting contractor company contact email",
    "pool":        "pool service company contact email",
    "tree":        "tree service company contact email",
    "excavation":  "excavation landscaping company contact email",
    "fencing":     "fence company contact email",
    "concrete":    "concrete contractor company contact email",
    "glass":       "glass window company contact email",
    "cabinet":     "cabinet kitchen company contact email",
    "countertop":  "countertop company contact email",
}

def _scrape_email(domain: str) -> str:
    """Best-effort email scrape from domain's contact/about pages."""
    for path in ("", "/contact", "/contact-us", "/about", "/get-in-touch"):
        for scheme in ("https://", "http://"):
            url = f"{scheme}{domain}{path}"
            html = _fetch(url)
            if not html:
                continue
            emails = [e for e in EMAIL_RE.findall(html) 
                     if not e.lower().endswith((".png",".jpg",".svg",".webp",".gif"))]
            if emails:
                for e in emails:
                    if e.split("@")[0].lower() in ("info","sales","contact","hello","admin","office","support"):
                        return e
                return emails[0]
    return ""


def run(metro: Optional[str] = None, verticals: Optional[List[str]] = None, limit: int = 40) -> Iterator[LeadCandidate]:
    targets = VERTICALS if verticals is None else {v: VERTICALS[v] for v in verticals if v in VERTICALS}
    pushed = 0
    
    for vert, query in targets.items():
        if pushed >= limit:
            break
        if metro:
            query += f" {metro}"
        
        print(f"[searxng] {vert}: searching...")
        
        doms = searxng_domains(query, num=30)
        
        for dm in doms:
            if pushed >= limit:
                break
            email = _scrape_email(dm)
            if not email:
                continue
            
            niche = infer_niche(vert)
            yield LeadCandidate(
                name=dm,
                email=email,
                niche=niche,
                metro=metro or "",
                source=f"searxng:{vert}",
                lead_score=65,
                url=f"https://{dm}",
                raw={"domain": dm, "vertical": vert, "query": query},
            )
            pushed += 1
            time.sleep(0.3)


def register_source(reg):
    reg(SourceInfo(
        name="searxng",
        tier="real",
        requires=[],
        description="Self-hosted SearXNG meta-search (Google/Bing/DDG/Brave/Yandex/20+) → domain → email. Zero keys, zero fees, unlimited.",
        run_fn=run,
    ))

if __name__ == "__main__":
    for c in run(verticals=["roofing"], limit=3):
        print(f"{c.name} | {c.email} | {c.niche} | {c.lead_score}")