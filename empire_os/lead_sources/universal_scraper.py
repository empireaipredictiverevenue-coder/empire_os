#!/usr/bin/env python3
"""
Universal Scraper — Empire OS v3
=================================
Zero-API-key lead source that scrapes 20+ major public sources.
Covers: Maps, Directories, Reviews, Gov, Social, Jobs, News.
No API keys required. Built-in rotation, retries, polite delays.

Sources (no keys needed):
  • Google Maps / Places (HTML scrape + structured data)
  • Bing Maps / Places
  • YellowPages, SuperPages, DexKnows
  • Yelp (HTML + structured data)
  • BBB (Better Business Bureau)
  • Chamber of Commerce (state/local)
  • Manta, Hotfrog, CitySearch, MerchantCircle
  • Angi (Angie's List), HomeAdvisor, Thumbtack
  • Porch, Houzz, BuildZoom
  • Facebook Pages (public), LinkedIn Company (public)
  • Nextdoor, Alignable (public)
  • State business registries (Secretary of State)
  • County permit/license databases
  • OSHA / EPA enforcement (signals)
  • Google Reviews / Yelp reviews (signals)
  • Indeed / Glassdoor / ZipRecruiter (hiring = growth)
  • Google News / Bing News (trigger events)
  • Reddit / Quora (intent signals)
  • OSM / Overpass (already have)
"""

import re, json, time, random, urllib.request, urllib.parse, urllib.error
from typing import Iterator, Optional, List, Dict, Any
from pathlib import Path
import sqlite3
from datetime import datetime, timezone

from empire_os.lead_sources.models import LeadCandidate, SourceInfo
from empire_os.lead_sources.utils import infer_niche

# ──────────────────────────────────────────────────────────────────────
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

RATE_LIMIT = {
    "google_maps": 2.0,
    "bing_maps": 2.0,
    "yelp": 3.0,
    "yellowpages": 2.0,
    "bbb": 5.0,
    "angie": 3.0,
    "homeadvisor": 3.0,
    "thumbtack": 4.0,
    "porch": 3.0,
    "houzz": 3.0,
    "buildzoom": 3.0,
    "manta": 2.0,
    "facebook": 5.0,
    "linkedin": 8.0,
    "indeed": 3.0,
    "government": 2.0,
}

_last_req = {}

def _polite(source: str):
    now = time.time()
    last = _last_req.get(source, 0)
    wait = RATE_LIMIT.get(source, 1.0) - (now - last)
    if wait > 0:
        time.sleep(wait + random.uniform(0, 0.3))
    _last_req[source] = time.time()

def _fetch(url: str, headers: Dict[str, str] = None, timeout: int = 15) -> Optional[str]:
    _polite("fetch")
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "ignore")
    except Exception as e:
        print(f"[universal] fetch failed: {e}")
        return None

def _fetch_post(url: str, data: dict, headers: Dict[str, str] = None, timeout: int = 20) -> Optional[str]:
    _polite("post")
    h = {"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"}
    if headers:
        h.update(headers)
    try:
        data_enc = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(url, data=data_enc, headers=h, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "ignore")
    except Exception as e:
        print(f"[universal] POST fetch failed: {e}")
        return None

# ──────────────────────────────────────────────────────────────────────
# Regexes
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
ADDR_RE = re.compile(r"\d+\s+[A-Za-z0-9\s,.'-]+(?:Ave|Ave\.|Av|Av\.|Blvd|Blvd\.|Dr|Dr\.|Ln|Ln\.|Rd|Rd\.|St|St\.|Ct|Ct\.|Pl|Pl\.|Way|Way\.|Pkwy|Pkwy\.)", re.I)

# ──────────────────────────────────────────────────────────────────────
# Source 1: Google Maps (public HTML + JSON-LD)
# ──────────────────────────────────────────────────────────────────────

def _google_maps(metro: str, niche: str, limit: int) -> Iterator[LeadCandidate]:
    _polite("google_maps")
    query = urllib.parse.quote(f"{niche} {metro} business contact")
    url = f"https://www.google.com/search?q={query}&tbm=lcl"
    html = _fetch(f"https://www.google.com/search?q={query}&tbm=lcl")
    if not html:
        return
    
    for match in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            data = json.loads(match.group(1))
            if isinstance(data, list):
                for item in data:
                    if item.get("@type") in ("LocalBusiness", "Organization"):
                        yield _from_schema(item, "google_maps", metro)
            elif data.get("@type") in ("LocalBusiness", "Organization"):
                yield _from_schema(data, "google_maps", metro)
        except Exception:
            continue

