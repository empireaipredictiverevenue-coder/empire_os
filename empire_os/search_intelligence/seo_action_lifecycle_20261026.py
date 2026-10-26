"""Evidence-governed SEO operations lifecycle for the ORIGINAL EmpireOS owners.

Reads the original immutable Google index, weekly SEO growth, AEO release and
live buyer path reports. A health GET may automatically test a bounded owned
page. This module NEVER authorizes publication, redirects, external messages,
index submissions, payments or content generation. No second database.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

ORIGIN = "https://empire-ai.co.uk"
WEEKLY_SCHEMA = "empire.search.seo_growth_action_queue.v1"
DAILY_SCHEMA = "empire.search.google_index_daily_watch.v1"
AE0_SCHEMA = "empire.seo.original_gated_aeo_release_result.v1"
AEO_SOURCE_V2_SCHEMA = "empire.seo.original_gated_aeo_source_hint_release.v2"
ORIGINAL_INDEXED_URLS = {
    "https://empire-ai.co.uk/",
    "https://empire-ai.co.uk/commercial",
    "https://empire-ai.co.uk/industries/roofing",
    "https://empire-ai.co.uk/industries/solar",
    "https://empire-ai.co.uk/predictive-revenue",
}
VALID_GOOGLE_INDEX_STATES = {
    "GOOGLE_INDEXED_VERSION_VERIFIED",
    "GOOGLE_HAS_NO_URL_RECORD",
    "GOOGLE_INDEX_STATUS_NEEDS_REVIEW",
}
STATES = ("detected", "prioritised", "staged", "tested", "published", "verified", "measured")
PRIORITY = {
    "P0_TECHNICAL": 0, "P1_TECHNICAL": 1, "P1_CRITICAL_PAGE": 2,
    "P2_CTR_OPPORTUNITY": 3, "P2_INTERNAL_LINKS": 4,
    "P2_ORIGINAL_CONTENT_REVIEW": 5, "P2_CONTENT_EVIDENCE": 6,
    "P3_MEASURE_AND_IMPROVE": 7,
}
FIXED_AEO = {
    "/aeo/roofing/DFW", "/aeo/hvac/DFW", "/aeo/general_contractor/NYC"
}
ALLOWED_TECHNICAL = frozenset({
    "HTTP_200", "SELF_CANONICAL", "INDEXABILITY", "LIVE_COMMERCIAL_LINK"
})


class SEOActionHeld(ValueError):
    pass


def _path(url: Any) -> str:
    if not isinstance(url, str) or len(url) > 400:
        raise SEOActionHeld("INVALID_OWNED_ACTION_URL")
    try:
        p = urlsplit(url)
    except ValueError as exc:
        raise SEOActionHeld("INVALID_OWNED_ACTION_URL") from exc
    if (p.scheme != "https" or p.netloc != "empire-ai.co.uk"
        or p.username or p.password or p.query or p.fragment
        or not p.path.startswith("/") or "//" in p.path):
        raise SEOActionHeld("UNTRUSTED_ACTION_HOST_OR_PATH")
    return p.path.rstrip("/") or "/"


def _id(url: str, reason: str) -> str:
    return sha256(f"seo.v1|{url}|{reason}".encode()).hexdigest()[:20]


def _owner(code: str) -> str:
    if code in {"RELEVANT_HISTORICAL_404"}:
        return "original_website_editorial_owner"
    if code == "COMMERCIAL_CTA_TWO_HOPS":
        return "original_website_conversion_owner"
    if code == "NO_GSC_PAGE_ROW_RETURNED":
        return "original_search_console_owner"
    if code in {"LOW_VOLUME_OR_RECENT_PAGE_OBSERVATION", "OBSERVED_IMPRESSIONS_NO_CLICKS"}:
        return "original_seo_content_owner"
    return "original_website_technical_owner"


def _closed_live_action(item: dict, journey: Mapping[str, Any],
                        released: bool) -> tuple[str, str] | None:
    if item["reason_code"] != "COMMERCIAL_CTA_TWO_HOPS":
        return None
    path = _path(item["url"])
    by_route = {x.get("route"): x for x in journey.get("routes", [])
                if isinstance(x, dict)}
    row = by_route.get(path)
    if row is None or row.get("http_status") != 200 or row.get("issues"):
        return None
    if path in FIXED_AEO and released and "/commercial" in row.get("direct_buyer_destinations", []):
        return "verified", "ORIGINAL_RELEASE_RECEIPT_AND_LIVE_DIRECT_COMMERCIAL_LINK"
    if path.startswith("/research/") and row.get("first_party_research_enquiry_form_present") is True:
        return "verified", "ORIGINAL_CONSENTED_RESEARCH_ENQUIRY_FORM_ALREADY_PRESENT"
    return None


def _validated_index_states(daily: Mapping[str, Any]) -> dict[str, str] | None:
    """Use the original five-URL daily owner's ACTUAL mapping contract.

    Never transform a sitemap, page impressions or empty/malformed source
    into a fabricated indexed state.
    """
    values = daily.get("exact_url_states")
    if values is None:
        return None
    if (not isinstance(values, dict)
        or set(values) != ORIGINAL_INDEXED_URLS
        or any(value not in VALID_GOOGLE_INDEX_STATES
               for value in values.values())
        or daily.get("schema_version") != DAILY_SCHEMA
        or daily.get("status") != "GOOGLE_INDEX_WATCH_RECORDED"
        or daily.get("scope_checked") != 5
        or daily.get("google_indexing_submissions") != 0
        or daily.get("database_writes") is not False
        or daily.get("website_changed") is not False
        or daily.get("execution_authority") != "none"
        or daily.get("full_site_indexation_verified") is not False
        or daily.get("indexed_verified") != sum(
            state == "GOOGLE_INDEXED_VERSION_VERIFIED" for state in values.values())
        or daily.get("unknown_to_google") != sum(
            state == "GOOGLE_HAS_NO_URL_RECORD" for state in values.values())):
        raise SEOActionHeld("ORIGINAL_FIVE_URL_GOOGLE_INDEX_EVIDENCE_UNTRUSTED")
    return values


def _index_state(states: Mapping[str, str] | None, url: str) -> str | None:
    return states.get(url) if states is not None else None


def _original_canonical_sales_evidence(source: Mapping[str, Any] | None) -> dict[str, Any]:
    """Only accept the ORIGINAL GTM Ops sanitized count receipt, no SQL here.

    Even nonzero sitewide enquiry totals NEVER prove AEO origin, organic
    channel, exact CRM delivery, qualified buyers or settled money.
    """
    held = {
        "status": "CANONICAL_SOURCE_NOT_AVAILABLE",
        "sitewide_commercial_enquiries": None,
        "sitewide_predictive_enquiries": None,
        "sitewide_sales_acquisitions": None,
        "source_count_verified": False,
        "verified_aeo_origin_enquiries": None,
        "verified_organic_conversions": None,
        "exact_crm_enquiry_receipt_verified": False,
        "qualified_buyer_verified": False,
        "earned_revenue_verified": False,
        "next_existing_owner_action": "REVIEW_EXISTING_PRIVILEGED_OPS_CONTROL_COUNT_RECEIPT",
    }
    if source is None:
        return held
    if not isinstance(source, Mapping):
        raise SEOActionHeld("ORIGINAL_SALES_COUNT_RECEIPT_NOT_OBJECT")
    if source.get("source_count_verified") is False:
        # The existing owner rejects stale or broken Ops snapshots. No zeros.
        return held
    if (source.get("source_count_verified") is not True
        or source.get("exact_crm_readback_verified") is not False
        or source.get("specific_response_consent_current_verified") is not False
        or source.get("individual_buyer_identity_verified") is not False
        or source.get("outreach_authorized") is not False
        or source.get("payments_authorized") is not False
        or source.get("database_writes") is not False
        or source.get("execution_authority") != "none"):
        raise SEOActionHeld("ORIGINAL_SALES_COUNT_RECEIPT_EXCEEDS_AUTHORITY")
    c=source.get("canonical_commercial_enquiries")
    p=source.get("canonical_predictive_revenue_enquiries")
    n=source.get("canonical_sales_acquisitions")
    if (any(type(v) is not int or not 0 <= v <= 20_000_000
            for v in (c,p,n)) or c+p!=n):
        raise SEOActionHeld("ORIGINAL_SALES_COUNT_SOURCE_CONTRADICTORY")
    status=source.get("status")
    if n==0 and status=="CANONICAL_COMMERCIAL_SALES_INTAKE_ZERO_OBSERVED":
        action="IMPROVE_SEARCH_DISCOVERY_AND_WAIT_FOR_GENUINE_CONSENTED_ENQUIRY"
    elif n>0 and status in {
        "CANONICAL_SALES_ENQUIRIES_FOUNDER_BINDING_HOLD",
        "CANONICAL_SALES_ENQUIRIES_PRESENT_EXACT_READBACK_REQUIRED",
    }:
        action="REVIEW_EXISTING_CRM_OWNER_EXACT_REAL_ENQUIRY_LINEAGE"
    else:
        raise SEOActionHeld("ORIGINAL_SALES_COUNT_STATUS_UNTRUSTED")
    return {**held,
        "status": status,
        "sitewide_commercial_enquiries": c,
        "sitewide_predictive_enquiries": p,
        "sitewide_sales_acquisitions": n,
        "source_count_verified": True,
        "next_existing_owner_action": action,
    }


def build_seo_action_lifecycle(
    weekly: Mapping[str, Any], daily: Mapping[str, Any],
    *, buyer_journey: Mapping[str, Any] | None = None,
    aeo_release: Mapping[str, Any] | None = None,
    ops_sales: Mapping[str, Any] | None = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise SEOActionHeld("AWARE_OBSERVATION_TIME_REQUIRED")
    if (weekly.get("schema_version") != WEEKLY_SCHEMA
            or weekly.get("status") != "EVIDENCE_BACKED_ACTION_QUEUE_READY"
            or weekly.get("source_property") != "sc-domain:empire-ai.co.uk"
            or weekly.get("execution_authority") != "none"
            or weekly.get("website_changed") is not False
            or not isinstance(weekly.get("actions"), list)
            or len(weekly["actions"]) > 60):
        raise SEOActionHeld("ORIGINAL_WEEKLY_SEO_ACTION_EVIDENCE_REQUIRED")
    if (daily.get("schema_version") != DAILY_SCHEMA
            or daily.get("website_changed") is not False
            or daily.get("execution_authority") != "none"):
        raise SEOActionHeld("ORIGINAL_DAILY_GOOGLE_INDEX_EVIDENCE_REQUIRED")
    journey = buyer_journey or {}
    if journey and (journey.get("schema_version") != "empire.search.live_organic_to_buyer_observer.v1"
                    or journey.get("status") != "GET_ONLY_PUBLIC_DISCOVERY_AUDIT"
                    or journey.get("site_mutations") is not False):
        raise SEOActionHeld("ORIGINAL_LIVE_BUYER_PATH_REQUIRED")
    release = aeo_release or {}
    released_v1 = (
        release.get("schema_version") == AE0_SCHEMA
        and release.get("status") == "ORIGINAL_THREE_AEO_B2B_LINKS_GATED_RELEASE_LIVE_VERIFIED"
    )
    released_v2 = (
        release.get("schema_version") == AEO_SOURCE_V2_SCHEMA
        and release.get("status") == "ORIGINAL_THREE_AEO_SOURCE_HINT_RELEASE_LIVE_VERIFIED"
        and release.get("other_aeo_pages_untouched") == 207
        and release.get("no_database_writes") is True
        and release.get("no_indexing_submissions") is True
    )
    release_valid = (
        (released_v1 or released_v2)
        and release.get("original_release_valid") is True
        and release.get("exact_approved_pages") == 3
        and release.get("live_http_200_pages") == 3
    )
    index_states = _validated_index_states(daily)
    sales_evidence = _original_canonical_sales_evidence(ops_sales)

    actions = []
    seen = set()
    for source in weekly["actions"]:
        if not isinstance(source, Mapping):
            raise SEOActionHeld("UNTRUSTED_ACTION_OBJECT")
        url, code = source.get("url"), source.get("reason_code")
        path = _path(url)
        if not isinstance(code, str) or len(code) > 90:
            raise SEOActionHeld("INVALID_REASON_CODE")
        key = _id(url, code)
        if key in seen:
            raise SEOActionHeld("DUPLICATE_CANONICAL_SEO_ACTION")
        seen.add(key)
        priority = source.get("priority")
        if priority not in PRIORITY:
            raise SEOActionHeld("UNKNOWN_ORIGINAL_ACTION_PRIORITY")
        if (source.get("website_change_authorized") is not False
            or source.get("publication_authorized") is not False):
            raise SEOActionHeld("ACTION_EXCEEDS_ORIGINAL_AUTHORITY")

        state = "prioritised"
        outcome = "OPEN"
        stage_ready = False
        test_methods = []
        if code in {"COMMERCIAL_CTA_TWO_HOPS", "NO_GSC_PAGE_ROW_RETURNED",
                    "LOW_VOLUME_OR_RECENT_PAGE_OBSERVATION"}:
            # Stage deterministic evidence checks, not speculative publication.
            stage_ready = True
            test_methods = ["HTTP_200", "SELF_CANONICAL", "INDEXABILITY"]
            state = "staged"
        closed = _closed_live_action(dict(source), journey, release_valid)
        evidence = []
        if closed:
            state, outcome = closed
            evidence.append("existing_buyer_journey_GET_observation")
            if path in FIXED_AEO:
                evidence.append("original_AEO_gated_release_live_receipt")
        actions.append({
            "id": key, "url": url, "reason_code": code, "priority": priority,
            "owner": _owner(code), "source_as_of": weekly.get("as_of"),
            "state": state, "state_path": list(STATES[:STATES.index(state) + 1])
                          if not (state == "verified" and outcome.startswith("ORIGINAL_CONSENTED"))
                          else ["detected", "prioritised", "tested", "verified"],
            "outcome": outcome,
            "evidence_refs": evidence,
            "index_status_first_party": _index_state(index_states, url),
            "stage": {
                "status": "STAGED_SAFE_TECHNICAL_CHECKS" if stage_ready else "REVIEW_REQUIRED",
                "allowed_automatic_checks": test_methods if not closed else [],
                "publish_eligible": False,
                "source_owner": _owner(code),
            },
            "next_action": (
                "COMPARE_FINAL_GSC_AND_CONSENTED_ENQUIRY_OUTCOMES"
                if closed else source.get("next_action") or "REVIEW_SOURCE_EVIDENCE"
            ),
            "published_claim": bool(closed and closed[1].startswith("ORIGINAL_RELEASE")),
            "organic_visits_verified": False,
            "qualified_buyer_verified": False,
            "earned_revenue_verified": False,
        })
    actions.sort(key=lambda x: (PRIORITY[x["priority"]], x["url"]))
    counts = {x: sum(a["state"] == x for a in actions) for x in STATES}
    reached = {x: sum(x in a["state_path"] for a in actions) for x in STATES}
    return {
        "schema_version": "empire.search.seo_action_lifecycle.v1",
        "mode": "ORIGINAL_SEO_OPERATIONS",
        "observed_at": now.astimezone(timezone.utc).isoformat(),
        "daily_source_date": str(daily.get("observed_at") or ""),
        "weekly_source_as_of": weekly["as_of"],
        "original_action_count": len(actions),
        "lifecycle_states": list(STATES),
        "state_counts": counts,
        "milestone_reached_counts": reached,
        "resolved_existing_owner_actions": sum(a["state"] == "verified" for a in actions),
        "unresolved_actions": sum(a["state"] != "verified" for a in actions),
        "actions": actions,
        "canonical_sitewide_sales_evidence": sales_evidence,
        "sitewide_acquisitions_never_equated_with_aeo_or_search_attribution": True,
        "existing_ops_control_canonical_reader_reused": True,
        "existing_daily_and_weekly_owners_retained": True,
        "max_automated_checks_per_action": 3,
        "safe_checks_execute_without_site_mutation": True,
        "automated_publication_authorized": False,
        "commercial_terms_approved": False,
        "indexing_requests_submitted": 0,
        "database_writes": False,
        "outbound_sent": False,
        "payment_actions": False,
        "actual_rank_uplift_verified": False,
        "verified_revenue": None,
        "execution_authority": "OBSERVE_WITH_BOUNDED_READ_ONLY_TESTS",
    }
