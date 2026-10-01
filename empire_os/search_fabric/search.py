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
import sys
import re
import json
import time
import random
import hashlib
import urllib.parse
import threading
from collections import Counter
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterator, Optional, List, Dict, Any, Mapping
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from empire_os.geo_registry import acquisition_markets
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

# Public scraper engines must fail fast. Long 20s x 3 retry chains multiply
# badly during market sweeps. Keyed APIs retain a slightly larger budget.
SEARCH_PUBLIC_TIMEOUT = max(
    2.0,
    min(float(os.environ.get("EMPIRE_SEARCH_PUBLIC_TIMEOUT_SECONDS", "6")), 12.0),
)
SEARCH_PUBLIC_ATTEMPTS = max(
    1,
    min(int(os.environ.get("EMPIRE_SEARCH_PUBLIC_ATTEMPTS", "1")), 2),
)
SEARCH_KEYED_TIMEOUT = max(
    3.0,
    min(float(os.environ.get("EMPIRE_SEARCH_KEYED_TIMEOUT_SECONDS", "10")), 20.0),
)
SEARCH_KEYED_ATTEMPTS = max(
    1,
    min(int(os.environ.get("EMPIRE_SEARCH_KEYED_ATTEMPTS", "2")), 3),
)

SEARCH_ENGINE_FAILURE_THRESHOLD = max(
    1,
    min(int(os.environ.get("EMPIRE_SEARCH_ENGINE_FAILURE_THRESHOLD", "2")), 5),
)
SEARCH_ENGINE_COOLDOWN_SECONDS = max(
    30.0,
    min(
        float(os.environ.get("EMPIRE_SEARCH_ENGINE_COOLDOWN_SECONDS", "300")),
        1800.0,
    ),
)

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
_engine_health_lock = threading.Lock()
_engine_health: Dict[str, dict] = {}
_provider_locks = {e["name"]: threading.Lock() for e in ENGINES}
_run_local = threading.local()


def _diagnostic(message, *, file=None):
    stats = getattr(_run_local, "stats", None)
    if stats is None:
        print(message, file=file or sys.stderr)
    else:
        stats[message] += 1


def _eligible_available():
    return any(_engine_available(e["name"]) for e in ENGINES
               if not e["requires_key"] or (e["name"] == "brave" and BRAVE_API_KEY))



def _engine_available(engine: str) -> bool:
    now = time.time()
    with _engine_health_lock:
        state = _engine_health.get(engine) or {}
        return float(state.get("disabled_until") or 0.0) <= now


def _record_engine_success(engine: str) -> None:
    with _engine_health_lock:
        _engine_health[engine] = {
            "failures": 0,
            "disabled_until": 0.0,
            "last_failure": None,
        }


def _record_engine_failure(
    engine: str, reason: str, *, temporary: bool = False,
    retry_after: str | None = None,
) -> None:
    now = time.time()
    with _engine_health_lock:
        state = dict(_engine_health.get(engine) or {})
        failures = int(state.get("failures") or 0) + 1
        disabled_until = float(state.get("disabled_until") or 0.0)
        if temporary:
            # Public blocks are not proof of a broken provider. Permit a later
            # query to probe after a short cooldown, escalating sustained blocks
            # to the normal cooldown. Never retry a block inside this fetch.
            delay = min(
                SEARCH_ENGINE_COOLDOWN_SECONDS,
                RATE_LIMIT.get(engine, 2.0) * 2 ** min(failures - 1, 10),
            )
            if retry_after:
                try:
                    delay = max(delay, float(retry_after))
                except (ValueError, TypeError):
                    try:
                        delay = max(delay, parsedate_to_datetime(retry_after).timestamp() - now)
                    except (ValueError, TypeError, OverflowError):
                        pass
            disabled_until = max(disabled_until, now + delay)
        elif failures >= SEARCH_ENGINE_FAILURE_THRESHOLD:
            disabled_until = max(
                disabled_until,
                now + SEARCH_ENGINE_COOLDOWN_SECONDS,
            )
        _engine_health[engine] = {
            "failures": failures,
            "disabled_until": disabled_until,
            "last_failure": reason,
        }



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


