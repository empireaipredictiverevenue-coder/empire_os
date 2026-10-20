"""Bounded evidence-chain audit for one original multi-industry commercial draft.

Consumes only existing Predictive, A2A, Buyer Scout, Lead Supply and Finance
read-only contracts. An owner *research* receipt, source-reported inventory,
file digest or hypothetical cloud scenario is never customer acceptance.
No external calls, side effects or new owner queues.
"""
from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

from empire_os.predictive_commercial_requirements import SCHEMA as REQUIREMENT
from empire_os.predictive_commercial_fulfilment import SCHEMA as PLAN
from empire_os.predictive_commercial_supply_readiness import SCHEMA as SUPPLY
from empire_os.predictive_existing_owner_pickup import SCHEMA as OWNER, A2A_SCHEMA
from empire_os.enterprise_finance_evidence_readiness import SCHEMA as FINANCE

SCHEMA = "empire.predictive_revenue.original_commercial_evidence_chain.v1"
_SHA = re.compile(r"^[0-9a-f]{64}$")


def review_original_commercial_evidence_chain(
    requirement: Mapping[str, Any],
    plan: Mapping[str, Any],
    supply: Mapping[str, Any],
    finance: Mapping[str, Any],
    a2a: Mapping[str, Any],
    owners: Mapping[str, Any],
    *,
    original_intake_bytes_sha256: str | None,
) -> dict[str, Any]:
    """Return source-linked blockers, never certify commercial truth itself."""
    if not all(isinstance(x, Mapping) for x in (
        requirement, plan, supply, finance, a2a, owners,
    )):
        raise ValueError("bounded original owner reports required")
    revision = requirement.get("requirement_revision_sha256")
    if not isinstance(revision, str) or not _SHA.fullmatch(revision):
        raise ValueError("original requirement revision SHA required")
    if (original_intake_bytes_sha256 is not None and (
        not isinstance(original_intake_bytes_sha256, str)
        or not _SHA.fullmatch(original_intake_bytes_sha256)
    )):
        raise ValueError("original intake bytes SHA invalid")
    if (requirement.get("schema_version") != REQUIREMENT
            or requirement.get("status") != "COMMERCIAL_REQUIREMENT_INCOMPLETE"
            or requirement.get("execution_authority") != "none"
            or plan.get("schema_version") != PLAN
            or plan.get("original_requirement_revision_sha256") != revision
            or plan.get("execution_authority") != "none"
            or supply.get("schema_version") != SUPPLY
            or supply.get("execution_authority") != "none"
            or finance.get("schema_version") != FINANCE
            or finance.get("execution_authority") != "none"
            or a2a.get("schema_version") != A2A_SCHEMA
            or a2a.get("reviewed_original_requirement_revision_sha256") != revision
            or a2a.get("execution_authority") != "none"
            or owners.get("schema_version") != OWNER
            or owners.get("original_requirement_revision_sha256") != revision
            or owners.get("execution_authority") != "none"):
        raise ValueError("mixed or elevated owner evidence provenance")
    if any(supply.get(k) != requirement.get(v) for k, v in (
        ("research_target_industry", "industry"),
        ("research_target_market_country", "country"),
        ("research_target_market_state", "state"),
        ("research_target_market_city", "city"),
    )):
        raise ValueError("cross-market lead supply provenance")
    if (a2a.get("reviewed_industry") != requirement.get("industry")
            or a2a.get("reviewed_city_region") != (
                requirement["city"] + ", " + requirement["state"]
            ).casefold()):
        raise ValueError("cross-market A2A source provenance")
    actions = owners.get("owner_required_action_queue")
    if (not isinstance(actions, list) or len(actions) != 8
            or any(not isinstance(item, Mapping)
                   or item.get("original_cryptographic_owner_acknowledgement") is not None
                   or item.get("live_service_execution_eligible") is not False
                   for item in actions)):
        raise ValueError("not an original unaccepted eight-owner plan")
    if (owners.get("owner_handoffs_dispatched") != 0
            or owners.get("original_owner_requirements_accepted") is not False
            or owners.get("original_customer_contract_verified") is not False
            or plan.get("owner_handoff_delivery_receipts") != 0
            or requirement.get("source_customer_order_authenticated") is not False):
        raise ValueError("unverified draft self-promoted into execution")

    stages = [
        ("CUSTOMER_ORDER_AND_BUYING_AUTHORITY",
         "Original tenant-scoped order, buyer role and purchasing authority from canonical customer owner"),
        ("REQUIREMENT_BOUND_OWNER_ACCEPTANCE",
         "Original signed receipt for THIS requirement revision from the existing authenticated owner"),
        ("CONSENTED_GEO_ELIGIBLE_SUPPLY",
         "Canonical unique event IDs, consent, ZIP scope, ownership, resale and exclusivity clearance"),
        ("ACCEPTED_PRICE_AND_TRUE_COST",
         "Original buyer terms, supplier quotes, accepted price, refund and delivery cost"),
        ("ORIGINAL_PROSPECTIVE_PREDICTION",
         "Prediction registered before the independently authenticated customer outcome"),
        ("SETTLED_OUTCOME_AND_PREDICTION_ERROR",
         "Canonical paid/settled outcome, realised gross profit and paired prediction-error record"),
    ]
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "ORIGINAL_COMMERCIAL_EVIDENCE_NOT_YET_ADMITTED",
        "original_requirement_revision_sha256": revision,
        "original_intake_bytes_sha256_untrusted_file_identity": original_intake_bytes_sha256,
        "source_intake_fingerprinted_not_customer_authenticated": original_intake_bytes_sha256 is not None,
        "research_tickets_are_not_original_requirement_acks": True,
        "a2a_source_reported_replies_not_independent_customer_proof":
            a2a.get("original_owner_authenticated_reply_count"),
        "global_supply_not_customer_eligible_inventory":
            supply.get("global_immediately_sellable_inventory"),
        "global_finance_status_not_customer_settlement":
            finance.get("status"),
        "stages": [
            {"stage": name, "status": "AWAITING_AUTHENTICATED_ORIGINAL_EVIDENCE",
             "required_proof": proof}
            for name, proof in stages
        ],
        "first_unmet_stage": stages[0][0],
        "existing_owner_queue_count": len(actions),
        "existing_owner_acceptance_verified": False,
        "authenticated_customer_order_verified": False,
        "verified_customer_specific_lead_inventory": None,
        "authenticated_realized_gross_profit_minor": None,
        "original_registered_prediction_and_outcome_matched": False,
        "commercial_execution_eligible": False,
        "cloud_learning_eligible": False,
        "source_owner_data_mutated": False,
        "database_writes": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }
