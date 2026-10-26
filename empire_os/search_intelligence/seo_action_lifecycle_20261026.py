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


def _index_state(daily: Mapping[str, Any], url: str) -> str | None:
    rows = daily.get("exact_url_states")
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, dict) and row.get("url") == url:
            # No inference from GSC page impressions.
            return str(row.get("state") or row.get("status") or "UNKNOWN")
    return None


def build_seo_action_lifecycle(
    weekly: Mapping[str, Any], daily: Mapping[str, Any],
    *, buyer_journey: Mapping[str, Any] | None = None,
    aeo_release: Mapping[str, Any] | None = None,
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
    release_valid = (
        release.get("schema_version") == AE0_SCHEMA
        and release.get("status") == "ORIGINAL_THREE_AEO_B2B_LINKS_GATED_RELEASE_LIVE_VERIFIED"
        and release.get("original_release_valid") is True
        and release.get("exact_approved_pages") == 3
        and release.get("live_http_200_pages") == 3
    )

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
            "index_status_first_party": _index_state(daily, url),
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
