"""Bounded public-web prospect enrichment for the canonical qualification rail.

The module is deliberately read-only:
- never mutates the source prospects table
- never invents contact names or email addresses
- records only fields supported by fetched public evidence
- keeps network work bounded per prospect
"""
from __future__ import annotations

import html
import json
import re
import socket
import urllib.parse
from datetime import datetime, timezone
from typing import Any
from urllib.request import Request, urlopen

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/153.0.0.0 Safari/537.36"
)

DIRECTORY_DOMAINS = {
    "bbb.org",
    "yelp.com",
    "yellowpages.com",
    "manta.com",
    "mapquest.com",
    "angi.com",
    "homeadvisor.com",
    "thumbtack.com",
    "facebook.com",
    "linkedin.com",
    "instagram.com",
    "youtube.com",
    "houzz.com",
    "expertise.com",
    "chamberofcommerce.com",
    "mapquest.com",
}

SOURCE_WEIGHTS = {
    "website": 35,
    "search": 25,
    "rdap": 15,
    "business_signals": 25,
}


def _domain(value: str | None) -> str:
    if not value:
        return ""
    value = value.strip()
    if "://" not in value:
        value = "https://" + value
    try:
        return (urllib.parse.urlparse(value).hostname or "").lower().strip(".")
    except Exception:
        return ""


def _is_directory(url: str | None) -> bool:
    domain = _domain(url)
    if not domain:
        return True
    return any(domain == d or domain.endswith("." + d) for d in DIRECTORY_DOMAINS)


def _get(url: str, timeout: int = 8) -> tuple[str, str]:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})
    with urlopen(req, timeout=timeout) as response:
        body = response.read(500_000).decode("utf-8", errors="replace")
        return body, response.geturl()


def _normalise_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url
    return url.rstrip("/")


def _discover_website(prospect: dict[str, Any]) -> tuple[str, str | None]:
    current = _normalise_url(str(prospect.get("website") or ""))
    if current and not _is_directory(current):
        return current, None

    name = str(prospect.get("business_name") or "").strip()
    metro = str(prospect.get("metro") or "").strip()
    if not name:
        return "", None

    query = urllib.parse.quote(f'"{name}" "{metro}" official website')
    search_url = f"https://html.duckduckgo.com/html/?q={query}"

    try:
        body, _ = _get(search_url, timeout=8)
    except Exception:
        return "", None

    matches = re.findall(
        r'class=["\']result__a["\'][^>]*href=["\']([^"\']+)',
        body,
        re.IGNORECASE,
    )
    for raw in matches[:8]:
        candidate = html.unescape(raw)
        candidate = urllib.parse.unquote(candidate)

        # DuckDuckGo sometimes wraps the target in uddg=.
        parsed = urllib.parse.urlparse(candidate)
        if parsed.netloc.endswith("duckduckgo.com") and parsed.query:
            params = urllib.parse.parse_qs(parsed.query)
            candidate = params.get("uddg", [""])[0]

        candidate = _normalise_url(candidate)
        domain = _domain(candidate)
        if not domain or _is_directory(candidate):
            continue
        if "duckduckgo.com" in domain:
            continue
        return candidate, "search"

    return "", None


