"""Explainable CRM customer-result milestones for the existing preview route.

The caller controls all fields in the /customer-success/preview request.
These are assertions to REVIEW, never independently authenticated evidence.
A nice dashboard must not launder submitted 'payment_verified=true' into a
verified payment or recognized revenue claim. Pure/read-only, no new tables.
"""
from __future__ import annotations

from typing import Any
from empire_os.revenue_crm_retention import RevenueCrmRetentionEvidence
from empire_os.revenue_crm_retention_freshness import RevenueCrmRetentionFreshness
from empire_os.revenue_crm_customer_success import CustomerSuccessReviewRoute

SCHEMA = "empire.revenue_crm.customer_results_experience.v1"

STAGES = (
    ("buyer", "Buyer and scope", "CONFIRM_CANONICAL_BUYER_AND_TENANT"),
    ("payment", "Payment receipt", "RECONCILE_ORIGINAL_PAYMENT_RECEIPT"),
    ("fulfilment", "Delivery and fulfilment", "VERIFY_FULFILMENT_ACCEPTANCE"),
    ("outcome", "Customer result", "VERIFY_ORIGINAL_CUSTOMER_OUTCOME"),
    ("capacity", "Service expansion capacity", "VERIFY_CURRENT_BUYER_CAPACITY"),
)

# Every stage must have independently sourced custody before customer-visible
# proof could ever be enabled by a separate authenticated endpoint.
def review_customer_results_experience(
    evidence: RevenueCrmRetentionEvidence,
    freshness: RevenueCrmRetentionFreshness,
    proposed_route: CustomerSuccessReviewRoute,
) -> dict[str, Any]:
    evidence.validate()
    if (freshness.buyer_id != evidence.buyer_id
            or proposed_route.buyer_id != evidence.buyer_id
            or freshness.execution_authority != "none"
            or proposed_route.execution_authority != "none"
            or proposed_route.follow_up_execution is not False
            or proposed_route.payment_execution is not False
            or proposed_route.crm_mutation is not False
            or proposed_route.offer_mutation is not False
            or freshness.follow_up_execution is not False
            or freshness.payment_execution is not False
            or freshness.crm_mutation is not False
            or freshness.offer_mutation is not False):
        raise ValueError("customer results preview contract untrusted")
    ages = freshness.ages_seconds
    if not isinstance(ages, dict) or any(
        type(value) not in (int, float) or value < -60
        for value in ages.values()
    ):
        raise ValueError("untrusted customer milestone timing")
    blockers = set(freshness.blockers)
    def safe(label: str) -> bool:
        if label not in ages:
            return False
        return not any(
            f"{label}_{reason}" in blockers for reason in (
                "evidence_stale", "evidence_from_future",
                "timestamp_missing",
            )
        )
    assertions = {
        "buyer": bool(evidence.buyer_activated and
                      str(evidence.buyer_evidence_ref or "").strip()),
        "payment": bool(evidence.payment_verified and
                        str(evidence.payment_evidence_ref or "").strip()),
        "fulfilment": bool(evidence.fulfilment_delivered and
                            str(evidence.fulfilment_evidence_ref or "").strip()),
        "outcome": bool(evidence.outcome_observed and
                        str(evidence.outcome_evidence_ref or "").strip()),
        "capacity": bool(
            evidence.buyer_available_capacity is not None
            and evidence.buyer_available_capacity > 0
            and str(evidence.capacity_evidence_ref or "").strip()
        ),
    }
    descriptions = {
        "buyer": "Confirm the correct buyer organisation, account and market.",
        "payment": "Reconcile an original payment record to the correct order.",
        "fulfilment": "Check delivery evidence and buyer acceptance.",
        "outcome": "Confirm the actual customer result, not merely delivery.",
        "capacity": "Verify the latest permitted allocation and delivery capacity.",
    }
    milestones = []
    for key, label, next_action in STAGES:
        reported = assertions[key]
        if key == "outcome" and reported and evidence.outcome_success_verified is False:
            state = "UNSUCCESSFUL_OUTCOME_REPORTED_NOT_VERIFIED" if safe(key) else "STALE_OR_INVALID_ASSERTION"
        elif reported and safe(key):
            state = "REPORTED_IN_PREVIEW_NOT_AUTHENTICATED"
        elif reported:
            state = "STALE_OR_INVALID_ASSERTION"
        else:
            state = "MISSING_OR_UNCONFIRMED_ASSERTION"
        milestones.append({
            "stage": key,
            "label": label,
            "state": state,
            "preview_claim_present": reported,
            "independently_verified": False,
            "customer_visible_proof_authorized": False,
            "required_next_action": next_action,
            "explanation": descriptions[key],
        })

    first_issue = next(
        (x for x in milestones if x["state"] not in
         ("REPORTED_IN_PREVIEW_NOT_AUTHENTICATED",)), None
    )
    # Even when every caller assertion appears internally consistent,
    # independent source, authority and tenant custody remain necessary.
    next_action = (
        first_issue["required_next_action"] if first_issue
        else "INDEPENDENT_SOURCE_AUTHENTICATION_AND_TENANT_BINDING"
    )
    reported_count = sum(
        x["state"] == "REPORTED_IN_PREVIEW_NOT_AUTHENTICATED"
        for x in milestones
    )
    return {
        "schema_version": SCHEMA,
        "mode": "PREVIEW_ONLY",
        "status": "CUSTOMER_RESULTS_AWAITING_INDEPENDENT_PROOF",
        "source_claim_class": "CALLER_SUPPLIED_UNVERIFIED_ASSERTIONS",
        "reported_milestones_with_valid_preview_timing": reported_count,
        "independently_verified_milestone_count": 0,
        "total_milestones": len(STAGES),
        "milestones": milestones,
        "next_evidence_action": next_action,
        "underlying_route_preview": (
            proposed_route.review_type if proposed_route.available else None
        ),
        "underlying_route_is_verified_customer_result": False,
        "tenant_authority_verified_by_this_preview": False,
        "original_source_authentication_verified": False,
        "verified_customer_outcome": None,
        "verified_realized_revenue_cents": None,
        "verified_customer_roi": None,
        "customer_visible_proof_authorized": False,
        "payment_action_authorized": False,
        "automatic_outbound_authorized": False,
        "crm_mutation": False,
        "economic_memory_updated": False,
        "execution_authority": "none",
    }
