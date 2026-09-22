#!/usr/bin/env python3
"""
Empire Search API — Self-Hosted SERP Scraper
=============================================
Zero-cost, self-hosted replacement for Serper/SerpAPI/Serply/SerpStack.
Scrapes multiple engines with rotation. No API keys. No fees.

Engines (priority order):
  1. Brave Search API (requires BRAVE_API_KEY, free tier 2000/q/mo)
  2. Bing HTML (works direct, good coverage)
  3. DuckDuckGo Lite (works via Tor, no JS)
  4. Mojeek (independent index, no key)

Returns Serper-compatible JSON:
{
  "organic": [{"title", "link", "snippet", "position"}],
  "searchParameters": {"q": "...", "num": 10, "engine": "brave"},
  "credits_left": 999999
}
"""

import os
import re
import json
import time
import random
import hashlib
import urllib.parse
from pathlib import Path
from typing import Iterator, Optional, List, Dict, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from .decoder import decode_document

# ──────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────
CACHE_DIR = Path(os.environ.get("EMPIRE_SEARCH_CACHE", "/srv/empire_os/runtime/search/cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL = 86400  # 24 hours

# Proxy configuration (comma-separated: "http://user:pass@host:port,http://...")
PROXY_LIST = [p.strip() for p in os.environ.get("SEARCH_PROXIES", "").split(",") if p.strip()]

# Brave API key (free: 2000 queries/month at api.search.brave.com)
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")

# Rate limits per engine (seconds between requests)
RATE_LIMIT = {
    "brave": 0.5,
    "bing_html": 1.5,
    "duckduckgo_html": 1.5,
    "bing_rss": 2.0,
    "duckduckgo_lite": 1.5,
    "mojeek": 3.0,
}

# Engine configurations
ENGINES = [
    {
        "name": "brave",
        "type": "api",
        "base": "https://api.search.brave.com/res/v1/web/search",
        "method": "GET",
        "requires_key": True,
        "auto": True,
    },
    {
        "name": "bing_html",
        "type": "html",
        "base": "https://www.bing.com/search",
        "method": "GET",
        "query_param": "q",
        "requires_key": False,
        "auto": True,
    },
    {
        "name": "duckduckgo_html",
        "type": "html",
        "base": "https://html.duckduckgo.com/html/",
        "method": "POST",
        "query_param": "q",
        "requires_key": False,
        "auto": True,
    },

    # Historical fallbacks. Preserved for explicit diagnostics/recovery,
    # but excluded from automatic production retrieval.
    {
        "name": "bing_rss",
        "type": "rss",
        "base": "https://www.bing.com/search",
        "method": "GET",
        "query_param": "q",
        "requires_key": False,
        "auto": False,
    },
    {
        "name": "duckduckgo_lite",
        "type": "html",
        "base": "https://lite.duckduckgo.com/lite/",
        "method": "POST",
        "query_param": "q",
        "requires_key": False,
        "auto": False,
    },
    {
        "name": "mojeek",
        "type": "html",
        "base": "https://www.mojeek.com/search",
        "method": "GET",
        "query_param": "q",
        "requires_key": False,
        "auto": False,
    },
]

# ──────────────────────────────────────────────────────────────────────
# Regexes
# ──────────────────────────────────────────────────────────────────────
DOM_RE = re.compile(r'https?://([A-Za-z0-9.-]+\.[A-Za-z]{2,})')
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
BAD_DOMAINS = (
    "google.com", "bing.com", "duckduckgo.com", "yahoo.com", "yandex.com",
    "facebook.com", "linkedin.com", "youtube.com", "wikipedia.org",
    "tripadvisor.com", "pinterest.com", "instagram.com", "twitter.com",
    "reddit.com", "pdf", ".gov", ".edu", "amazon.com", "ebay.com"
)

# ──────────────────────────────────────────────────────────────────────
# Rate Limiting
# ──────────────────────────────────────────────────────────────────────
_last_req: Dict[str, float] = {}

def _polite(engine: str):
    rate = RATE_LIMIT.get(engine, 2.0)
    now = time.time()
    last = _last_req.get(engine, 0)
    wait = rate - (now - last)
    if wait > 0:
        time.sleep(wait + random.uniform(0, 0.3))
    _last_req[engine] = time.time()

# ──────────────────────────────────────────────────────────────────────
# Proxy Rotation
# ──────────────────────────────────────────────────────────────────────
_proxy_cycle = None
if PROXY_LIST:
    import itertools
    _proxy_cycle = itertools.cycle(PROXY_LIST)

def _next_proxy() -> Optional[Dict[str, str]]:
    if not _proxy_cycle:
        return None
    p = next(_proxy_cycle)
    return {"http": p, "https": p}

# ──────────────────────────────────────────────────────────────────────
# Cache
# ──────────────────────────────────────────────────────────────────────
def _cache_key(engine: str, query: str, num: int) -> Path:
    h = hashlib.sha256(f"{engine}:{query}:{num}".encode()).hexdigest()[:16]
    return CACHE_DIR / f"{engine}_{h}.json"

def _get_cache(engine: str, query: str, num: int) -> Optional[dict]:
    path = _cache_key(engine, query, num)
    try:
        if path.exists():
            data = json.loads(path.read_text())
            if time.time() - data.get("ts", 0) < CACHE_TTL:
                return data.get("data")
    except Exception:
        pass
    return None

def _set_cache(engine: str, query: str, num: int, data: dict):
    path = _cache_key(engine, query, num)
    try:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"ts": time.time(), "data": data}))
        tmp.replace(path)
    except Exception:
        pass

