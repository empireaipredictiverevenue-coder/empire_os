"""First-party commercial evidence acquisition from existing revenue pathways.

Closes a *research routing* gap, NOT the commercial buyer gap itself.
Exactly one same-key candidate, recent canonical snapshots, no generic LLM
predictions or public permit/search signal promoted into buyer acceptance.
Uses the existing ASTRA department queue and worker, £0 external budget.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping

from empire_os.revenue_evidence_pathways import (
    SCHEMA as PATHWAYS_SCHEMA,
    review_evidence_pathways_runtime,
)
from empire_os.quant_brain import _DECISION_PACKET_REQUIRED

SCHEMA = "empire.predictive_revenue.buyer_evidence_handoff.v1"
RESEARCH_SCHEMA = "empire.predictive_revenue.buyer_evidence_request.v1"
TARGET = "existing_opportunity_factory_commercial_evidence"
GOAL = "verify_first_party_commercial_buyer_evidence"
ACTION = "review_existing_crm_buyer_interest_and_offer_terms_without_outbound"
REQUIRED_FIRST_FACT = "buyer_intent_normalized_score_required"
MAX_REQUESTS = 1

# Scientific evidence requirements, not values. No model may replace these
# authoritative first-party or independently reconciled observations.
EVIDENCE_CUSTODY = {
    "buyer_intent_normalized_score_required": "CANONICAL_REPLY_OR_SIGNED_BUYING_BRIEF",
    "demand_normalized_score_required": "FIRST_PARTY_PURCHASE_REQUIREMENTS",
    "distribution_path_required": "BUYER_SPECIFIC_DELIVERY_ACCEPTANCE",
    "offer_key_required": "EXISTING_VERIFIED_OFFER_PRODUCT",
    "probability_success": "TEMPORAL_HOLDOUT_PRIOR_VERIFIED_TERMINAL_OUTCOMES",
    "conditional_revenue_cents": "BUYER_SPECIFIC_WRITTEN_PRICE_TERMS",
    "fixed_cost_cents": "INDEPENDENT_FIXED_COST_RECORD",
    "success_cost_cents": "VERIFIED_FULFILMENT_UNIT_COST",
    "revenue_low_cents": "SOURCED_CONDITIONAL_REVENUE_LOWER_BOUND",
    "revenue_high_cents": "SOURCED_CONDITIONAL_REVENUE_UPPER_BOUND",
    "success_cost_low_cents": "SOURCED_SUCCESS_COST_LOWER_BOUND",
    "success_cost_high_cents": "SOURCED_SUCCESS_COST_UPPER_BOUND",
    "uncertainty": "DOCUMENTED_ESTIMATOR_AND_VALIDATION_ERROR",
    "time_to_revenue_days": "HISTORICAL_VERIFIED_SETTLEMENT_TIMELINE",
    "confidence": "VALIDATED_PREDICTIVE_COVERAGE_NOT_LLM_CERTAINTY",
}
if set(_DECISION_PACKET_REQUIRED) - set(EVIDENCE_CUSTODY):
    raise RuntimeError("Quant Brain evidence custody mapping missing a factor")


class CommercialResearchHold(ValueError):
    pass


def _aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("timezone-aware commercial evidence clock required")
    return value.astimezone(timezone.utc)


def _pathway_candidate(
    root: Path,
    *,
    as_of: datetime,
    limit: int = 5,
) -> tuple[dict[str, Any], dict[str, Any]]:
    report = review_evidence_pathways_runtime(root, as_of=as_of, limit=limit)
    if (report.get("schema_version") != PATHWAYS_SCHEMA
            or report.get("status") != "EVIDENCE_PATHWAY_REVIEW_READY"
            or report.get("source_snapshot_count") != 4
            or report.get("source_join_exact_identity_enforced") is not True
            or report.get("execution_authority") != "none"
            or report.get("economic_memory_updated") is not False
            or report.get("model_weights_updated") is not False):
        raise CommercialResearchHold("authoritative_current_pathways_not_ready")
    eligible = [
        row for row in report.get("research_shortlist", [])
        if row.get("next_owner") == "business_development"
        and row.get("first_unverified_requirement") == REQUIRED_FIRST_FACT
        and row.get("missing_quant_factor_count", 0) > 0
        and row.get("buyer_or_contract_verified") is False
        and row.get("recognized_revenue_cents") is None
    ]
    if not eligible:
        raise CommercialResearchHold("no_verified_current_buyer_evidence_gap_in_shortlist")
    item = eligible[0]
    if (not isinstance(item.get("opportunity_ref"), str)
            or not item["opportunity_ref"].startswith("oppref_")
            or len(item["opportunity_ref"]) != 27
            or not isinstance(item.get("missing_quant_factors"), list)
            or len(item["missing_quant_factors"]) != len(set(item["missing_quant_factors"]))
            or any(field not in _DECISION_PACKET_REQUIRED
                   for field in item["missing_quant_factors"])):
        raise CommercialResearchHold("invalid_quant_missing_factor_contract")
    return report, item


def _fingerprint(item: Mapping[str, Any]) -> str:
    # Stable across generated_at changes; changes when SAME candidate's
    # facts/blockers differ. No raw names or personally identifying records.
    source = {
        "opportunity_ref": item["opportunity_ref"],
        "next_owner": item["next_owner"],
        "first_unverified_requirement": item["first_unverified_requirement"],
        "missing_quant_factors": sorted(item["missing_quant_factors"]),
        "factory_blocker_count": item["factory_blocker_count"],
        "blocker_groups": dict(item["blocker_groups"]),
        "contradictions": list(item["contradictions_to_investigate"]),
    }
    return sha256(json.dumps(source, sort_keys=True,
                             separators=(",", ":")).encode()).hexdigest()


def review_one_commercial_evidence_request(
    repo_root: Path,
    *,
    as_of: datetime,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    now = _aware(as_of)
    try:
        report, item = _pathway_candidate(root, as_of=now)
    except CommercialResearchHold as exc:
        return {
            "schema_version": SCHEMA,
            "status": "HELD_NO_CURRENT_FIRST_PARTY_GAP",
            "reason_code": str(exc),
            "candidate_count_in_authoritative_view": None,
            "request": None,
            "internal_work_created": False,
            "buyer_contacted": False,
            "forecast_created": False,
            "actual_revenue_verified": False,
            "execution_authority": "none",
        }
    missing = item["missing_quant_factors"]
    request = {
        "schema_version": RESEARCH_SCHEMA,
        "opportunity_ref": item["opportunity_ref"],
        "niche": (
            item["niche"] if isinstance(item.get("niche"), str)
            and re.fullmatch(r"[a-z][a-z0-9_]{0,79}", item["niche"])
            else None
        ),
        "source_pathway_fingerprint": _fingerprint(item),
        "first_missing_evidence": item["first_unverified_requirement"],
        "required_authoritative_source": EVIDENCE_CUSTODY[REQUIRED_FIRST_FACT],
        "quant_gaps": [
            {"factor": field, "required_source": EVIDENCE_CUSTODY[field]}
            for field in _DECISION_PACKET_REQUIRED if field in missing
        ],
        "independent_custody": "CANONICAL_CRM_BUYER_REPLY_AND_CONTRACT_EVIDENCE",
        "research_question": (
            "Is there a genuine first-party buyer buying brief, product fit, "
            "price/terms and postcode or service-area acceptance for THIS "
            "specific public market opportunity?"
        ),
        "negative_control": (
            "reject public tenders, search impressions, directory listings, "
            "email sends and agent-created drafts as first-party buyer interest"
        ),
        "evidence_required_to_progress": [
            "existing_authoritative_customer_organisation_and_market",
            "verified_inbound_buyer_request_or_authorised_written_terms",
            "exact_product_and_location_scope",
            "existing_delivery_acceptance_and_capacity",
            "verifiable_price_and_cost_provenance",
        ],
        "testable_hypothesis_not_a_verified_sale": True,
        "buyer_identity_or_contact_exported": False,
        "automatic_email_or_offer_authorized": False,
        "quant_probability_source_verified": False,
        "model_training_authorized": False,
        "execution_authority": "none",
    }
    return {
        "schema_version": SCHEMA,
        "status": "ONE_INTERNAL_EVIDENCE_REQUEST_PREPARED",
        "generated_at": now.isoformat(),
        "candidate_count_in_authoritative_view": report["candidate_count"],
        "quant_complete_count": report["quant_complete_count"],
        "request": request,
        "internal_work_created": False,
        "buyer_contacted": False,
        "forecast_created": False,
        "actual_revenue_verified": False,
        "execution_authority": "none",
    }


def enqueue_one_commercial_evidence_request(
    repo_root: Path,
    prepared: Mapping[str, Any],
    *,
    as_of: datetime,
    allow_noncanonical_test: bool = False,
) -> dict[str, Any]:
    """Optional, ONE zero-spend existing ASTRA internal queue handoff."""
    from empire_os.department_work_queue import DepartmentWorkQueue

    root = Path(repo_root).resolve()
    if root != Path("/srv/empire_os") and not allow_noncanonical_test:
        raise PermissionError("canonical ASTRA internal queue required")
    now = _aware(as_of)
    current = review_one_commercial_evidence_request(root, as_of=now)
    if (current.get("status") != "ONE_INTERNAL_EVIDENCE_REQUEST_PREPARED"
            or not isinstance(prepared, Mapping)
            or prepared.get("schema_version") != SCHEMA
            or prepared.get("status") != current["status"]
            or prepared.get("request") != current["request"]
            or prepared.get("execution_authority") != "none"
            or prepared.get("internal_work_created") is not False
            or prepared.get("buyer_contacted") is not False
            or prepared.get("forecast_created") is not False):
        raise CommercialResearchHold("commercial_handoff_source_drift_or_tampering")
    request = current["request"]
    assert request is not None
    fingerprint = request["source_pathway_fingerprint"]
    step = {
        "step_id": "first_party_buyer_review_" + fingerprint[:24],
        "goal_key": GOAL,
        "department_keys": ["business_development"],
        "target_component": TARGET,
        "action": ACTION,
        "authority": "observe",
        "evidence_refs": [
            "runtime:opportunity_factory/intake_latest.json",
            "runtime:opportunity_factory/evidence_routes_latest.json",
            "runtime:opportunity_factory/quant_review_latest.json",
        ],
        "rationale": (
            "Obtain first-party buying evidence for one existing opportunity "
            "before any Quant prediction, product quote or outbound"
        ),
        "success_condition": (
            "Internal scientific gap review; first-party CRM buying intent "
            "and price/cost custody remain independently unverified"
        ),
        "intelligence_request": {
            "first_party_buyer_evidence": request,
            "budget": {
                "requested_model_tokens": 0,
                "requested_external_cost_cents": 0,
            },
        },
    }
    item, created = DepartmentWorkQueue(root).enqueue_step(
        plan_id="predictive_revenue_first_party_buyer_evidence_v1",
        step=step,
        priority=96,
    )
    return {
        "schema_version": "empire.predictive_revenue.buyer_evidence_queue_handoff.v1",
        "status": "QUEUED" if created else "ALREADY_QUEUED",
        "created": created,
        "work_id": item.id,
        "source_opportunity_ref": request["opportunity_ref"],
        "first_party_buying_evidence_verified": False,
        "outbound_sent": False,
        "crm_mutated": False,
        "financial_authority": "none",
        "execution_authority": "none",
    }


def complete_one_buyer_evidence_desk_review(
    repo_root: Path,
    item: Any,
    *,
    as_of: datetime,
) -> dict[str, Any]:
    """ASTRA worker ONLY completes desk triage, never the buying hypothesis."""
    root = Path(repo_root).resolve()
    if (item.goal_key != GOAL or item.target_component != TARGET
            or item.action != ACTION or item.authority != "observe"
            or item.tenant_id is not None
            or item.commercial_decision_provenance is not None
            or item.decision_identity is not None
            or tuple(item.department_keys) != ("business_development",)
            or tuple(item.evidence_refs) != (
                "runtime:opportunity_factory/intake_latest.json",
                "runtime:opportunity_factory/evidence_routes_latest.json",
                "runtime:opportunity_factory/quant_review_latest.json",
            )):
        raise CommercialResearchHold("untrusted_buyer_evidence_task_authority")
    proposed = item.intelligence_request
    if (not isinstance(proposed, Mapping)
            or proposed.get("budget") != {
                "requested_model_tokens": 0,
                "requested_external_cost_cents": 0,
            }):
        raise CommercialResearchHold("nonzero_or_unbounded_buyer_evidence_task")
    fresh = review_one_commercial_evidence_request(root, as_of=_aware(as_of))
    if (fresh.get("status") != "ONE_INTERNAL_EVIDENCE_REQUEST_PREPARED"
            or proposed.get("first_party_buyer_evidence") != fresh["request"]):
        raise CommercialResearchHold("buyer_evidence_task_snapshot_changed")
    request = fresh["request"]
    return {
        "schema_version": "empire.predictive_revenue.buyer_evidence_desk_triage.v1",
        "status": "INTERNAL_BUYER_EVIDENCE_GAP_REVIEWED",
        "first_party_commercial_evidence_status": "AWAITING_INDEPENDENT_CRM_AND_BUYER_TERMS",
        "source_opportunity_ref": request["opportunity_ref"],
        "source_pathway_fingerprint": request["source_pathway_fingerprint"],
        "next_evidence_action": "VERIFY_GENUINE_BUYER_INTEREST_IN_EXISTING_CRM",
        "quant_missing_factors": [factor["factor"] for factor in request["quant_gaps"]],
        "scientific_negative_control": request["negative_control"],
        "candidate_selection_is_not_a_verified_buyer": True,
        "crm_buyer_outcome_checked": False,
        "buyer_terms_verified": False,
        "qualified_opportunity_admitted": False,
        "prediction_registered": False,
        "economic_memory_updated": False,
        "payments_moved": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }
