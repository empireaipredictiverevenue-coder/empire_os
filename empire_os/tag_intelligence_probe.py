"""Bounded first-party tag observation for Empire Tag Intelligence.

Static observation only. Seeing tag code is not proof that an event fired,
that Meta CAPI delivered, that Google received a hit, or that consent is
legally sufficient.
"""
from __future__ import annotations

import ipaddress
import json
import re
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


RequestGet = Callable[..., Any]

_GTM_RE = re.compile(r"\bGTM-[A-Z0-9]+\b", re.I)
_GTAG_RE = re.compile(r"\bGT-[A-Z0-9]+\b", re.I)
_GA4_RE = re.compile(r"\bG-[A-Z0-9]+\b", re.I)
_ADS_RE = re.compile(r"\bAW-[0-9]+\b", re.I)
_FB_INIT_RE = re.compile(
    r"fbq\s*\(\s*['\"]init['\"]\s*,\s*['\"]([^'\"]+)['\"]",
    re.I,
)
_GTAG_EVENT_RE = re.compile(
    r"gtag\s*\(\s*['\"]event['\"]\s*,\s*['\"]([^'\"]+)['\"]",
    re.I,
)
_FB_EVENT_RE = re.compile(
    r"fbq\s*\(\s*['\"]track(?:Custom)?['\"]\s*,\s*['\"]([^'\"]+)['\"]",
    re.I,
)