# ──────────────────────────────────────────────────────────────────────
# HTTP Client
# ──────────────────────────────────────────────────────────────────────
UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

def _headers(engine: str) -> Dict[str, str]:
    h = {
        "User-Agent": random.choice(UA_POOL),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    if engine == "brave":
        h["Accept"] = "application/json"
        h["X-Subscription-Token"] = BRAVE_API_KEY
    return h

def _decode_http_response(response) -> str:
    """
    Normalize an HTTP response through the Empire Universal Decoder.

    requests already handles its supported transfer compression before
    exposing response.content, so content_encoding is intentionally empty
    here to avoid double-decompression.
    """
    document = decode_document(
        url=str(response.url),
        data=response.content,
        content_type=response.headers.get("Content-Type", ""),
        content_encoding="",
        charset=response.encoding,
    )
    return document.text


def _fetch(engine: dict, query: str, num: int) -> Optional[str]:
    """Fetch raw HTML/JSON from engine. Returns text or None on failure."""
    _polite(engine["name"])
    proxy = _next_proxy()
    headers = _headers(engine["name"])

    for attempt in range(3):
        try:
            if engine["name"] == "brave":
                params = {"q": query, "count": min(num, 20)}
                r = requests.get(
                    engine["base"],
                    params=params,
                    headers=headers,
                    proxies=proxy,
                    timeout=20,
                )
            elif engine["name"] == "bing_html":
                params = {
                    "q": query,
                    "count": str(min(num, 20)),
                    "cc": "US",
                    "setlang": "en-US",
                }
                r = requests.get(
                    engine["base"],
                    params=params,
                    headers=headers,
                    proxies=proxy,
                    timeout=20,
                )

            elif engine["name"] in ("bing", "bing_rss"):
                # Use RSS format for reliable parsing
                params = {engine["query_param"]: query, "format": "rss"}
                r = requests.get(
                    engine["base"],
                    params=params,
                    headers=headers,
                    proxies=proxy,
                    timeout=20,
                )
            elif engine["method"] == "POST":
                data = {engine["query_param"]: query}
                if "num" in engine:
                    data["num"] = str(num)
                r = requests.post(
                    engine["base"],
                    data=data,
                    headers=headers,
                    proxies=proxy,
                    timeout=20,
                )
            else:
                params = {engine["query_param"]: query}
                if "num" in engine:
                    params["num"] = str(num)
                r = requests.get(
                    engine["base"],
                    params=params,
                    headers=headers,
                    proxies=proxy,
                    timeout=20,
                )

            if r.status_code == 200:
                return _decode_http_response(r)
            elif r.status_code in (403, 429, 503):
                print(f"[search_api] {engine['name']} HTTP {r.status_code} (attempt {attempt+1}/3)", file=sys.stderr)
                if attempt < 2:
                    time.sleep(2 ** attempt + random.uniform(0, 1))
                    if proxy and _proxy_cycle:
                        proxy = _next_proxy()  # rotate on block
                continue
            else:
                print(f"[search_api] {engine['name']} HTTP {r.status_code}", file=sys.stderr)
                return None

        except requests.exceptions.Timeout:
            print(f"[search_api] {engine['name']} timeout (attempt {attempt+1}/3)", file=sys.stderr)
        except Exception as e:
            print(f"[search_api] {engine['name']} error: {e}", file=sys.stderr)
            if attempt == 2:
                return None
            time.sleep(1)

    return None

# ──────────────────────────────────────────────────────────────────────
# HTML Parsing
# ──────────────────────────────────────────────────────────────────────
def _parse_brave(data: dict) -> List[dict]:
    """Parse Brave JSON API response."""
    results = []
    for i, item in enumerate(data.get("web", {}).get("results", []), 1):
        results.append({
            "title": item.get("title", "")[:200],
            "link": item.get("url", ""),
            "snippet": item.get("description", "")[:300],
            "position": i,
        })
    return results

def _parse_bing_rss(xml: str) -> List[dict]:
    """Parse Bing RSS feed results using regex (handles entities)."""
    results = []
    # Regex approach - handles & and other entities
    for m in re.finditer(
        r'<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>.*?<description>(.*?)</description>',
        xml, re.S | re.I
    ):
        title, link, description = m.groups()
        # Decode common HTML entities
        title = title.replace("&", "&").replace("<", "<").replace(">", ">").replace('"', '"')
        description = description.replace("&", "&").replace("<", "<").replace(">", ">").replace('"', '"')
        results.append({
            "title": re.sub(r"<[^>]+>", "", title).strip()[:200],
            "link": link.strip(),
            "snippet": re.sub(r"<[^>]+>", "", description).strip()[:300],
            "position": len(results) + 1,
        })
    return results

def _parse_duckduckgo_lite(html: str) -> List[dict]:
    """Parse DuckDuckGo Lite table results."""
    results = []
    for m in re.finditer(
        r'<td class="result-snippet">(.*?)</td>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        html, re.S | re.I
    ):
        snippet, link, title = m.groups()
        results.append({
            "title": re.sub(r"<[^>]+>", "", title).strip()[:200],
            "link": link,
            "snippet": re.sub(r"<[^>]+>", "", snippet).strip()[:300],
            "position": len(results) + 1,
        })
    return results

def _parse_mojeek(html: str) -> List[dict]:
    """Parse Mojeek HTML results."""
    results = []
    for m in re.finditer(
        r'<article class="s-result".*?<h3><a[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
        r'<p class="s-desc">(.*?)</p>',
        html, re.S | re.I
    ):
        link, title, snippet = m.groups()
        results.append({
            "title": re.sub(r"<[^>]+>", "", title).strip()[:200],
            "link": link,
            "snippet": re.sub(r"<[^>]+>", "", snippet).strip()[:300],
            "position": len(results) + 1,
        })
    return results


def _clean_html_text(value: str) -> str:
    import html as _html

    value = _html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _decode_bing_url(value: str) -> str:
    """
    Convert Bing /ck/a redirect URLs into the underlying destination URL
    when the encoded `u=` target is available.
    """
    import base64
    import html as _html
    from urllib.parse import parse_qs, urlparse

    value = _html.unescape(value or "")

    try:
        parsed = urlparse(value)

        if "bing.com" not in parsed.netloc or not parsed.path.startswith("/ck/"):
            return value

        encoded = parse_qs(parsed.query).get("u", [""])[0]

        # Bing commonly prefixes the base64 target with "a1".
        if encoded.startswith("a1"):
            encoded = encoded[2:]

        if not encoded:
            return value

        encoded += "=" * (-len(encoded) % 4)
        decoded = base64.urlsafe_b64decode(encoded).decode(
            "utf-8",
            errors="ignore",
        )

        if decoded.startswith(("http://", "https://")):
            return decoded

    except Exception:
        pass

    return value


def _decode_duckduckgo_url(value: str) -> str:
    """Resolve DDG redirect URLs where uddg contains the real target."""
    import html as _html
    from urllib.parse import parse_qs, unquote, urlparse

    value = _html.unescape(value or "")

    if value.startswith("//"):
        value = "https:" + value

    try:
        parsed = urlparse(value)
        target = parse_qs(parsed.query).get("uddg", [""])[0]

        if target:
            return unquote(target)
    except Exception:
        pass

    return value


def _parse_bing_html(page: str) -> List[dict]:
    """Parse Bing's current organic HTML result blocks."""
    results = []

    blocks = re.findall(
        r'<li[^>]+class="[^"]*\bb_algo\b[^"]*"[^>]*>(.*?)</li>',
        page,
        re.I | re.S,
    )

    for block in blocks:
        match = re.search(
            r'<h2[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            block,
            re.I | re.S,
        )

        if not match:
            continue

        link, title = match.groups()

        snippet_match = re.search(
            r'<p[^>]*>(.*?)</p>',
            block,
            re.I | re.S,
        )

        snippet = (
            _clean_html_text(snippet_match.group(1))
            if snippet_match
            else ""
        )

        results.append({
            "title": _clean_html_text(title)[:200],
            "link": _decode_bing_url(link),
            "snippet": snippet[:300],
            "position": len(results) + 1,
            "source_engine": "bing_html",
        })

    return results


def _parse_duckduckgo_html(page: str) -> List[dict]:
    """Parse DuckDuckGo's current HTML endpoint."""
    results = []

    matches = re.finditer(
        r'<a[^>]+class="[^"]*\bresult__a\b[^"]*"'
        r'[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        page,
        re.I | re.S,
    )

    for match in matches:
        link, title = match.groups()

        # Search locally after the title for the associated snippet.
        tail = page[match.end():match.end() + 2500]

        snippet_match = re.search(
            r'class="[^"]*\bresult__snippet\b[^"]*"[^>]*>'
            r'(.*?)</(?:a|div)>',
            tail,
            re.I | re.S,
        )

        snippet = (
            _clean_html_text(snippet_match.group(1))
            if snippet_match
            else ""
        )

        results.append({
            "title": _clean_html_text(title)[:200],
            "link": _decode_duckduckgo_url(link),
            "snippet": snippet[:300],
            "position": len(results) + 1,
            "source_engine": "duckduckgo_html",
        })

    return results


PARSERS = {
    "brave": _parse_brave,
    "bing_html": _parse_bing_html,
    "duckduckgo_html": _parse_duckduckgo_html,
    "bing_rss": _parse_bing_rss,
    "duckduckgo_lite": _parse_duckduckgo_lite,
    "mojeek": _parse_mojeek,
}

# ──────────────────────────────────────────────────────────────────────
# Main Search Function
# ──────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────
# Result Quality / Relevance
# ──────────────────────────────────────────────────────────────────────

from urllib.parse import unquote as _url_unquote

_QUERY_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "is", "of", "on", "or", "the", "to", "with",
}

