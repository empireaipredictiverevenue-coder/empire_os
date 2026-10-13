"""Read-only enterprise commercial review from existing scout evidence.

Company identity, locations and inferred product mappings are research only.
This module never grants recipient clearance, buyer demand or send authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from empire_os.predictive_revenue_enterprise_location import location_from_addresses


def _key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (str(row.get("domain") or "").lower().strip(),
            str(row.get("candidate_id") or "").strip())


def build_review(
    pool: Mapping[str, Any],
    locations: Mapping[str, Any],
    promotion: Mapping[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    if (pool.get("mode") != "OBSERVE"
            or locations.get("mode") != "OBSERVE"
            or promotion.get("mode") != "OBSERVE"
            or promotion.get("outbound_sent") is not False
            or pool.get("outreach_authorized") is not False
            or locations.get("outreach_authorized") is not False):
        raise ValueError("UNTRUSTED_ENTERPRISE_REVIEW_SOURCES")
    candidates = pool.get("rolling_candidates")
    location_rows = locations.get("candidates")
    proposals = promotion.get("proposals")
    if (not isinstance(candidates, list) or len(candidates) > 50
            or not isinstance(location_rows, list)
            or not isinstance(proposals, list)):
        raise ValueError("INVALID_ENTERPRISE_REVIEW_COHORT")

    selected = {_key(row): row for row in candidates if isinstance(row, Mapping)}
    promoted = {_key(row): row for row in proposals if isinstance(row, Mapping)}
    packets: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in location_rows:
        if (not isinstance(row, Mapping)
                or row.get("location_verified") is not True
                or row.get("site_probe_ok") is not True
                or row.get("location_source") != "first_party_site_address"):
            continue
        key = _key(row)
        current, proposal = selected.get(key), promoted.get(key)
        if not current or not proposal or key in seen:
            continue
        if any(str(row.get(field) or "").strip() != str(current.get(field) or "").strip()
               for field in ("account_name", "website")):
            continue
        place = location_from_addresses(row.get("location_evidence_addresses") or [])
        if not place or place.get("metro") != row.get("metro"):
            continue
        seen.add(key)
        readiness = current.get("commercial_readiness") or {}
        fit = readiness.get("state") == "FIT_REVIEW"
        product_codes = list(current.get("target_product_codes") or [])
        source_prospect_ids = proposal.get("source_prospect_ids") or []
        blockers = [
            "BUYING_INTENT_UNVERIFIED", "PRODUCT_NEED_UNVERIFIED",
            "PERSON_EMAIL_BINDING_UNVERIFIED", "PRIOR_CONTACT_RECHECK_REQUIRED",
            "RECIPIENT_SUPPRESSION_CHECK_REQUIRED", "FOUNDER_SEND_GATE_REQUIRED",
        ]
        if not fit:
            blockers.append("PRODUCT_OR_FIRST_PARTY_PERSON_REVIEW_REQUIRED")
        if not source_prospect_ids:
            blockers.append("CANONICAL_PROSPECT_LINK_UNAVAILABLE")
        packets.append({
            "account_name": current.get("account_name"),
            "domain": key[0],
            "candidate_id": key[1],
            "location": place["metro"],
            "location_source": row.get("location_source"),
            "fit_state": "FIT_REVIEW" if fit else "RESEARCH_ONLY",
            "product_codes_research_only": product_codes,
            "observed_first_party_person": readiness.get("first_party_person_observed") is True,
            "source_prospect_binding_present": bool(source_prospect_ids),
            "priority": "REVIEW_PRODUCT_FIT_AND_BUYER_ROLE" if fit else "COMPLETE_RESEARCH_EVIDENCE",
            "blockers": blockers,
            "person_email_binding_verified": False,
            "prior_contact_status": "UNKNOWN_RECHECK_REQUIRED",
            "suppression_status": "UNKNOWN_SEND_TIME_CHECK_REQUIRED",
            "verified_buying_intent": False,
            "commercially_qualified": False,
            "outreach_authorized": False,
        })
    packets.sort(key=lambda r: (r["fit_state"] != "FIT_REVIEW", r["domain"]))
    return {
        "schema_version": "empire.predictive-revenue-enterprise-commercial-review.v1",
        "mode": "OBSERVE",
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "research_pool_count": len(candidates),
        "location_verified_current_count": len(packets),
        "fit_review_current_count": sum(r["fit_state"] == "FIT_REVIEW" for r in packets),
        "commercially_qualified_count": 0,
        "packets": packets,
        "database_write_performed": False,
        "outbound_sent": False,
        "outreach_authorized": False,
        "payment_action": False,
        "execution_authority": "none",
    }
