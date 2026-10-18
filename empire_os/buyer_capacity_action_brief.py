"""Read-only actionable buyer-capacity evidence brief for Predictive Revenue.

Consumes *only* the already-validated Astra founder executive projection.
Aggregates may be nonzero for different buyers: they never establish a single
buyer buy-box, permission to send, a payout, or delivery readiness.
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA_VERSION = "empire.predictive_revenue.buyer_capacity_action_brief.v1"
SOURCE_SCHEMA = "empire.founder.executive_roles_status.v1"
SOURCE_STATUSES = frozenset({
    "SOURCE_MISSING", "SOURCE_UNTRUSTED", "SOURCE_STALE",
    "NO_VERIFIED_COMMERCIAL_CAPACITY", "AGGREGATE_CAPACITY_NOT_SPECIFIC_BUYBOX",
})
STAGES = (
    ("reviewed", "VERIFY_EXISTING_BUYER_IDENTITY",
     "Confirm the actual buyer organisation, authorised decision-maker and present relationship"),
    ("market_defined", "VERIFY_MARKET_AND_PRODUCT_BUYBOX",
     "Confirm product/vertical, geography or postcodes, eligible customer and exclusions"),
    ("positive_capacity_configured", "VERIFY_PURCHASE_VOLUME_AND_CAP",
     "Obtain buyer-specific demand, acceptable volume, remaining capacity and period"),
    ("capacity_verified", "VERIFY_CURRENT_BUYER_CAPACITY_EVIDENCE",
     "Obtain dated evidence that this same buyer can accept the proposed volume"),
    ("terms_verified", "VERIFY_AGREED_BUYER_PRICING_AND_TERMS",
     "Confirm buyer-specific price or payout, valid terms and acceptance"),
    ("delivery_destination_present", "VERIFY_DESTINATION_AND_CHANNEL",
     "Record a verified buyer delivery destination and approved channel"),
    ("delivery_verified", "VERIFY_DELIVERY_ACCEPTANCE_EVIDENCE",
     "Confirm an independently observed successful destination/acceptance test"),
    ("commercially_activated", "VERIFY_COMMERCIAL_ACTIVATION",
     "Confirm current activation evidence against the same buyer and buy-box"),
)
MAX_COUNT = 10_000_000


def _hold(reason: str, source_status: str = "UNAVAILABLE") -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SOURCE_HOLD",
        "reason": reason,
        "source_status": source_status,
        "owner": "business_development",
        "next_action": "VERIFY_DOWNSTREAM_BUYER_TERMS_CAPACITY",
        "verified_specific_buybox_count": None,
        "buyers_seen": None,
        "evidence_checklist": [],
        "first_missing_evidence": None,
        "same_buyer_cross_stage_binding_proven": False,
        "publisher_payout_can_be_quoted": False,
        "lead_delivery_authorized": False,
        "execution_authority": "none",
        "work_dispatched": False,
    }


def build_buyer_capacity_action_brief(
    executive: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Describe the next commercial proof without reading customer identities."""
    if (not isinstance(executive, Mapping)
            or executive.get("available") is not True
            or executive.get("schema_version") != SOURCE_SCHEMA
            or executive.get("mode") != "OBSERVE"
            or executive.get("execution_authority") != "none"):
        return _hold("validated_executive_projection_required")
    business = executive.get("business_development")
    capacity = business.get("downstream_buyer_capacity") if isinstance(business, Mapping) else None
    if not isinstance(capacity, Mapping):
        return _hold("buyer_capacity_source_unavailable")
    source_status = capacity.get("status")
    if source_status not in SOURCE_STATUSES:
        return _hold("buyer_capacity_unknown_status")
    if (capacity.get("specific_buybox_verified") is not False
            or capacity.get("publisher_payout_can_be_quoted") is not False
            or capacity.get("lead_delivery_authorized") is not False):
        return _hold("buyer_capacity_authority_inconsistent", str(source_status))
    if source_status in {"SOURCE_MISSING", "SOURCE_UNTRUSTED", "SOURCE_STALE"}:
        return _hold("buyer_capacity_evidence_not_current", source_status)

    fields = ("buyers_seen", *(name for name, _, _ in STAGES))
    counts: dict[str, int] = {}
    for name in fields:
        value = capacity.get(name)
        if type(value) is not int or not 0 <= value <= MAX_COUNT:
            return _hold("buyer_capacity_aggregate_count_missing_or_invalid", source_status)
        counts[name] = value
    seen = counts["buyers_seen"]
    if any(n > seen for n in counts.values()):
        return _hold("aggregate_count_exceeds_buyer_inventory", source_status)
    aggregate_complete = all(counts[key] > 0 for key in (
        "capacity_verified", "terms_verified", "delivery_verified",
        "commercially_activated",
    ))
    if (aggregate_complete !=
            (source_status == "AGGREGATE_CAPACITY_NOT_SPECIFIC_BUYBOX")):
        return _hold("buyer_capacity_status_and_aggregate_counts_disagree", source_status)

    checklist = [
        {
            "evidence_key": key,
            "action_code": action,
            "requirement": requirement,
            "owner": "business_development",
            "aggregate_observed_count": counts[key],
            "status": ("NO_AGGREGATE_PROOF" if counts[key] == 0
                       else "AGGREGATE_EXISTS_NOT_SAME_BUYER_PROOF"),
            "same_buyer_verified": False,
            "execution_authority": "none",
        }
        for key, action, requirement in STAGES
    ]
    first_missing = next(
        (row["action_code"] for row in checklist
         if row["status"] == "NO_AGGREGATE_PROOF"), None
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "BUYER_BUYBOX_EVIDENCE_REQUIRED",
        "reason": ("aggregates_do_not_prove_a_specific_paying_buyer"
                   if first_missing is None else "missing_stage_aggregate_and_buybox_binding"),
        "source_status": source_status,
        "owner": "business_development",
        "next_action": "VERIFY_DOWNSTREAM_BUYER_TERMS_CAPACITY",
        "verified_specific_buybox_count": 0,
        "buyers_seen": seen,
        "evidence_checklist": checklist,
        "first_missing_evidence": first_missing or "BIND_ALL_EVIDENCE_TO_ONE_BUYER_BUYBOX",
        "same_buyer_cross_stage_binding_proven": False,
        "publisher_payout_can_be_quoted": False,
        "lead_delivery_authorized": False,
        "execution_authority": "none",
        "work_dispatched": False,
    }
