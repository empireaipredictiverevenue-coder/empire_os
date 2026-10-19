"""Complete bounded internal desk triage for existing blocked mining jobs.

Scientific and source-quality observations from canonical snapshots ONLY.
No model, OpenManus, external GET, buyer records, CRM write or outbound.
A desk triage completion is never an independent research finding.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

from empire_os.department_work_queue import DepartmentWorkItem
from empire_os.public_source_sweep import review_public_source_sweep
from empire_os.revenue_stream_mining import build_revenue_stream_mining

SUPPORTED = {
    "existing_source_intelligence_and_opportunity_factory": "stream_mining_review",
    "existing_source_intelligence_and_sensor_mesh": "official_source_deep_sweep",
}
STREAM_DEPARTMENTS = {
    "acquisition": "market_intelligence",
    "public_opportunity": "market_intelligence",
    "commercial_opportunity": "business_development",
    "quant_economics": "data_quant",
    "competitor": "marketing_growth",
}
LANE_RESEARCH_REQUIRED = {
    "acquisition": "verify_original_public_source_provenance_and_signal_quality",
    "public_opportunity": "obtain_primary_source_for_unresolved_public_blocker",
    "commercial_opportunity": "obtain_real_first_party_buying_terms_or_intent",
    "quant_economics": "obtain_canonical_probability_price_cost_and_uncertainty",
    "competitor": "refresh_primary_competitor_information",
}


class SpecialistEvidenceHold(ValueError):
    pass


def _one_authorized_department(item: DepartmentWorkItem, expected: str) -> None:
    if (item.authority != "observe"
            or item.tenant_id is not None
            or item.commercial_decision_provenance is not None
            or item.decision_identity is not None
            or len(item.department_keys) != 1
            or item.department_keys[0] != expected):
        raise SpecialistEvidenceHold("unauthorized_department_or_tenant_scope")
    request = item.intelligence_request
    if not isinstance(request, Mapping):
        raise SpecialistEvidenceHold("untrusted_research_request")
    budget = request.get("budget")
    if (not isinstance(budget, Mapping)
            or budget.get("requested_model_tokens") != 0
            or budget.get("requested_external_cost_cents") != 0):
        raise SpecialistEvidenceHold("source_mining_zero_budget_required")


def _stream_review(item: DepartmentWorkItem, root: Path) -> dict[str, Any]:
    raw = item.intelligence_request.get("stream_mining_review")
    if not isinstance(raw, Mapping):
        raise SpecialistEvidenceHold("missing_stream_mining_source_contract")
    name = raw.get("lane")
    if name not in STREAM_DEPARTMENTS:
        raise SpecialistEvidenceHold("unknown_stream_mining_lane")
    _one_authorized_department(item, STREAM_DEPARTMENTS[name])
    review = build_revenue_stream_mining(root)
    lane = next((l for l in review["department_lanes"] if l["stream"] == name), None)
    if lane is None:
        raise SpecialistEvidenceHold("canonical_source_lane_missing")
    if (lane["status"] not in ("FRESH", "OBSERVED")
            or lane["evidence_fingerprint"] != raw.get("evidence_fingerprint")
            or lane["source_ref"] != raw.get("source_ref")
            or lane["counts"] != raw.get("safe_counts")
            or lane["review_code"] != raw.get("review_code")
            or item.action != lane["next_internal_action"]
            or list(item.evidence_refs) != [lane["source_ref"]]
            or raw.get("do_not_infer_probabilities_or_revenue") is not True
            or raw.get("no_private_customer_rows_or_contact_fields") is not True):
        raise SpecialistEvidenceHold("source_snapshot_drift_or_contract_mismatch")
    protocol = review["scientific_validation"]
    if (protocol.get("posterior_probability") is not None
            or protocol.get("control_results_verified") is not False):
        raise SpecialistEvidenceHold("untrusted_scientific_calibration_status")
    return {
        "status": "INTERNAL_SOURCE_DESK_TRIAGE_COMPLETED",
        "adapter": "existing_canonical_source_mining_specialist_v1",
        "stream": name,
        "department": lane["department"],
        "source_snapshot_status": lane["status"],
        "canonical_evidence_fingerprint": lane["evidence_fingerprint"],
        "source_ref": lane["source_ref"],
        "bounded_source_counts": dict(lane["counts"]),
        "source_presence_is_buyer_intent": False,
        "research_action_still_required": LANE_RESEARCH_REQUIRED[name],
        "independent_source_research_completed": False,
        "scientific_controls_required": protocol["controls_to_execute"],
        "scientific_controls_verified": False,
        "ling_or_openmanus_invoked": False,
        "qualified_buyer_proven": False,
        "prediction_calibrated": False,
        "revenue_verified": False,
        "external_model_or_api_called": False,
        "external_execution_performed": False,
        "execution_authority": "none",
    }


def _official_source_review(item: DepartmentWorkItem, root: Path) -> dict[str, Any]:
    raw = item.intelligence_request.get("official_source_deep_sweep")
    if not isinstance(raw, Mapping):
        raise SpecialistEvidenceHold("missing_official_source_contract")
    source_ids = raw.get("source_keys")
    if not isinstance(source_ids, list) or len(source_ids) != 2 or not all(
        isinstance(value, str) for value in source_ids
    ):
        raise SpecialistEvidenceHold("invalid_official_source_inventory")
    expected = {
        ("uk_find_a_tender", "uk_contracts_finder"): (
            "business_development",
            "review_official_uk_procurement_public_ocds_for_eligible_sector_demand",
        ),
        ("ea_flood_warnings", "uk_ea_rainfall"): (
            "market_intelligence",
            "review_ea_flood_source_event_quality_for_sensor_mesh",
        ),
    }
    pair = tuple(source_ids)
    if pair not in expected:
        raise SpecialistEvidenceHold("unapproved_official_source_pair")
    department, action = expected[pair]
    _one_authorized_department(item, department)
    catalogue = review_public_source_sweep()
    data = {s["source_key"]: s for s in catalogue["sources"]}
    digest = sha256(
        (catalogue["metadata_fingerprint"] + "|" + "|".join(pair)).encode()
    ).hexdigest()
    if (raw.get("source_inventory_fingerprint") != digest
            or raw.get("public_metadata_only") is not True
            or raw.get("commercial_source_rights_must_be_verified") is not True
            or raw.get("explicit_ingest_authorization_required") is not True
            or item.action != action
            or list(item.evidence_refs) != [
                data[key]["official_documentation"] for key in pair
            ]):
        raise SpecialistEvidenceHold("official_source_evidence_drift_or_tampering")
    return {
        "status": "INTERNAL_SOURCE_READINESS_TRIAGE_COMPLETED",
        "adapter": "existing_official_source_sweep_specialist_v1",
        "department": department,
        "source_inventory": [
            {
                "source_key": key,
                "readiness": data[key]["readiness"],
                "auth_class": data[key]["auth"],
                "rights_review_class": data[key]["rights"],
                "evidence_limit": data[key]["truth_limit"],
            }
            for key in pair
        ],
        "source_inventory_fingerprint": digest,
        "next_research_action": (
            "independently_verify_current_tenders_sector_fit_and_eligibility"
            if department == "business_development"
            else "verify_environmental_event_geography_revision_and_source_freshness"
        ),
        "independent_live_source_verification_completed": False,
        "source_polling_activated": False,
        "new_commercial_opportunities_admitted": 0,
        "commercial_buyer_or_revenue_proven": False,
        "external_execution_performed": False,
        "execution_authority": "none",
    }


def complete_source_mining_desk_review(
    repo_root: Path, item: DepartmentWorkItem,
) -> dict[str, Any]:
    """No writes: caller is responsible for existing queue completion."""
    root = Path(repo_root).resolve()
    expected = SUPPORTED.get(item.target_component)
    if expected is None:
        raise SpecialistEvidenceHold("source_adapter_target_not_supported")
    if item.goal_key not in {
        "mine_existing_canonical_source_stream_evidence",
        "assess_official_source_mining_reuse",
    }:
        raise SpecialistEvidenceHold("not_authorized_source_mining_goal")
    if expected == "stream_mining_review":
        return _stream_review(item, root)
    return _official_source_review(item, root)