def _extract_site(url: str) -> dict[str, Any]:
    body, final_url = _get(url, timeout=8)
    result: dict[str, Any] = {
        "website": _normalise_url(final_url or url),
    }

    title = re.search(
        r"<title[^>]*>(.*?)</title>",
        body,
        re.IGNORECASE | re.DOTALL,
    )
    if title:
        value = re.sub(r"\s+", " ", html.unescape(title.group(1))).strip()
        if value:
            result["site_title"] = value[:300]

    description = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)["\']',
        body,
        re.IGNORECASE,
    )
    if description:
        value = re.sub(r"\s+", " ", html.unescape(description.group(1))).strip()
        if value:
            result["meta_description"] = value[:500]

    emails = re.findall(
        r"(?i)\b[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}\b",
        body,
    )
    domain = _domain(result["website"])
    email_candidates = []
    for email in emails:
        email = email.lower()
        if domain and email.endswith("@" + domain):
            email_candidates.append(email)
    if email_candidates:
        result["email"] = email_candidates[0]

    phones = re.findall(
        r"(?<!\d)(?:\+?1[\s.\-]?)?(?:\(?\d{3}\)?[\s.\-]?)\d{3}[\s.\-]\d{4}(?!\d)",
        body,
    )
    if phones:
        result["phone"] = phones[0].strip()

    social_map = {
        "facebook": r"https?://(?:www\.)?facebook\.com/[^\s\"'<>]+",
        "linkedin": r"https?://(?:www\.)?linkedin\.com/(?:company|in)/[^\s\"'<>]+",
        "instagram": r"https?://(?:www\.)?instagram\.com/[^\s\"'<>]+",
        "youtube": r"https?://(?:www\.)?youtube\.com/(?:@|channel/|c/)[^\s\"'<>]+",
    }
    socials: list[str] = []
    for pattern in social_map.values():
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            value = html.unescape(match.group(0)).rstrip(".,;")
            if value not in socials:
                socials.append(value)
    if socials:
        result["social_links"] = json.dumps(socials)

    return result


def _rdap(url: str) -> dict[str, Any]:
    domain = _domain(url)
    if not domain or "." not in domain:
        return {}

    result: dict[str, Any] = {}
    try:
        addresses = socket.gethostbyname_ex(domain)[2]
        if addresses:
            result["domain_ip"] = addresses[0]
    except OSError:
        pass

    if domain.endswith(".com"):
        try:
            body, _ = _get(
                f"https://rdap.verisign.com/com/v1/domain/{domain}",
                timeout=8,
            )
            data = json.loads(body)
            for event in data.get("events", []):
                if event.get("eventAction") == "registration":
                    result["domain_created"] = str(event.get("eventDate", ""))[:10]
                    break
        except Exception:
            pass

    return result


def enrich_prospect_for_scoring(prospect: dict[str, Any]) -> dict[str, Any]:
    """Return evidence-backed fields and a bounded enrichment quality score."""
    fields: dict[str, Any] = {}
    evidence: list[dict[str, Any]] = []
    source_names: list[str] = []

    website, discovered_source = _discover_website(prospect)
    if website:
        try:
            site_fields = _extract_site(website)
            for key, value in site_fields.items():
                if value and not prospect.get(key):
                    fields[key] = value
            source_names.append("website")
            evidence.append(
                {
                    "source": "website",
                    "url": website,
                    "fields": sorted(site_fields.keys()),
                }
            )
        except Exception as exc:
            evidence.append(
                {"source": "website", "url": website, "error": str(exc)[:200]}
            )

    if discovered_source:
        source_names.append(discovered_source)
        evidence.append(
            {
                "source": discovered_source,
                "query": f"{prospect.get('business_name','')} {prospect.get('metro','')}",
            }
        )

    rdap_target = fields.get("website") or prospect.get("website")
    if rdap_target and not _is_directory(str(rdap_target)):
        rdap_fields = _rdap(str(rdap_target))
        if rdap_fields:
            fields.update({k: v for k, v in rdap_fields.items() if v})
            source_names.append("rdap")
            evidence.append(
                {
                    "source": "rdap",
                    "domain": _domain(str(rdap_target)),
                    "fields": sorted(rdap_fields.keys()),
                }
            )

    # A separate business-signals source is credited only when enrichment
    # actually surfaced business-facing contact or social evidence.
    if any(k in fields for k in ("email", "phone", "social_links")):
        source_names.append("business_signals")
        evidence.append(
            {
                "source": "business_signals",
                "fields": [
                    k for k in ("email", "phone", "social_links") if k in fields
                ],
            }
        )

    unique_sources = []
    for source in source_names:
        if source not in unique_sources:
            unique_sources.append(source)

    quality = min(
        100.0,
        sum(SOURCE_WEIGHTS.get(source, 0) for source in unique_sources),
    )

    return {
        "fields": fields,
        "enrichment_score": quality,
        "sources": unique_sources,
        "evidence": evidence,
        "enriched_at": datetime.now(timezone.utc).isoformat(),
    }