def _search_market_locale(query: str) -> tuple[str | None, str | None]:
    """Resolve search locale from one unambiguous canonical registered market."""
    query_text = " ".join(
        re.findall(r"[a-z0-9]+", str(query or "").casefold())
    )

    matches = []

    for market in acquisition_markets():
        # Registry metros may contain region suffixes such as "Denver, CO".
        # Match the full metro first, then its canonical city component.
        metro = str(market.metro or "").casefold()
        metro_text = " ".join(re.findall(r"[a-z0-9]+", metro))

        city = metro.split(",", 1)[0].strip()
        city_text = " ".join(re.findall(r"[a-z0-9]+", city))

        candidates = tuple(
            value for value in (metro_text, city_text)
            if value
        )

        if any(
            re.search(
                rf"(?<![a-z0-9]){re.escape(value)}(?![a-z0-9])",
                query_text,
            )
            for value in candidates
        ):
            matches.append(market)

    # Multiple registry entries for the same real locale are acceptable only
    # when they agree on country and language.
    if not matches:
        return None, None

    # Prefer the most specific matching city/metro.
    # Example: "New York" must outrank the nested market name "York".
    specificity = {}
    for market in matches:
        city = str(market.metro or "").split(",", 1)[0].strip()
        city_tokens = re.findall(r"[a-z0-9]+", city.casefold())
        specificity.setdefault(len(city_tokens), []).append(market)

    best = specificity[max(specificity)]
    locales = {
        (market.country_code, market.language_code)
        for market in best
    }

    # Equal-specificity disagreement remains ambiguous and fails closed.
    if len(locales) != 1:
        return None, None

    return next(iter(locales))


def _fetch(engine: dict, query: str, num: int) -> Optional[str]:
    # Queued threads must recheck the circuit after the preceding request.
    with _provider_locks[engine["name"]]:
        return _fetch_locked(engine, query, num)


def _fetch_locked(engine: dict, query: str, num: int) -> Optional[str]:
    """Fetch raw HTML/JSON from engine. Returns text or None on failure."""
    if not _engine_available(engine["name"]):
        _diagnostic(
            f"[search_api] {engine['name']} circuit-open; skipping",
            file=sys.stderr,
        )
        return None

    _polite(engine["name"])
    proxy = _next_proxy()
    headers = _headers(engine["name"])

    keyed = bool(engine.get("requires_key"))
    attempts = SEARCH_KEYED_ATTEMPTS if keyed else SEARCH_PUBLIC_ATTEMPTS
    timeout = SEARCH_KEYED_TIMEOUT if keyed else SEARCH_PUBLIC_TIMEOUT

    for attempt in range(attempts):
        try:
            if engine["name"] == "brave":
                params = {"q": query, "count": min(num, 20)}
                r = requests.get(
                    engine["base"],
                    params=params,
                    headers=headers,
                    proxies=proxy,
                    timeout=timeout,
                )
            elif engine["name"] == "bing_html":
                country_code, language_code = _search_market_locale(query)
                params = {
                    "q": query,
                    "count": str(min(num, 20)),
                }
                if country_code:
                    params["cc"] = country_code
                if language_code:
                    params["setlang"] = language_code
                r = requests.get(
                    engine["base"],
                    params=params,
                    headers=headers,
                    proxies=proxy,
                    timeout=timeout,
                )

            elif engine["name"] in ("bing", "bing_rss"):
                # Use RSS format for reliable parsing
                params = {engine["query_param"]: query, "format": "rss"}
                r = requests.get(
                    engine["base"],
                    params=params,
                    headers=headers,
                    proxies=proxy,
                    timeout=timeout,
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
                    timeout=timeout,
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
                    timeout=timeout,
                )

            if r.status_code == 200:
                _record_engine_success(engine["name"])
                return _decode_http_response(r)
            elif r.status_code in (202, 403, 429, 503):
                _record_engine_failure(
                    engine["name"],
                    f"http_{r.status_code}",
                    temporary=True,
                    retry_after=getattr(r, "headers", {}).get("Retry-After"),
                )
                _diagnostic(f"[search_api] {engine['name']} HTTP {r.status_code} (attempt {attempt+1}/{attempts})", file=sys.stderr)
                if not keyed or not _engine_available(engine["name"]):
                    return None
                if attempt + 1 < attempts:
                    time.sleep(2 ** attempt + random.uniform(0, 1))
                    if proxy and _proxy_cycle:
                        proxy = _next_proxy()  # rotate on block
                continue
            else:
                _record_engine_failure(
                    engine["name"],
                    f"http_{r.status_code}",
                )
                _diagnostic(f"[search_api] {engine['name']} HTTP {r.status_code}", file=sys.stderr)
                return None

        except requests.exceptions.Timeout:
            _record_engine_failure(engine["name"], "timeout", temporary=not keyed)
            _diagnostic(f"[search_api] {engine['name']} timeout (attempt {attempt+1}/{attempts})", file=sys.stderr)
            if not keyed or not _engine_available(engine["name"]):
                return None
        except Exception as e:
            _record_engine_failure(
                engine["name"],
                type(e).__name__,
            )
            _diagnostic(f"[search_api] {engine['name']} error: {type(e).__name__}", file=sys.stderr)
            if attempt + 1 >= attempts or not _engine_available(engine["name"]):
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
    # URL syntax/TLD tokens must never make an unrelated result relevant.
    "com", "net", "org", "www", "http", "https",
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
    matched_terms = set()

    for term in terms:
        if term in title_tokens:
            matched += 1.0
            matched_terms.add(term)
        elif term in link_tokens:
            matched += 0.8
            matched_terms.add(term)
        elif term in snippet_tokens:
            matched += 0.6
            matched_terms.add(term)

    # Multi-term intent must be supported by multiple distinct query terms.
    # This prevents a result matching only "solar" from satisfying
    # "solar London", while preserving single-term search behaviour.
    if len(terms) >= 2 and len(matched_terms) < 2:
        return 0.0

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


