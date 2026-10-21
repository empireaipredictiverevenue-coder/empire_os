"""Evidence-first decision brief composer for EmpireOS brokerage research.

No autonomous publishing, quotations-as-facts, synthetic intent, or self-
approval. Existing Vane/OpenManus research receipts become a useful editorial
work product, with provider health, provenance and unanswered buyer questions.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit
import ipaddress
import json
import re

from .brokerage_editorial_review import COUNTRY_SOURCES, SCHEMA as REVIEW_SCHEMA

SCHEMA = "empire.brokerage.evidence_decision_brief.v1"
_SEARCH_QUERIES = {
    "US": (
        "Chicago Lincoln Park dental implant clinic original service pages",
        "Chicago dental implant market original primary source evidence",
    ),
    "GB": (
        "Birmingham dental implant practice original services official UK",
        "UK CMA private dental services market study primary source",
    ),
}

def _valid_search_url(value: Any) -> bool:
    if not isinstance(value, str) or len(value) > 1000:
        return False
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme != "https" or not host or parsed.username or parsed.password:
            return False
        if parsed.port not in (None, 443):
            return False
        if host in {"localhost", "example.com", "example.org", "example.net"}:
            return False
        if host.endswith((".test", ".example", ".invalid", ".local", ".internal")):
            return False
        if "." not in host:
            return False
        try:
            addr = ipaddress.ip_address(host)
        except ValueError:
            return True
        return addr.is_global
    except (ValueError, TypeError):
        return False


def discover_held_candidates(
    country: str,
    search_fn: Callable[..., Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Search Fabric discovery with strict freshness; no result auto-admission.

    A failed or stale search provider is UNKNOWN, not evidence that a market
    has no buyers or competitors. Search results are only candidate URLs,
    never factual evidence, lead identities or source-reuse clearance.
    """
    if country not in COUNTRY_SOURCES:
        raise ValueError("BROKERAGE_MARKET_COUNTRY_UNSUPPORTED")
    if search_fn is None:
        return {
            "status": "SEARCH_NOT_RUN_NO_VERIFIED_PROVIDER",
            "queries_attempted": 0,
            "candidate_urls": [],
            "any_verified_fresh_results": False,
            "source_admissions": 0,
            "buyer_intent_verified": False,
        }
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    failures: list[str] = []
    for query in _SEARCH_QUERIES[country]:
        try:
            result = search_fn(query, num=5, engine="bing_html", use_cache=False)
            if not isinstance(result, Mapping):
                raise ValueError("INVALID_SEARCH_FABRIC_RESULT")
            p = result.get("searchParameters")
            if not isinstance(p, Mapping):
                raise ValueError("SEARCH_PROVENANCE_MISSING")
            if (result.get("error") or result.get("stale") or result.get("synthetic")
                or p.get("stale") or p.get("synthetic")
                or p.get("cache") is not False
                or p.get("engine") in (None, "none", "unknown")):
                raise ValueError("NO_VERIFIED_FRESH_SEARCH_EVIDENCE")
            for row in result.get("organic", [])[:5]:
                if not isinstance(row, Mapping) or row.get("synthetic"):
                    continue
                url = row.get("link") or row.get("url")
                if not _valid_search_url(url) or url in seen:
                    continue
                seen.add(url)
                items.append({
                    "url": url,
                    "title": str(row.get("title") or "")[:150],
                    "discovery_query": query,
                    "provider": str(p["engine"])[:45],
                    "admission_state": "PENDING_INDEPENDENT_ORIGINAL_SOURCE_REVIEW",
                })
        except Exception as exc:
            failures.append(type(exc).__name__)
    return {
        "status": (
            "FRESH_DISCOVERY_CANDIDATES_NOT_ADMITTED" if items
            else "SEARCH_PROVIDER_DEGRADED_OR_NO_FRESH_EVIDENCE"
        ),
        "queries_attempted": len(_SEARCH_QUERIES[country]),
        "provider_errors": failures,
        "candidate_urls": items[:10],
        "any_verified_fresh_results": bool(items),
        "source_admissions": 0,
        "buyer_intent_verified": False,
        "outbound_authorized": False,
    }