def _query_terms(query: str) -> List[str]:
    """Extract meaningful normalized terms from a query."""
    terms = re.findall(r"[a-z0-9]+", query.lower())
    return [
        term for term in terms
        if len(term) > 1 and term not in _QUERY_STOPWORDS
    ]


def _result_relevance(result: dict, query: str) -> float:
    """Measure lexical agreement between a result and search intent."""
    terms = _query_terms(query)
    if not terms:
        return 0.0

    title = (result.get("title") or "").lower()
    snippet = (result.get("snippet") or "").lower()
    link = _url_unquote(result.get("link") or "").lower()

    title_tokens = set(re.findall(r"[a-z0-9]+", title))
    snippet_tokens = set(re.findall(r"[a-z0-9]+", snippet))
    link_tokens = set(re.findall(r"[a-z0-9]+", link))

    matched = 0.0
    for term in terms:
        if term in title_tokens:
            matched += 1.0
        elif term in link_tokens:
            matched += 0.8
        elif term in snippet_tokens:
            matched += 0.6

    return matched / len(terms)


def _quality_filter(
    results: List[dict],
    query: str,
    limit: int,
) -> List[dict]:
    """Reject unrelated SERPs and rank surviving results."""
    ranked = []

    for result in results:
        score = _result_relevance(result, query)

        if score < 0.34:
            continue

        row = dict(result)
        row["relevance_score"] = round(score, 4)
        ranked.append(row)

    ranked.sort(
        key=lambda row: (
            -row["relevance_score"],
            row.get("position", 9999),
        )
    )

    ranked = ranked[:limit]

    for position, row in enumerate(ranked, 1):
        row["position"] = position

    return ranked