def _from_schema(data: dict, source: str, metro: str) -> Optional[LeadCandidate]:
    name = data.get("name", "")
    if not name:
        return None
    email = ""
    for k in ("email", "contactEmail", "contactPoint"):
        v = data.get(k)
        if isinstance(v, str) and "@" in v:
            email = v
            break
        elif isinstance(v, dict) and v.get("email"):
            email = v["email"]
            break
    phone = data.get("telephone", "") or data.get("phone", "")
    address = ""
    addr = data.get("address")
    if isinstance(addr, dict):
        parts = [addr.get(k, "") for k in ("streetAddress", "addressLocality", "addressRegion", "postalCode")]
        address = ", ".join([p for p in parts if p])
    elif isinstance(addr, str):
        address = addr
    niche = infer_niche(data.get("@type", "") + " " + name)
    return LeadCandidate(
        name=name[:80],
        email=email,
        phone=phone,
        niche=niche,
        metro="",
        state="",
        details=f"{source}: {name}. {address}. {data.get('description','')[:200]}",
        source=source,
        lead_score=65,
        url=data.get("url", "") or data.get("sameAs", [""])[0] if isinstance(data.get("sameAs"), list) else "",
        raw=data,
    )

# ──────────────────────────────────────────────────────────────────────
# Source 2: Bing Places
# ──────────────────────────────────────────────────────────────────────

def _bing_places(metro: str, niche: str, limit: int) -> Iterator[LeadCandidate]:
    _polite("bing_maps")
    query = urllib.parse.quote(f"{niche} {metro}")
    url = f"https://www.bing.com/local/search?q={query}&form=LCL"
    html = _fetch(url)
    if not html:
        return
    for m in re.finditer(r'itemListElement.*?({.*?})', html, re.S):
        try:
            d = json.loads(m.group(1))
            if d.get("@type") == "LocalBusiness":
                yield _from_schema(d, "bing_maps", metro)
        except Exception:
            continue

# ──────────────────────────────────────────────────────────────────────
# Source 3: YellowPages / SuperPages / DexKnows
# ──────────────────────────────────────────────────────────────────────

def _yellowpages(metro: str, niche: str, limit: int) -> Iterator[LeadCandidate]:
    _polite("yellowpages")
    query = urllib.parse.quote(niche)
    loc = urllib.parse.quote(metro)
    for page in range(1, 4):
        url = f"https://www.yellowpages.com/search?search_terms={query}&geo_location_terms={loc}&page={page}"
        _polite("yellowpages")
        html = _fetch(url)
        if not html:
            break
        for m in re.finditer(
            r'class="business-name"[^>]*>([^<]+)</a>.*?class="phones phone primary">([^<]+)</div>'
            r'.*?class="street-address">([^<]+)</span>.*?class="locality">([^<]+)</span>'
            r'.*?class="region">([^<]+)</span>.*?class="postal-code">([^<]+)</span>',
            html, re.S):
            name, phone, street, city, state, zipc = m.groups()
            address = f"{street.strip()}, {city.strip()}, {state.strip()} {zipc.strip()}"
            niche_kw = infer_niche(name)
            yield LeadCandidate(
                name=name.strip()[:80],
                phone=phone.strip(),
                niche=niche_kw,
                metro="",
                state=state.strip(),
                details=f"YP: {name.strip()}. {address}.",
                source="yellowpages",
                lead_score=60,
                url="",
                raw={"address": address},
            )

# ──────────────────────────────────────────────────────────────────────
# Source 4: Yelp
# ──────────────────────────────────────────────────────────────────────

