"""Bounded first-party Google URL Inspection, with no publication authority.

This reports Google's *indexed version* only; it is not a live URL test.
No general URL input, Search Console queries, identities, or provider secrets.
Runs solely through the existing read-only Search Console adapter.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Callable, Mapping

from empire_os.search_intelligence.search_console import (
    GoogleSearchConsoleAdapter, SearchConsoleUnavailable,
)

SITE = "sc-domain:empire-ai.co.uk"
INSPECTION_ENDPOINT = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
URLS = (
    "https://empire-ai.co.uk/",
    "https://empire-ai.co.uk/commercial",
    "https://empire-ai.co.uk/industries/roofing",
    "https://empire-ai.co.uk/industries/solar",
    "https://empire-ai.co.uk/predictive-revenue",
)
# Founder-published 11 Nov 2026; only these exact additional owned URLs
# are eligible for a separate read-only indexed-version inspection.
ROOFING_GUIDE_URLS = (
    "https://empire-ai.co.uk/roofing/installation-checklist",
    "https://empire-ai.co.uk/roofing/replacement-vs-repair",
)
STATUS_KEYS = (
    "verdict", "coverageState", "robotsTxtState", "indexingState",
    "pageFetchState", "crawledAs",
)
CANONICAL_KEYS = ("googleCanonical", "userCanonical")
_TS = re.compile(r"^20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
_SAFE_TEXT = re.compile(r"^[a-zA-Z0-9 _:,./()\-]{1,160}$")


def _string(value: Any) -> str | None:
    if not isinstance(value, str) or not _SAFE_TEXT.fullmatch(value):
        return None
    return value


def _canonical(value: Any) -> str | None:
    """Don't echo external/untrusted canonical URLs into an audit."""
    if not isinstance(value, str) or not value:
        return None
    if value in URLS or value in ROOFING_GUIDE_URLS:
        return value
    # A known-host canonical can be a different first-party path.
    # Return a scoped classification rather than copying unknown URL content.
    if value.startswith(("https://empire-ai.co.uk/", "https://www.empire-ai.co.uk/")):
        return "SAME_PROPERTY_OTHER_PATH"
    return "EXTERNAL_OR_UNVERIFIED"


def parse_inspection(url: str, packet: Mapping[str, Any]) -> dict[str, Any]:
    if url not in URLS and url not in ROOFING_GUIDE_URLS:
        raise SearchConsoleUnavailable("out_of_scope_inspection_url")
    if not isinstance(packet, Mapping):
        raise SearchConsoleUnavailable("invalid_inspection_response")
    result = packet.get("inspectionResult")
    if not isinstance(result, Mapping):
        raise SearchConsoleUnavailable("missing_inspection_result")
    index = result.get("indexStatusResult")
    if not isinstance(index, Mapping):
        raise SearchConsoleUnavailable("missing_index_status")
    safe: dict[str, Any] = {"url": url, "index_status_reported": True}
    for key in STATUS_KEYS:
        safe[key] = _string(index.get(key))
    for key in CANONICAL_KEYS:
        safe[key] = _canonical(index.get(key))
    crawl = index.get("lastCrawlTime")
    safe["lastCrawlTime"] = crawl if isinstance(crawl, str) and _TS.fullmatch(crawl) else None
    safe["google_indexed_version_only"] = True
    safe["live_url_test_performed"] = False
    # No inspectionResultLink (provider browsing token), sitemaps,
    # referringUrls, free-text issues, HTML, emails or query strings.
    return safe


def _inspect_scoped_urls(
    adapter: GoogleSearchConsoleAdapter,
    urls: tuple[str, ...],
    *,
    now: Callable[[], datetime],
    schema_version: str,
    success_status: str,
) -> dict[str, Any]:
    """Reuses the original approved adapter and exact trusted URL whitelist."""
    if not isinstance(adapter, GoogleSearchConsoleAdapter):
        raise SearchConsoleUnavailable("approved_adapter_required")
    status = adapter.status()
    if not status.available or status.site_url != SITE:
        raise SearchConsoleUnavailable("property_or_authority_mismatch")
    clock = now()
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise SearchConsoleUnavailable("untrusted_clock")
    # Acquire one scoped token for the complete bounded fixed-URL review.
    # Never print or persist it in the private indexing report.
    token = adapter._token_provider(adapter.credential_file)
    items = []
    for url in urls:
        # Reuse existing read-only transport, not a new OAuth integration.
        packet = adapter._post_json(
            INSPECTION_ENDPOINT,
            {"Authorization": f"Bearer {token}", "Accept": "application/json",
             "Content-Type": "application/json"},
            {"inspectionUrl": url, "siteUrl": SITE, "languageCode": "en-GB"},
        )
        items.append(parse_inspection(url, packet))
    return {
        "schema_version": schema_version,
        "status": success_status,
        "mode": "OBSERVE",
        "site": SITE,
        "observed_at": clock.astimezone(timezone.utc).isoformat(),
        "count": len(items),
        "items": items,
        "google_live_test_performed": False,
        "full_site_indexation_verified": False,
        "google_indexing_request_sent": False,
        "production_database_writes": False,
        "website_changed": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }



def inspect_fixed_urls(
    adapter: GoogleSearchConsoleAdapter,
    *,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    """Original five-URL indexed-version review; unchanged original scope."""
    return _inspect_scoped_urls(
        adapter, URLS, now=now,
        schema_version="empire.search.owned_gsc_index_inspection.v1",
        success_status="INDEXED_VERSION_INSPECTION_RECORDED",
    )


def inspect_published_roofing_guides(
    adapter: GoogleSearchConsoleAdapter,
    *,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    """Only the two SHA-released informational U.S. roofing guides.

    Google returns indexed-version status, NOT a live crawl, visitor count,
    index request or guarantee of ranking. No new permission or backend.
    """
    return _inspect_scoped_urls(
        adapter, ROOFING_GUIDE_URLS, now=now,
        schema_version="empire.search.owned_roofing_guide_index_inspection.v1",
        success_status="ROOFING_GUIDES_INDEXED_VERSION_INSPECTION_RECORDED",
    )
