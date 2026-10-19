"""First-payer scientific-to-commercial evidence alignment; read-only.

Reuses the already owned buyer acquisition request, Quant formula readiness
and authorised market-capacity projection. Does not enqueue duplicate work,
claim CRM access, start outreach, register a forecast or train a model.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
import re

from empire_os.revenue_buyer_evidence_handoff import (
    EVIDENCE_CUSTODY, RESEARCH_SCHEMA, SCHEMA as BUYER_SCHEMA,
    ACTION, review_one_commercial_evidence_request,
)
from empire_os.predictive_formula_evidence_review import (
    SCHEMA_VERSION as FORMULA_SCHEMA, review_formula_evidence,
)
from empire_os.flagship_buyer_market_projection import (
    SCHEMA as COVERAGE_SCHEMA, review_authorized_market_coverage_snapshot,
)
from empire_os.quant_brain import _DECISION_PACKET_REQUIRED

SCHEMA = "empire.flagship.first_payer_owner_handoff.v1"
_OPPREF = re.compile(r"^oppref_[0-9a-f]{20}$")
_NICHE = re.compile(r"^[a-z][a-z0-9_]{0,79}$")


def summarize_first_payer_owner_handoff(
    *, buyer: Mapping[str, Any], formula: Mapping[str, Any],
    coverage: Mapping[str, Any], as_of: datetime,
) -> dict[str, Any]:
    """Align the same existing owner's gap with Quant without forging a join."""
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("trusted awareness clock required")
    if (not isinstance(buyer, Mapping) or not isinstance(formula, Mapping)
            or not isinstance(coverage, Mapping)):
        raise ValueError("existing upstream review objects required")
    if (buyer.get("schema_version") != BUYER_SCHEMA
            or buyer.get("execution_authority") != "none"
            or buyer.get("buyer_contacted") is not False
            or buyer.get("forecast_created") is not False
            or buyer.get("actual_revenue_verified") is not False
            or formula.get("schema_version") != FORMULA_SCHEMA
            or formula.get("mode") != "OBSERVE"
            or formula.get("execution_authority") != "none"
            or formula.get("forecast_generated_by_this_review") is not False
            or formula.get("commercial_execution_authorized") is not False
            or coverage.get("schema_version") != COVERAGE_SCHEMA
            or coverage.get("mode") != "OBSERVE"
            or coverage.get("execution_authority") != "none"
            or coverage.get("first_party_buyer_request_verified") is not False
            or coverage.get("written_terms_or_allocation_verified") is not False
            or coverage.get("buyer_or_revenue_verified") is not False):
        raise ValueError("untrusted or commercially promoted owner review")
    statuses = formula.get("source_status")
    if (formula.get("status") not in ("REVIEW_READY", "EVIDENCE_HOLD")
            or not isinstance(statuses, Mapping)
            or set(statuses) != {"cloud_formula", "revenue_distribution", "opportunity_quant"}
            or any(v not in ("FRESH", "STALE", "MISSING_OR_UNSAFE",
                             "UNTRUSTED", "UNAVAILABLE", "FUTURE_HELD")
                   for v in statuses.values())):
        raise ValueError("formula source inventory cannot be exported")

    ready = buyer.get("status") == "ONE_INTERNAL_EVIDENCE_REQUEST_PREPARED"
    if buyer.get("status") not in (
        "ONE_INTERNAL_EVIDENCE_REQUEST_PREPARED",
        "HELD_NO_CURRENT_FIRST_PARTY_GAP",
    ):
        raise ValueError("unknown buyer evidence owner status")
    request = buyer.get("request")
    ref = niche = fingerprint = None
    evidence_gaps = []
    if ready:
        if (not isinstance(request, Mapping)
                or request.get("schema_version") != RESEARCH_SCHEMA
                or not isinstance(request.get("opportunity_ref"), str)
                or not _OPPREF.fullmatch(request["opportunity_ref"])
                or (request.get("niche") is not None and (
                    not isinstance(request["niche"], str)
                    or not _NICHE.fullmatch(request["niche"])))
                or not isinstance(request.get("source_pathway_fingerprint"), str)
                or not re.fullmatch(r"[0-9a-f]{64}",
                                    request["source_pathway_fingerprint"])
                or request.get("first_missing_evidence") !=
                    "buyer_intent_normalized_score_required"
                or request.get("quant_probability_source_verified") is not False
                or request.get("automatic_email_or_offer_authorized") is not False
                or not isinstance(request.get("quant_gaps"), list)):
            raise ValueError("untrusted first-party evidence request")
        gaps = request["quant_gaps"]
        if len(gaps) > len(_DECISION_PACKET_REQUIRED) or len(gaps) != len({
            row["factor"] for row in gaps if isinstance(row, Mapping)
            and isinstance(row.get("factor"), str)
        }):
            raise ValueError("ambiguous quantified evidence gaps")
        for row in gaps:
            if (not isinstance(row, Mapping)
                    or set(row) != {"factor", "required_source"}
                    or row["factor"] not in _DECISION_PACKET_REQUIRED
                    or row["required_source"] != EVIDENCE_CUSTODY[row["factor"]]):
                raise ValueError("Quant/source authority mismatch")
        if not gaps:
            raise ValueError("buyer proof missing but no Quant gaps provided")
        ref = request["opportunity_ref"]
        niche = request["niche"]
        fingerprint = request["source_pathway_fingerprint"]
        evidence_gaps = [
            {"field": key, "required_evidence": EVIDENCE_CUSTODY[key],
             "owner": (
                 "scientific_quant" if key in (
                     "probability_success", "uncertainty", "confidence",
                     "time_to_revenue_days",
                 ) else "business_development"
             )}
            for key in _DECISION_PACKET_REQUIRED
            if key in {row["factor"] for row in gaps}
        ]
    elif request is not None:
        raise ValueError("held owner response cannot supply an opportunity")
    # Never reuse the prior roofing candidate after a source refresh. Keep
    # the original owner's hold reason only when it is a known safe code.
    hold_reason = None if ready else buyer.get("reason_code")
    if hold_reason not in (None, "authoritative_current_pathways_not_ready",
                           "no_verified_current_buyer_evidence_gap_in_shortlist",
                           "invalid_quant_missing_factor_contract"):
        hold_reason = "BUYER_EVIDENCE_CURRENT_SOURCE_UNAVAILABLE"

    quant = formula.get("quant_original_prediction_readiness")
    quant_complete = None
    quant_count = None
    if quant is not None:
        if (not isinstance(quant, Mapping)
                or type(quant.get("candidate_count")) is not int
                or type(quant.get("available_quant_decision_count")) is not int
                or quant["candidate_count"] < quant["available_quant_decision_count"]
                or quant["available_quant_decision_count"] < 0
                or quant.get("source_rows_are_original_conversion_predictions") is not False
                or quant.get("immutable_prediction_receipt_verified") is not False):
            raise ValueError("untrusted aggregated Quant readiness")
        quant_count = quant["candidate_count"]
        quant_complete = quant["available_quant_decision_count"]

    return {
        "schema_version": SCHEMA,
        "status": (
            "FIRST_PAYER_MARKET_IDENTITY_HELD" if ready and niche is None
            else "FIRST_PAYER_BUYER_EVIDENCE_BLOCKED" if ready
            else "CURRENT_OPPORTUNITY_NOT_ESTABLISHED"
        ),
        "mode": "OBSERVE",
        "as_of": as_of.astimezone(timezone.utc).isoformat(),
        "opaque_opportunity_ref": ref,
        "market_vertical": niche,
        "existing_source_fingerprint": fingerprint,
        "existing_business_development_action": ACTION if ready else None,
        "existing_business_development_workflow_reused": ready,
        "buyer_snapshot_status": buyer["status"],
        "buyer_source_hold_reason": hold_reason,
        "buyer_coverage_status": coverage.get("status"),
        "quant_formula_status": formula.get("status"),
        "quant_source_status": dict(formula.get("source_status") or {}),
        "global_quant_candidates_observed": quant_count,
        "global_quant_complete_count": quant_complete,
        "same_opportunity_quant_input_gaps": evidence_gaps,
        "same_buyer_verified_terms": False,
        "same_buyer_capacity_and_delivery_verified": False,
        "source_request_not_equivalent_to_buyer_acceptance": True,
        "global_quant_counts_not_same_opportunity_counts": True,
        "first_priority_owner": (
            "market_intelligence" if ready and niche is None
            else "business_development" if ready
            else "existing_evidence_pathways_owner"
        ),
        "first_priority_action": (
            "VERIFY_SOURCE_MARKET_NICHE_BEFORE_BUYER_MATCH"
            if ready and niche is None
            else "VERIFY_EXISTING_CRM_BUYER_REPLY_PRICE_TERRITORY_AND_CAPACITY"
            if ready else "RESTORE_CURRENT_FIRST_PARTY_OPPORTUNITY_EVIDENCE"
        ),
        "second_priority_owner": "scientific_quant" if ready and niche is not None else None,
        "second_priority_action": (
            "RECORD_VALIDATED_PROSPECTIVE_PROBABILITY_AND_ECONOMICS"
            if ready and niche is not None else None
        ),
        "existing_work_item_created": False,
        "crm_accessed": False,
        "canonical_record_writes": False,
        "forecast_issued": False,
        "registry_activated": False,
        "calibration_claim_authorized": False,
        "outbound_sent": False,
        "funds_moved": False,
        "execution_authority": "none",
    }


def review_current_first_payer_owner_handoff(
    repo_root: str | Path, *, as_of: datetime,
) -> dict[str, Any]:
    """Invoke read interfaces and diagnose stale source epochs."""
    from empire_os.flagship_source_epoch_reconciliation import review_source_epoch_reconciliation_runtime
    root = Path(repo_root).resolve(strict=False)
    report = summarize_first_payer_owner_handoff(
        buyer=review_one_commercial_evidence_request(root, as_of=as_of),
        formula=review_formula_evidence(root, as_of=as_of),
        coverage=review_authorized_market_coverage_snapshot(root, as_of=as_of),
        as_of=as_of,
    )
    if report["status"] != "CURRENT_OPPORTUNITY_NOT_ESTABLISHED":
        return report
    epoch = review_source_epoch_reconciliation_runtime(root, as_of=as_of)
    report["source_epoch_reconciliation"] = epoch
    if epoch["status"] in (
        "RADAR_AHEAD_OF_FACTORY_STAGES", "COMMUNITY_SOURCE_POPULATION_CHANGED",
        "MULTI_STAGE_IDENTITY_DRIFT",
    ):
        report["first_priority_owner"] = "existing_opportunity_factory_owner"
        report["first_priority_action"] = epoch["next_action"]
    return report