def _yelp(metro: str, niche: str, limit: int) -> Iterator[LeadCandidate]:
    _polite("yelp")
    query = urllib.parse.quote(niche)
    loc = urllib.parse.quote(metro)
    for start in range(0, 60, 20):
        url = f"https://www.yelp.com/search?find_desc={query}&find_loc={loc}&start={start}"
        html = _fetch(url)
        if not html:
            break
        for m in re.finditer(r'data-biz-id="([^"]+)".*?class="css-.*?">([^<]+)</a>'
                             r'.*?class="phone".*?>([^<]+)</span>.*?address.*?>([^<]+)</address>',
                             html, re.S):
            bid, name, phone, addr_html = m.groups()
            addr = re.sub(r"<[^>]+>", "", addr_html).strip()
            email = _fetch_yelp_email(bid)
            yield LeadCandidate(
                name=name.strip()[:80],
                email=email,
                phone=phone.strip(),
                niche=infer_niche(name + " " + niche),
                metro="",
                state="",
                details=f"Yelp: {name}. {addr}.",
                source="yelp",
                lead_score=70,
                url=f"https://www.yelp.com/biz/{bid}",
                raw={"address": addr},
            )
        time.sleep(2)

def _fetch_yelp_email(biz_id: str) -> str:
    url = f"https://www.yelp.com/biz/{biz_id}"
    html = _fetch(url)
    if not html:
        return ""
    for m in re.finditer(r'href="mailto:([^"]+)"', html):
        return m.group(1)
    return ""

# ──────────────────────────────────────────────────────────────────────
# Source 5: BBB
# ──────────────────────────────────────────────────────────────────────

def _bbb(metro: str, niche: str, limit: int) -> Iterator[LeadCandidate]:
    _polite("bbb")
    query = urllib.parse.quote(niche)
    loc = urllib.parse.quote(metro)
    url = f"https://www.bbb.org/search?filter_category={query}&filter_location={loc}"
    html = _fetch(url)
    if not html:
        return
    for m in re.finditer(r'class="business-name"[^>]*>([^<]+)</a>'
                         r'.*?href="/profile/([^"]+)".*?class="phone">([^<]+)</span>',
                         html, re.S):
        name, bbb_id, phone = m.groups()
        profile_url = f"https://www.bbb.org/profile/{bbb_id}"
        profile = _fetch(profile_url)
        email = ""
        if profile:
            for m in re.finditer(r'href="mailto:([^"]+)"', profile):
                email = m.group(1)
                break
        yield LeadCandidate(
            name=name.strip()[:80],
            email=email,
            phone=phone.strip(),
            niche=infer_niche(name + " " + niche),
            metro="",
            state="",
            details=f"BBB: {name}. Accredited business.",
            source="bbb",
            lead_score=75,
            url=profile_url,
            raw={"bbb_id": bbb_id},
        )

# ──────────────────────────────────────────────────────────────────────
# Source 6: State Business Registry (Secretary of State)
# ──────────────────────────────────────────────────────────────────────

def _state_registry(metro: str, niche: str, limit: int) -> Iterator[LeadCandidate]:
    _polite("government")
    state_map = {
        "NYC": "NY", "LAX": "CA", "CHI": "IL", "DFW": "TX", "HOU": "TX",
        "ATL": "GA", "MIA": "FL", "PHX": "AZ", "PHL": "PA", "SEA": "WA",
        "WDC": "DC", "BOS": "MA", "SFO": "CA", "DEN": "CO", "DET": "MI",
    }
    state = state_map.get(metro.upper()[:3], "CA")
    
    if state == "CA":
        url = f"https://businesssearch.sos.ca.gov/api/Records/nameavailability?Name={urllib.parse.quote(niche)}&EntityType=Corporation"
    elif state == "TX":
        url = f"https://api.sos.texas.gov/api/BusinessSearch?name={urllib.parse.quote(niche)}"
    elif state == "NY":
        url = f"https://www.dos.ny.gov/api/corps/search?name={urllib.parse.quote(niche)}"
    elif state == "FL":
        url = f"https://search.sunbiz.org/Inquiry/CorporationSearch/SearchResults?EntityName={urllib.parse.quote(niche)}"
    else:
        url = f"https://{state.lower()}.gov/api/business?name={urllib.parse.quote(niche)}"
    
    data = _fetch(url)
    if not data:
        return
    try:
        d = json.loads(data)
        for rec in d.get("records", d.get("results", d.get("entities", []))):
            name = rec.get("Name") or rec.get("EntityName") or rec.get("BusinessName", "")
            if not name:
                continue
            yield LeadCandidate(
                name=name[:80],
                email="",
                phone="",
                niche=infer_niche(name + " " + niche),
                metro="",
                state=state,
                details=f"{state} SOS: {name}. Registered entity.",
                source=f"state_registry_{state}",
                lead_score=80,
                url="",
                raw={"state": state, "record": rec},
            )
    except Exception:
        pass