def _public_http_url(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("url required")
    if not text.startswith(("http://", "https://")):
        text = "https://" + text
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("http/https url required")

    host = parsed.hostname.lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise ValueError("local targets are not allowed")
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        addr = None
    if addr is not None and (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
    ):
        raise ValueError("private network targets are not allowed")
    return text


def _content(
    soup: BeautifulSoup,
    *,
    name: str | None = None,
    property_name: str | None = None,
) -> str | None:
    attrs: dict[str, str] = {}
    if name is not None:
        attrs["name"] = name
    if property_name is not None:
        attrs["property"] = property_name
    node = soup.find("meta", attrs=attrs)
    if node is None:
        return None
    value = str(node.get("content") or "").strip()
    return value or None


def _all_matches(pattern: re.Pattern[str], text: str) -> list[str]:
    return sorted({
        str(value).strip()
        for value in pattern.findall(text)
        if str(value).strip()
    })


def _counts(pattern: re.Pattern[str], text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in pattern.findall(text):
        key = str(value).strip()
        if key:
            counts[key] = counts.get(key, 0) + 1
    return counts


def _json_ld_types(soup: BeautifulSoup) -> list[str]:
    types: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            raw = value.get("@type")
            if isinstance(raw, str) and raw.strip():
                types.add(raw.strip())
            elif isinstance(raw, list):
                for item in raw:
                    if str(item).strip():
                        types.add(str(item).strip())
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for node in soup.find_all(
        "script",
        attrs={"type": re.compile(r"application/ld\+json", re.I)},
    ):
        try:
            walk(json.loads(node.string or node.get_text() or ""))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    return sorted(types)


def observe_tag_surface(
    url: str,
    *,
    request_timeout: float = 8.0,
    get: RequestGet = requests.get,
) -> dict[str, Any]:
    target = _public_http_url(url)
    timeout = max(1.0, min(float(request_timeout), 20.0))
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; EmpireTagIntelligence/1.0; "
            "+https://empire-ai.co.uk)"
        ),
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    }

    try:
        response = get(
            target,
            timeout=timeout,
            headers=headers,
            allow_redirects=True,
        )
    except Exception as exc:
        return {
            "ok": False,
            "requested_url": target,
            "error": type(exc).__name__,
            "mode": "OBSERVE",
            "execution_authority": "none",
        }

    status = int(getattr(response, "status_code", 0) or 0)
    final_url = str(getattr(response, "url", target) or target)
    if status < 200 or status >= 400:
        return {
            "ok": False,
            "requested_url": target,
            "final_url": final_url,
            "status_code": status,
            "error": "http_status_not_success",
            "mode": "OBSERVE",
            "execution_authority": "none",
        }

    html = str(getattr(response, "text", "") or "")
    soup = BeautifulSoup(html, "html.parser")
    combined = html

    title_nodes = soup.find_all("title")
    title = (
        title_nodes[0].get_text(" ", strip=True)
        if title_nodes else None
    )
    canonical_node = soup.find(
        "link",
        attrs={"rel": lambda value: value and "canonical" in value},
    )
    canonical = (
        urljoin(final_url, str(canonical_node.get("href") or "").strip())
        if canonical_node and str(canonical_node.get("href") or "").strip()
        else None
    )

    og = {
        key: _content(soup, property_name=f"og:{key}")
        for key in ("title", "description", "url", "image", "type")
    }
    twitter = {
        key: _content(soup, name=f"twitter:{key}")
        for key in ("card", "title", "description", "image")
    }

    hreflang = []
    for node in soup.find_all("link"):
        lang = str(node.get("hreflang") or "").strip()
        href = str(node.get("href") or "").strip()
        if lang and href:
            hreflang.append(f"{lang}:{urljoin(final_url, href)}")

    images_missing_alt = sum(
        1
        for node in soup.find_all("img")
        if node.get("alt") is None
    )

    charset_present = bool(
        soup.find("meta", attrs={"charset": True})
        or soup.find(
            "meta",
            attrs={
                "http-equiv": re.compile(r"content-type", re.I),
            },
        )
    )
    viewport_present = (
        soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
        is not None
    )

    gtm_counts = _counts(_GTM_RE, combined)
    gtag_counts = _counts(_GTAG_RE, combined)
    ga4_counts = _counts(_GA4_RE, combined)
    ads_counts = _counts(_ADS_RE, combined)
    pixel_counts = _counts(_FB_INIT_RE, combined)

    duplicate_tag_counts = {
        key: count
        for group in (
            gtm_counts,
            gtag_counts,
            ga4_counts,
            ads_counts,
            pixel_counts,
        )
        for key, count in group.items()
        if count > 1
    }

    declared_events: list[str] = []
    event_counts: dict[str, int] = {}
    for pattern in (_GTAG_EVENT_RE, _FB_EVENT_RE):
        for event in pattern.findall(combined):
            name = str(event).strip()
            if not name:
                continue
            declared_events.append(name)
            event_counts[name] = event_counts.get(name, 0) + 1

    consent_observed = bool(
        re.search(
            r"gtag\s*\(\s*['\"]consent['\"]",
            combined,
            re.I,
        )
    )

    page_tags = {
        "url": final_url,
        "title": title,
        "title_count": len(title_nodes),
        "meta_description": _content(soup, name="description"),
        "canonical_url": canonical,
        "robots": _content(soup, name="robots"),
        "x_robots_tag": str(
            getattr(response, "headers", {}).get("X-Robots-Tag") or ""
        ).strip() or None,
        "open_graph": {
            key: value for key, value in og.items() if value
        },
        "twitter": {
            key: value for key, value in twitter.items() if value
        },
        "json_ld_types": _json_ld_types(soup),
        "hreflang": sorted(set(hreflang)),
        "viewport_present": viewport_present,
        "charset_present": charset_present,
        "h1_count": len(soup.find_all("h1")),
        "images_missing_alt": images_missing_alt,
        "meta_keywords_present": (
            soup.find(
                "meta",
                attrs={"name": re.compile(r"^keywords$", re.I)},
            )
            is not None
        ),
    }

    measurement_tags = {
        "observation_level": "STATIC_MARKUP",
        "event_observation_level": "SOURCE_DECLARATION",
        "gtm_container_ids": sorted(gtm_counts),
        "google_tag_ids": sorted(gtag_counts),
        "ga4_measurement_ids": sorted(ga4_counts),
        "google_ads_conversion_ids": sorted(ads_counts),
        "meta_pixel_ids": sorted(pixel_counts),
        "duplicate_tag_counts": duplicate_tag_counts,
        "observed_events": sorted(set(declared_events)),
        "duplicate_event_counts": {
            key: count
            for key, count in event_counts.items()
            if count > 1
        },
        "consent_mode_enabled": True if consent_observed else None,
        "meta_capi_enabled": None,
        "meta_event_id_dedup": None,
        "server_side_tagging": None,
        "revenue_truth_linked": None,
    }

    return {
        "ok": True,
        "requested_url": target,
        "final_url": final_url,
        "status_code": status,
        "page_tags": page_tags,
        "measurement_tags": measurement_tags,
        "limitations": [
            "static_markup_observation_only",
            "event_declaration_is_not_event_delivery",
            "meta_capi_delivery_not_observed",
            "google_hit_delivery_not_observed",
            "consent_legality_not_assessed",
            "revenue_impact_not_inferred",
        ],
        "mode": "OBSERVE",
        "execution_authority": "none",
    }