def search(query: str, num: int = 10, engine: Optional[str] = None, *, use_cache: bool = True) -> dict:
    """
    Main search function. Returns Serper-compatible dict.

    Args:
        query: Search query string
        num: Number of results (1-20)
        engine: Specific engine to use, or None for auto-rotation
        use_cache: False forces new provider retrieval for observation producers

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
        cached = _get_cache(eng["name"], query, num) if use_cache else None
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
                    "quality_gate": "lexical_v2",
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
            _diagnostic(
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
                "quality_gate": "lexical_v2",
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
def _domains_from_response(res: Mapping[str, Any]) -> List[str]:
    domains = []
    for row in res.get("organic", []):
        m = DOM_RE.search(row.get("link", ""))
        if m:
            domain = m.group(1).lower().replace("www.", "")
            if domain and not any(
                bad in domain for bad in BAD_DOMAINS
            ):
                domains.append(domain)
    return list(dict.fromkeys(domains))


def _broaden_query(query: str) -> str:
    broadened = re.sub(r'["“”]', " ", query)
    broadened = re.sub(r"\s+", " ", broadened).strip()
    return broadened


def search_domains(query: str, num: int = 20, *, use_cache: bool = True) -> List[str]:
    """Extract clean domains with a bounded quote-relaxation fallback."""
    kwargs = {} if use_cache else {"use_cache": False}
    res = search(query, num=num, **kwargs)
    domains = _domains_from_response(res)
    if domains:
        return domains

    broadened = _broaden_query(query)
    if broadened and broadened != query.strip() and _eligible_available():
        _diagnostic(
            "[search_fabric] no domains; retrying without exact-match quotes",
            file=sys.stderr,
        )
        domains = _domains_from_response(
            search(broadened, num=num, **kwargs)
        )
    return domains

def search_domains_parallel(queries: List[str], num: int = 15) -> Dict[str, List[str]]:
    """Search multiple queries in parallel (threaded)."""
    if not queries:
        return {}
    out = {}
    totals = Counter()

    def _one(q):
        stats = Counter()
        _run_local.stats = stats
        try:
            return q, search_domains(q, num=num, use_cache=False), stats
        except Exception as exc:
            stats["query_failure:" + type(exc).__name__] += 1
            return q, [], stats
        finally:
            del _run_local.stats

    with ThreadPoolExecutor(max_workers=min(5, len(queries))) as ex:
        for q, domains, stats in ex.map(_one, queries):
            out[q] = domains
            totals.update(stats)
    print(json.dumps({"search_fabric_run": {
        "queries": len(queries), "queries_with_domains": sum(bool(v) for v in out.values()),
        "diagnostics": dict(sorted(totals.items())), "fresh_only": True,
    }}, sort_keys=True), file=sys.stderr)
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