def build_brokerage_decision_brief(
    report: Mapping[str, Any],
    *,
    search_diagnostic: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Binds original inspected sources to research questions, not conclusions."""
    if (not isinstance(report, Mapping)
        or report.get("schema_version") != REVIEW_SCHEMA
        or report.get("market_country") not in COUNTRY_SOURCES):
        raise ValueError("EXACT_CURRENT_RESEARCH_RECEIPT_REQUIRED")
    country = report["market_country"]
    known = {url for _, url in COUNTRY_SOURCES[country]}
    observations = report.get("source_observations")
    if not isinstance(observations, list):
        raise ValueError("SOURCE_OBSERVATIONS_REQUIRED")
    seen = set()
    ledger: list[dict[str, Any]] = []
    for record in observations:
        if not isinstance(record, Mapping) or record.get("url") not in known:
            raise ValueError("UNCLEARED_OR_CROSS_MARKET_SOURCE")
        url = record["url"]
        if url in seen:
            raise ValueError("DUPLICATE_ORIGINAL_SOURCE")
        seen.add(url)
        inspected = (record.get("original_page_inspected") is True
                     and record.get("inspection_status") == "ORIGINAL_HTML_HEADINGS_INSPECTED"
                     and bool(re.fullmatch("[0-9a-f]{64}",
                                           str(record.get("content_sha256") or ""))))
        headings = record.get("document_headings") if inspected else []
        ledger.append({
            "source_id": record.get("source_id"),
            "publisher_host": urlsplit(url).hostname,
            "original_url": url,
            "source_type": ("official_public_market_context" if "gov.uk" in url
                            else "practice_first_party_service_page"),
            "inspected": inspected,
            "content_sha256": record.get("content_sha256") if inspected else None,
            "page_headings_as_observed": headings[:4] if isinstance(headings, list) else [],
            "literal_terms_seen_on_page_not_clinically_validated": (
                (record.get("literal_source_terms_observed") or [])[:12]
                if inspected and isinstance(record.get("literal_source_terms_observed"), list)
                else []
            ),
            "headings_are_not_independent_claim_verification": True,
            "factual_interpretation_editorial_review_required": True,
            "licensing_reuse_cleared": False,
        })
    if len(ledger) != len(known):
        # Never say the country has full original coverage from partial sources.
        coverage = "PARTIAL_KNOWN_SOURCE_SET"
    else:
        coverage = "ALL_CURATED_ORIGINAL_SOURCE_URLS_PRESENT"
    inspected_n = sum(r["inspected"] for r in ledger)
    status = ("SOURCE_EVIDENCE_READY_FOR_EDITORIAL_REVIEW"
              if inspected_n == len(known) and coverage.startswith("ALL_")
              else "HELD_MISSING_ORIGINAL_SOURCE_EVIDENCE")
    questions = [
        "What exact buyer decision, city/catchment and treatment should this research answer?",
        "Do observed clinic propositions describe comparable services or distinct treatment pathways?",
        "Which quoted original-page claims require specialist/editorial verification?",
        "What source licences, attribution or publisher permissions limit client reuse?",
        "What ranking, enquiry, patient and commercial-performance evidence is not available?",
    ]
    if country == "GB":
        questions.insert(
            2, "How does CMA market context differ from claims on individual Birmingham practice pages?"
        )
    discovery = search_diagnostic or discover_held_candidates(country, None)
    if discovery.get("source_admissions") != 0 or discovery.get("buyer_intent_verified") is not False:
        raise ValueError("SEARCH_RESULTS_CANNOT_GRANT_SOURCE_OR_COMMERCIAL_AUTHORITY")
    evidence_fingerprint = sha256(json.dumps(ledger, sort_keys=True).encode()).hexdigest()
    return {
        "schema_version": SCHEMA,
        "country": country,
        "status": status,
        "source_coverage": coverage,
        "original_pages_inspected": inspected_n,
        "curated_original_source_count": len(known),
        "original_sample_sha256": report.get("original_sample_sha256"),
        "evidence_fingerprint_sha256": evidence_fingerprint,
        "evidence_ledger": ledger,
        "source_term_comparison": [
            {"publisher_host": entry["publisher_host"],
             "source_type": entry["source_type"],
             "literal_source_terms": entry["literal_terms_seen_on_page_not_clinically_validated"],
             "verified_service_availability": False}
            for entry in ledger
        ],
        "current_search_discovery": dict(discovery),
        "editorial_questions": questions,
        "buyer_first_sequence": (
            "independent_research", "editorially_approved_value", "rapport",
            "actual_buyer_problem", "scope", "proposal_only_after_interest"
        ),
        "recommendation_state": "REVIEW_QUESTIONS_ONLY_NO_CONCLUSIONS",
        "verified_buyer": False,
        "editorial_approval": False,
        "sources_reuse_licensed": False,
        "price_quote_authorized": False,
        "outbound_authorized": False,
        "client_delivery_authorized": False,
        "payment_authorized": False,
        "database_writes": False,
    }