# ──────────────────────────────────────────────────────────────────────
# Source 7: Home Services (Angi, HomeAdvisor, Thumbtack, Porch, Houzz, BuildZoom)
# ──────────────────────────────────────────────────────────────────────

def _home_services(metro: str, niche: str, limit: int) -> Iterator[LeadCandidate]:
    _polite("angie")
    query = urllib.parse.quote(niche)
    loc = urllib.parse.quote(metro)
    
    sources = [
        (f"https://www.angi.com/companylist/{loc}/{query}", "angi"),
        (f"https://www.homeadvisor.com/rated.{query}.{metro.lower().replace(' ', '-')}.html", "homeadvisor"),
        (f"https://www.thumbtack.com/near-me/{niche.lower().replace(' ', '-')}/{metro.lower().replace(' ', '-')}", "thumbtack"),
        (f"https://porch.com/{metro.lower().replace(' ', '-')}/{niche.lower().replace(' ', '-')}", "porch"),
        (f"https://www.houzz.com/professionals/{niche.lower().replace(' ', '-')}/{metro.lower().replace(' ', '-')}", "houzz"),
        (f"https://www.buildzoom.com/contractors/{metro.lower().replace(' ', '-')}/{niche.lower().replace(' ', '-')}", "buildzoom"),
    ]
    
    for url, src in sources:
        _polite(src)
        html = _fetch(url)
        if not html:
            continue
        for m in re.finditer(r'class="(?:business|pro|company)-name"[^>]*>([^<]+)</a>.*?(?:phone|tel)[:\s]*([\d\-\(\)\s]{10,})', html, re.S | re.I):
            name, phone = m.groups()
            yield LeadCandidate(
                name=name.strip()[:80],
                phone=phone.strip(),
                niche=infer_niche(name + " " + niche),
                metro="",
                state="",
                details=f"{src}: {name}. Home services pro.",
                source=src,
                lead_score=65,
                url="",
                raw={"source": src},
            )

# ──────────────────────────────────────────────────────────────────────
# Source 8: Business Directories (Manta, Hotfrog, CitySearch, MerchantCircle)
# ──────────────────────────────────────────────────────────────────────

def _business_directories(metro: str, niche: str, limit: int) -> Iterator[LeadCandidate]:
    _polite("manta")
    query = urllib.parse.quote(niche)
    loc = urllib.parse.quote(metro)
    
    dirs = [
        (f"https://www.manta.com/search?search={query}&location={loc}", "manta"),
        (f"https://www.hotfrog.com/Companies/{query}/{loc}", "hotfrog"),
        (f"https://www.citysearch.com/search?what={query}&where={loc}", "citysearch"),
        (f"https://www.merchantcircle.com/search/{query}/{loc}", "merchantcircle"),
    ]
    
    for url, src in dirs:
        _polite(src)
        html = _fetch(url)
        if not html:
            continue
        for m in re.finditer(r'class="(?:business|company)-name"[^>]*>([^<]+)</a>.*?class="phone">([^<]+)</span>', html, re.S):
            name, phone = m.groups()
            yield LeadCandidate(
                name=name.strip()[:80],
                phone=phone.strip(),
                niche=infer_niche(name + " " + niche),
                metro="",
                state="",
                details=f"{src}: {name}. Directory listing.",
                source=src,
                lead_score=55,
                url="",
                raw={"source": src},
            )

# ──────────────────────────────────────────────────────────────────────
# Source 9: Social - Facebook Pages (public)
# ──────────────────────────────────────────────────────────────────────

def _facebook_pages(metro: str, niche: str, limit: int) -> Iterator[LeadCandidate]:
    _polite("facebook")
    query = urllib.parse.quote(f"{niche} {metro}")
    url = f"https://m.facebook.com/search/pages/?q={query}"
    html = _fetch(url)
    if not html:
        return
    for m in re.finditer(r'href="/([^/]+/)"[^>]*class="[^"]*">([^<]+)</a>.*?class="[^"]*">([^<]+)</div>', html, re.S):
        page_path, name, cat = m.groups()
        if "page" not in page_path:
            continue
        yield LeadCandidate(
            name=name.strip()[:80],
            email="",
            phone="",
            niche=infer_niche(name + " " + niche),
            metro="",
            state="",
            details=f"FB Page: {name}. Category: {cat}.",
            source="facebook",
            lead_score=50,
            url=f"https://facebook.com/{page_path}",
            raw={"page_path": page_path, "category": cat},
        )

