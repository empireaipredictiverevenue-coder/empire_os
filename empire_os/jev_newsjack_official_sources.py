"""Bounded public-government source inputs for the existing JEV traffic review.

Reads only official fixed endpoints on explicit operator invocation. This is
not a new news daemon, scraper, publisher or commercial-proof producer.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Callable, Mapping
from urllib.parse import urlencode, urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, Request

from empire_os.jev_newsjack_traffic import _public_https, _timestamp

MAX_RESPONSE_BYTES = 650_000
_MAX_RESULTS = 10
_ALLOWED_TYPES = ("solar", "roofing", "hvac", "dental", "ai")
_US_API = "https://www.federalregister.gov/api/v1/documents.json"


class SourceUnavailable(RuntimeError):
    pass


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _receive_official_json(url: str) -> Mapping[str, Any]:
    """Single bounded official GET. Reject redirects and all non-allowlisted URLs."""
    parsed = urlsplit(url)
    host, path = parsed.hostname, parsed.path
    if not (parsed.scheme == "https" and parsed.port is None and
            parsed.username is None and parsed.password is None and
            ((host == "www.federalregister.gov" and
              path == "/api/v1/documents.json") or
             (host == "www.gov.uk" and path.startswith("/api/content/")))):
        raise ValueError("official_source_url_not_allowlisted")

    class RejectRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise SourceUnavailable("official_redirect_refused")

    request = Request(url, headers={
        "User-Agent": "EmpireAI-OfficialResearch-ReadOnly/1.0",
        "Accept": "application/json",
    })
    try:
        with build_opener(RejectRedirect).open(request, timeout=8) as response:
            if response.status != 200:
                raise SourceUnavailable("official_api_non_200")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise SourceUnavailable("official_api_response_too_large")
        payload = json.loads(raw)
    except (OSError, ValueError) as exc:
        raise SourceUnavailable("official_api_unavailable") from exc
    if not isinstance(payload, Mapping):
        raise SourceUnavailable("official_api_invalid_json")
    return payload


def _base(*, as_of: str, sector: str, market: str) -> tuple[datetime, dict[str, Any]]:
    observed = _timestamp(as_of)
    if (observed is None or sector not in _ALLOWED_TYPES or
            market not in ("GB", "US")):
        raise ValueError("approved market, sector and timestamp required")
    return observed, {
        "sector": sector, "market": market,
        "observed_at": observed.isoformat(),
        "independent_corroboration_verified": False,
        "destination_live_verified": False,
    }


def federal_register_signals(
    *, term: str, as_of: str, sector: str, max_results: int = 8,
    fetch_json: Callable[[str], Mapping[str, Any]] = _receive_official_json,
) -> dict[str, Any]:
    """Official dated US records, not inferred breaking-news headlines."""
    clock, shared = _base(as_of=as_of, sector=sector, market="US")
    if (not isinstance(term, str) or not re.fullmatch(r"[a-zA-Z0-9 -]{3,55}", term)
            or type(max_results) is not int
            or not 1 <= max_results <= _MAX_RESULTS):
        raise ValueError("bounded public term and max_results required")
    query_url = _US_API + "?" + urlencode({
        "conditions[term]": term.strip(),
        "order": "newest",
        "per_page": str(max_results),
    })
    payload = fetch_json(query_url)
    results = payload.get("results")
    if not isinstance(results, list):
        raise SourceUnavailable("official_api_results_unavailable")
    signals = []
    rejected_generic = 0
    for record in results[:max_results]:
        if not isinstance(record, Mapping):
            continue
        number, title = record.get("document_number"), record.get("title")
        url, pub = record.get("html_url"), record.get("publication_date")
        if (not isinstance(number, str) or not re.fullmatch(r"20\d\d-\d{3,7}", number)
                or not isinstance(title, str) or len(title.strip()) < 8
                or not isinstance(pub, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", pub)
                or not isinstance(url, str)
                or urlsplit(url).hostname != "www.federalregister.gov"
                or not _public_https(url)):
            continue
        try:
            datetime.strptime(pub, "%Y-%m-%d")
        except ValueError:
            continue
        # A general docket filing is NOT a sector-specific editorial discovery.
        if ("combined notice of filings" in title.lower()
                or "notice of availability" in title.lower()
                or not any(word.lower() in title.lower() for word in term.split())):
            rejected_generic += 1
            continue
        signals.append({
            **shared, "signal_id": "federal_register:" + number,
            "title": title.strip()[:220], "primary_source_url": url,
            "published_at": None, "publication_date": pub,
            "publication_date_verified": True,
            "source_kind": "federal_register",
            "source_document_type": str(record.get("type") or "")[:50],
            "source_metadata_precision": "date_only",
            "evidence_refs": ["federalregister:api:" + _digest({
                "number": number, "title": title, "url": url, "publication_date": pub,
            })],
        })
    return {
        "schema_version": "empire.organic.official_source_intake.v1",
        "mode": "OBSERVE", "source": "us_federal_register",
        "source_url": query_url, "signals": signals,
        "candidate_count": len(signals),
        "generic_or_off_topic_filtered": rejected_generic,
        "unverified_claims_not_promoted": True,
        "note": "date-only official publications; future publication dates are held",
        "execution_authority": "none",
    }


def govuk_primary_signal(
    *, public_url: str, as_of: str, sector: str,
    fetch_json: Callable[[str], Mapping[str, Any]] = _receive_official_json,
) -> dict[str, Any]:
    """Verify metadata for one known GOV.UK URL; this is not keyword discovery."""
    clock, shared = _base(as_of=as_of, sector=sector, market="GB")
    canonical = _public_https(public_url)
    parts = urlsplit(canonical or "")
    if (not canonical or parts.hostname != "www.gov.uk"
            or not parts.path.startswith(("/government/", "/guidance/", "/statistics/"))
            or len(parts.path) > 350 or parts.query):
        raise ValueError("known public GOV.UK content URL required")
    api_url = "https://www.gov.uk/api/content" + parts.path
    response = fetch_json(api_url)
    first = _timestamp(response.get("first_published_at"))
    updated = _timestamp(response.get("public_updated_at"))
    basepath = response.get("base_path")
    title = response.get("title")
    if (basepath != parts.path or not isinstance(title, str) or
            not 8 <= len(title.strip()) <= 220 or not first
            or response.get("document_type") in ("redirect", "gone")
            or response.get("withdrawn_notice")):
        raise SourceUnavailable("govuk_not_original_published_content")
    document_id = response.get("content_id")
    result = {
        **shared,
        "signal_id": "govuk:" + _digest({"path": basepath})[:28],
        "title": title.strip(), "primary_source_url": canonical,
        "published_at": first.isoformat(),
        "source_public_updated_at": updated.isoformat() if updated else None,
        "source_kind": "govuk_content_api",
        "source_document_type": str(response.get("document_type") or "")[:50],
        "evidence_refs": ["govuk:content_api:" + _digest({
            "id": document_id, "path": basepath, "title": title,
            "first_published_at": first.isoformat(), "public_updated_at": response.get("public_updated_at"),
        })],
    }
    return {
        "schema_version": "empire.organic.official_source_intake.v1",
        "mode": "OBSERVE", "source": "govuk_content_api",
        "source_url": api_url, "signals": [result],
        "candidate_count": 1, "unverified_claims_not_promoted": True,
        "note": "original first publication, not update date, determines freshness",
        "execution_authority": "none",
    }
