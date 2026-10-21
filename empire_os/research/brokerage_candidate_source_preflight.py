"""Read-only original-publisher candidate checks; no source admission.

Strictly scoped to two independently identified Birmingham roofing sites.
This is not a general URL fetcher, source registry, licence check, claim
verifier, customer prospect engine, or unsupervised publication workflow.
The existing research Editorial inspector/short-passage parser are reused.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Callable
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from bs4 import BeautifulSoup

from .brokerage_editorial_review import MAX_BYTES, _Headings, _NoRedirect
from .original_source_passages import extract_source_passage_anchors

SCHEMA = "empire.research.original_publisher_candidate_preflight.v1"
CANDIDATES = {
    ("roofing", "GB"): {
        "https://www.centralroofing.co.uk/branch/birmingham-roofing-contractor/": "Central Roofing Birmingham branch",
        "https://ehsroofing.co.uk/": "EHS Roofing Birmingham",
    },
}
ROOFING_TERMS = (
    "roofing", "roof repair", "roof replacement", "flat roof",
    "roofing contractor", "commercial roofing", "residential roofing",
    "roof maintenance", "roofing services",
)


def _fetch_original_candidate(url: str) -> bytes:
    """Exact public HTTPS URL only; never follow redirects or load assets."""
    request = Request(url, headers={
        "User-Agent": "EmpireOSOriginalSourceReview/1.0",
        "Accept": "text/html",
    })
    with build_opener(_NoRedirect()).open(request, timeout=10) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError("CANDIDATE_HTTP_OR_IDENTITY_MISMATCH")
        content_type = str(response.headers.get("Content-Type", "")).lower()
        if "text/html" not in content_type:
            raise ValueError("CANDIDATE_NOT_HTML")
        body = response.read(MAX_BYTES + 1)
        if not body or len(body) > MAX_BYTES:
            raise ValueError("CANDIDATE_BODY_SIZE_INVALID")
        return body


def preflight_candidate(
    *, niche: str, country: str, source_url: str,
    fetch_fn: Callable[[str], bytes] = _fetch_original_candidate,
    observed_at: datetime | None = None,
) -> dict:
    """Observe body hash & short original-page anchors, no trust promotion."""
    now = observed_at or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("TRUSTED_CANDIDATE_CLOCK_REQUIRED")
    allowed = CANDIDATES.get((niche, country), {})
    if type(source_url) is not str or source_url not in allowed:
        raise ValueError("SOURCE_CANDIDATE_NOT_IN_EXACT_OWNER_REVIEW_SET")
    parsed_url = urlsplit(source_url)
    if parsed_url.scheme != "https" or parsed_url.username or parsed_url.password or parsed_url.port:
        raise ValueError("UNSAFE_CANDIDATE_ORIGINAL_URL")
    base = {
        "schema_version": SCHEMA, "niche": niche, "country": country,
        "source_url": source_url, "publisher_name_as_candidate": allowed[source_url],
        "observed_at_utc": now.astimezone(timezone.utc).isoformat(),
        "source_admitted": False, "source_reuse_rights_verified": False,
        "original_publisher_claims_verified": False,
        "actual_buyer_interest_verified": False, "research_owner_approved": False,
        "editorial_signoff": False, "outbound_authorized": False,
        "customer_delivery_authorized": False, "commercial_actions_authorized": False,
        "database_writes": False, "payment_authorized": False,
        "next_owner": "existing_search_and_market_intelligence",
    }
    try:
        body = fetch_fn(source_url)
        if not isinstance(body, bytes) or not body or len(body) > MAX_BYTES:
            raise ValueError("CANDIDATE_BODY_SIZE_INVALID")
        parsed = _Headings()
        parsed.feed(body.decode("utf-8", errors="replace"))
        soup = BeautifulSoup(body, "html.parser")
        title = (" ".join(soup.title.get_text(" ", strip=True).split())[:180]
                 if soup.title else "")
        passages = extract_source_passage_anchors(body, terms=ROOFING_TERMS)
        if not (parsed.headings or title) or not passages:
            return {**base, "status": "CANDIDATE_ORIGINAL_PAGE_TOPIC_OR_STRUCTURE_HELD",
                    "reason": "NO_BOUNDED_RELEVANT_ORIGINAL_HEADING_AND_PASSAGE",
                    "original_body_sha256": sha256(body).hexdigest(),
                    "short_source_anchors": [],
                    "next_action": "MANUAL_PUBLISHER_AND_TOPIC_REVIEW"}
        return {
            **base, "status": "CANDIDATE_ORIGINAL_PAGE_OBSERVED_NOT_ADMITTED",
            "reason": None, "original_body_sha256": sha256(body).hexdigest(),
            "original_body_size_bytes": len(body),
            "publisher_host": parsed_url.hostname,
            "observed_document_title": title,
            "observed_headings": parsed.headings[:4],
            "short_source_anchors": passages,
            "next_action": "INDEPENDENT_RESEARCH_OWNER_CONFIRM_PUBLISHER_RIGHTS_AND_CLAIMS",
        }
    except (OSError, ValueError, TimeoutError, UnicodeError) as exc:
        return {**base, "status": "CANDIDATE_ORIGINAL_PAGE_FETCH_HELD",
                "reason": type(exc).__name__, "short_source_anchors": [],
                "next_action": "ORIGINAL_SOURCE_ACCESS_AND_RIGHTS_REVIEW"}


def run_birmingham_roofing_candidates() -> dict:
    """Two exact self-published original candidates, no market inference."""
    rows = [preflight_candidate(niche="roofing", country="GB", source_url=url)
            for url in CANDIDATES[("roofing", "GB")]]
    return {
        "schema_version": "empire.research.roofing_candidate_batch.v1",
        "status": "EXACT_UK_ROOFING_CANDIDATES_REVIEWED_NOT_ADMITTED",
        "source_candidate_count": len(rows),
        "original_candidate_pages_observed": sum(
            row["status"] == "CANDIDATE_ORIGINAL_PAGE_OBSERVED_NOT_ADMITTED"
            for row in rows
        ),
        "admitted_original_sources": 0, "editorial_approvals": 0,
        "money_moved": False, "outbound_sent": False, "database_writes": False,
        "owner": "existing_search_and_market_intelligence", "rows": rows,
    }