def search(query: str, num: int = 10, engine: Optional[str] = None) -> dict:
    """
    Main search function. Returns Serper-compatible dict.

    Args:
        query: Search query string
        num: Number of results (1-20)
        engine: Specific engine to use, or None for auto-rotation

    Returns:
        {
            "organic": [{"title", "link", "snippet", "position"}],
            "searchParameters": {"q": query, "num": num, "engine": engine_used},
            "credits_left": 999999
        }
    """
    num = min(max(1, num), 20)

    # Determine engines to try
    if engine:
        engines_to_try = [e for e in ENGINES if e["name"] == engine]
        if not engines_to_try:
            return {"organic": [], "searchParameters": {"q": query, "num": num, "engine": engine}, "credits_left": 999999, "error": f"Unknown engine: {engine}"}
    else:
        # Production auto order:
        # Brave when configured -> Bing HTML -> DuckDuckGo HTML.
        # If those fail or are blocked, reuse the already-shipped historical
        # adapters as bounded recovery providers. Every recovered result still
        # passes the same lexical quality gate before it can leave Search Fabric.
        engines_to_try = [
            e for e in ENGINES
            if e.get("auto", True)
            and (
                not e["requires_key"]
                or (e["name"] == "brave" and BRAVE_API_KEY)
            )
        ]
        if not BRAVE_API_KEY:
            engines_to_try = [
                e for e in engines_to_try
                if e["name"] != "brave"
            ]

        recovery_names = {
            "bing_rss",
            "duckduckgo_lite",
            "mojeek",
        }
        recovery_engines = [
            e for e in ENGINES
            if e["name"] in recovery_names
            and not e["requires_key"]
            and e not in engines_to_try
        ]
        engines_to_try.extend(recovery_engines)

    for eng in engines_to_try:
        # Check cache first
        cached = _get_cache(eng["name"], query, num)
        if cached:
            cached_results = _quality_filter(
                cached.get("organic", []),
                query,
                num,
            )
            if cached_results:
                cached = dict(cached)
                cached["organic"] = cached_results
                cached["searchParameters"] = {
                    **cached.get("searchParameters", {}),
                    "quality_gate": "lexical_v1",
                    "cache": True,
                }
                return cached

        raw = _fetch(eng, query, num)
        if not raw:
            continue

        if eng["name"] == "brave":
            try:
                data = json.loads(raw)
                results = _parse_brave(data)
            except json.JSONDecodeError:
                continue
        else:
            parser = PARSERS.get(eng["name"])
            if not parser:
                continue
            results = parser(raw)

        if not results:
            continue

        results = _quality_filter(
            results,
            query,
            num,
        )

        if not results:
            print(
                f"[search_fabric] {eng['name']} rejected: "
                "no relevant results",
                file=sys.stderr,
            )
            continue

        response = {
            "organic": results,
            "searchParameters": {
                "q": query,
                "num": num,
                "engine": eng["name"],
                "quality_gate": "lexical_v1",
                "cache": False,
            },
            "credits_left": 999999,
        }

        _set_cache(eng["name"], query, num, response)
        return response

    # All engines failed
    return {
        "organic": [],
        "searchParameters": {"q": query, "num": num, "engine": "none"},
        "credits_left": 999999,
        "error": "All engines failed"
    }