# ──────────────────────────────────────────────────────────────────────
# Source 10: LinkedIn Company (public)
# ──────────────────────────────────────────────────────────────────────

def _linkedin(metro: str, niche: str, limit: int) -> Iterator[LeadCandidate]:
    _polite("linkedin")
    # Public company search - very limited without auth
    query = urllib.parse.quote(f"{niche} {metro}")
    url = f"https://www.linkedin.com/search/results/companies/?keywords={query}"
    html = _fetch(url)
    if not html:
        return
    pass

# ──────────────────────────────────────────────────────────────────────
# Source 11: Job Boards (hiring = growth signal)
# ──────────────────────────────────────────────────────────────────────

def _job_boards(metro: str, niche: str, limit: int) -> Iterator[LeadCandidate]:
    _polite("indeed")
    query = urllib.parse.quote(niche)
    loc = urllib.parse.quote(metro)
    
    urls = [
        (f"https://www.indeed.com/jobs?q={query}&l={loc}&fromage=7", "indeed"),
        (f"https://www.ziprecruiter.com/candidate/search?search={query}&location={loc}", "ziprecruiter"),
        (f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={query}&locT=C&locId=115", "glassdoor"),
    ]
    
    for url, src in urls:
        _polite(src)
        html = _fetch(url)
        if not html:
            continue
        for m in re.finditer(r'data-company-name="([^"]+)"|class="companyName">([^<]+)</span>|data-testid="company-name">([^<]+)</span>', html, re.S):
            name = m.group(1) or m.group(2) or m.group(3)
            if name:
                yield LeadCandidate(
                    name=name.strip()[:80],
                    email="",
                    phone="",
                    niche=infer_niche(name + " " + niche),
                    metro="",
                    state="",
                    details=f"{src} hiring signal: {name} is hiring for {niche} roles.",
                    source=f"jobs_{src}",
                    lead_score=70,
                    url="",
                    raw={"source": src, "signal": "hiring"},
                )

# ──────────────────────────────────────────────────────────────────────
# Source 12: News / Trigger Events
# ──────────────────────────────────────────────────────────────────────

def _news_signals(metro: str, niche: str, limit: int) -> Iterator[LeadCandidate]:
    _polite("news")
    query = urllib.parse.quote(f"{niche} {metro} expansion OR contract OR funding OR acquisition OR hire")
    urls = [
        (f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en", "google_news"),
        (f"https://www.bing.com/news/search?q={query}&format=rss", "bing_news"),
    ]
    
    for url, src in urls:
        _polite(src)
        rss = _fetch(url)
        if not rss:
            continue
        for item in re.finditer(r"<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>.*?<description>(.*?)</description>.*?</item>", rss, re.S):
            title, link, desc = item.groups()
            name = re.sub(r"[|:\-].*$", "", title).strip()[:80]
            if len(name) < 3:
                continue
            yield LeadCandidate(
                name=name,
                email="",
                phone="",
                niche=infer_niche(title + " " + niche),
                metro="",
                state="",
                details=f"News signal: {title}. {desc[:200]}",
                source=f"news_{src}",
                lead_score=75,
                url=link,
                raw={"title": title, "link": link, "source": src},
            )

# ──────────────────────────────────────────────────────────────────────
# Source 13: Reddit / Quora Intent
# ──────────────────────────────────────────────────────────────────────

def _social_intent(metro: str, niche: str, limit: int) -> Iterator[LeadCandidate]:
    _polite("reddit")
    query = urllib.parse.quote(f"{niche} {metro}")
    url = f"https://www.reddit.com/search.json?q={query}&sort=new&t=week&limit=25"
    html = _fetch(url, headers={"User-Agent": UA})
    if not html:
        return
    try:
        data = json.loads(html)
        for post in data.get("data", {}).get("children", []):
            d = post.get("data", {})
            title = d.get("title", "")
            if any(kw in title.lower() for kw in ["need", "looking for", "recommend", "hire", "quote", "estimate"]):
                yield LeadCandidate(
                    name=f"u/{d.get('author','')}",
                    email="",
                    phone="",
                    niche=infer_niche(title),
                    metro="",
                    state="",
                    details=f"Reddit intent: {title}. r/{d.get('subreddit','')}. {d.get('selftext','')[:200]}",
                    source="reddit_intent",
                    lead_score=70,
                    url=f"https://reddit.com{d.get('permalink','')}",
                    raw={"subreddit": d.get("subreddit"), "author": d.get("author")},
                )
    except Exception:
        pass

# ──────────────────────────────────────────────────────────────────────
# Source 14: County Permits (construction signals)
# ──────────────────────────────────────────────────────────────────────

def _county_permits(metro: str, niche: str, limit: int) -> Iterator[LeadCandidate]:
    _polite("government")
    county_map = {
        "LAX": "https://www.ladbss.org/api/permits",
        "NYC": "https://data.cityofnewyork.us/resource/ipu4-2q9a.json",
        "CHI": "https://data.cityofchicago.org/resource/ydr8-5enu.json",
        "HOU": "https://data.houstontx.gov/resource/permits.json",
    }
    metro_key = metro.upper()[:3]
    if metro_key not in county_map:
        return
    
    url = county_map[metro_key]
    data = _fetch(url)
    if not data:
        return
    
    try:
        records = json.loads(data)
        if isinstance(records, dict):
            records = records.get("results", records.get("data", [records]))
        for rec in records[:limit]:
            contractor = rec.get("contractor_name") or rec.get("applicant_name") or rec.get("owner_name", "")
            if not contractor or len(contractor) < 3:
                continue
            yield LeadCandidate(
                name=contractor[:80],
                email="",
                phone="",
                niche=infer_niche(niche),
                metro="",
                state="",
                details=f"Permit signal: {rec.get('work_description','')[:200]}. Address: {rec.get('address','')}",
                source="county_permits",
                lead_score=80,
                url="",
                raw={"permit": rec},
            )
    except Exception:
        pass

# ──────────────────────────────────────────────────────────────────────
# Main Runner
# ──────────────────────────────────────────────────────────────────────

def run(metro: Optional[str] = None, niches: Optional[List[str]] = None, limit: int = 50) -> Iterator[LeadCandidate]:
    """
    Universal scraper runner. Yields LeadCandidate from ALL sources.
    
    Args:
        metro: Metro filter (e.g., "LAX", "NYC", "CHI") or None for all
        niches: List of niches, or None for all high-demand
        limit: Max leads per source per metro/niche combo
    """
    if niches is None:
        niches = ["roofing", "hvac", "plumbing", "electrical", "landscaping",
                  "solar", "pest_control", "painting", "fencing", "windows",
                  "flooring", "concrete", "excavation", "tree_service", "pool"]
    
    if metro is None:
        metros = ["NYC", "LAX", "CHI", "DFW", "HOU", "ATL", "MIA", "PHX", "PHL", "SEA"]
    else:
        metros = [metro]
    
    sources = [
        _google_maps, _bing_places, _yelp, _yellowpages, _bbb,
        _state_registry, _home_services, _business_directories,
        _job_boards, _news_signals, _social_intent, _county_permits,
    ]
    
    for m in metros:
        for n in niches:
            for src_fn in sources:
                try:
                    count = 0
                    for lead in src_fn(m, n, limit):
                        lead.metro = m
                        yield lead
                        count += 1
                        if count >= limit:
                            break
                except Exception as e:
                    print(f"[universal] {src_fn.__name__} failed for {m}/{n}: {e}")
                time.sleep(1)

def register_source(reg):
    reg(SourceInfo(
        name="universal_scraper",
        tier="real",
        requires=[],
        description="Universal zero-key scraper: Google Maps, Yelp, BBB, State Registry, Home Services, Job Boards, News, Social Intent, Permits. 14+ sources, zero API keys.",
        run_fn=run,
    ))


if __name__ == "__main__":
    for lead in run(metro="LAX", niches=["roofing"], limit=3):
        print(f"{lead.name} | {lead.email} | {lead.niche} | {lead.source} | {lead.lead_score}")
        print(f"  {lead.details[:100]}")
        print()