# ──────────────────────────────────────────────────────────────────────
# Domain Extraction & Email Scraping
# ──────────────────────────────────────────────────────────────────────
def search_domains(query: str, num: int = 20) -> List[str]:
    """Extract clean domains from search results."""
    res = search(query, num=num)
    domains = []
    for r in res.get("organic", []):
        m = DOM_RE.search(r.get("link", ""))
        if m:
            d = m.group(1).lower().replace("www.", "")
            if d and not any(bad in d for bad in BAD_DOMAINS):
                domains.append(d)
    return list(dict.fromkeys(domains))  # preserve order, dedupe

def search_domains_parallel(queries: List[str], num: int = 15) -> Dict[str, List[str]]:
    """Search multiple queries in parallel (threaded)."""
    out = {}
    def _one(q):
        return q, search_domains(q, num=num)

    with ThreadPoolExecutor(max_workers=min(5, len(queries))) as ex:
        for q, domains in ex.map(_one, queries):
            out[q] = domains
    return out

# ──────────────────────────────────────────────────────────────────────
# Email Scraping
# ──────────────────────────────────────────────────────────────────────
def _fetch_url(url: str, timeout: int = 8) -> Optional[str]:
    """Fetch a single URL with the Search Fabric HTTP policy."""
    proxy = _next_proxy()
    headers = _headers("html")
    try:
        r = requests.get(url, headers=headers, proxies=proxy, timeout=timeout)
        if r.status_code == 200:
            return r.text
    except Exception:
        pass
    return None

def scrape_emails(domain: str, paths: List[str] = None) -> str:
    """Best-effort email scrape from domain's contact/about pages."""
    if paths is None:
        paths = ["", "/contact", "/contact-us", "/about", "/get-in-touch", "/about-us"]

    for path in paths:
        for scheme in ("https://", "http://"):
            url = f"{scheme}{domain}{path}"
            html = _fetch_url(url)
            if not html:
                continue
            emails = [e for e in EMAIL_RE.findall(html)
                     if not e.lower().endswith((".png", ".jpg", ".svg", ".webp", ".gif"))]
            if emails:
                # Prefer generic addresses
                for e in emails:
                    if e.split("@")[0].lower() in ("info", "sales", "contact", "hello", "admin", "office", "support"):
                        return e
                return emails[0]
    return ""

# ──────────────────────────────────────────────────────────────────────
# CLI / Test
# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 -m empire_os.lead_sources.search_api 'query' [num] [engine]")
        sys.exit(1)

    q = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    eng = sys.argv[3] if len(sys.argv) > 3 else None

    res = search(q, num=n, engine=eng)
    print(json.dumps(res, indent=2))
