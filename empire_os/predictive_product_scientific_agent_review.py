"""Existing Scientific Research Agent governance applied to product forecasts.

Shares pinned evidence/engineering skills and ExperimentRegistryRecord with
EmpireOS Scientific Research Agent. This is a bounded scientific PROTOCOL
review, not an independent agent execution, proof of issuer identity or
scientific verification of actual customer forecasts.
"""
from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from empire_os.predictive_existing_scientific_agent_skill_lock import (
    ROOT, verify_existing_scientific_agent_skill_lock,
)
from empire_os.experiment_registry import ExperimentRegistryRecord
from empire_os.predictive_product_science_readiness import SCHEMA as SCIENCE_SCHEMA
from empire_os.predictive_product_scientific_holdout import (
    SCHEMA as HOLDOUT_SCHEMA, MIN_HISTORY, MIN_EVALUATIONS,
)

SCHEMA = "empire.predictive_revenue.scientific_agent_product_protocol.v1"
EXPERIMENT_KEY = "predictive_revenue_product_cohort_baseline_challenge_v1"
PRIMARY_METRIC = "out_of_sample_brier_skill_vs_past_only_baseline"
HYPOTHESIS = (
    "An originally registered product-cohort conversion forecast achieves "
    "lower out-of-sample Brier loss than the time-safe historical outcome "
    "baseline for the same tenant and verified product version"
)


class ScientificProtocolHold(ValueError):
    """Malformed and contradictory evidence never opens a research gate."""


def _integer(value: Any, field: str) -> int:
    if type(value) is not int or not 0 <= value <= 1_000_000:
        raise ScientificProtocolHold(f"{field} invalid")
    return value


def _science_summary(source: Mapping[str, Any]) -> tuple[int, int, int]:
    if (not isinstance(source, Mapping)
            or source.get("schema_version") != SCIENCE_SCHEMA
            or source.get("mode") != "OBSERVE"
            or source.get("status") not in (
                "NO_PRODUCT_TERMINAL_OUTCOMES_OBSERVED",
                "UNSCOPED_ORIGINAL_OUTCOMES_QUARANTINED",
                "PRODUCT_COHORT_PRESENT_OWNER_AUTHENTICATION_STILL_REQUIRED",
            )
            or source.get("execution_authority") != "none"
            or source.get("forecast_eligible_for_customer") is not False
            or source.get("original_source_issuer_authenticated") is not False
            or source.get("original_forecast_registry_readback_authenticated") is not False
            or source.get("economic_memory_update_eligible") is not False
            or source.get("database_writes") is not False):
        raise ScientificProtocolHold("source science status or authority invalid")
    product_count = _integer(source.get("catalogue_product_count"), "product count")
    outcomes = _integer(source.get("source_reported_terminal_outcome_count"), "outcomes")
    cohorts = _integer(source.get("source_reported_product_cohorts"), "cohorts")
    probability = _integer(
        source.get("source_reported_probability_ready_product_count"), "probability cohorts"
    )
    held = _integer(source.get("unscoped_source_rows_quarantined_count", 0),
                    "unscoped source rows held")
    if (held > 0) != (source["status"] == "UNSCOPED_ORIGINAL_OUTCOMES_QUARANTINED"):
        raise ScientificProtocolHold("source quarantine/status contradiction")
    if held and (outcomes or cohorts or probability):
        raise ScientificProtocolHold("quarantined rows cannot be science evidence")
    if (cohorts > product_count or probability > cohorts
            or (source["status"] == "NO_PRODUCT_TERMINAL_OUTCOMES_OBSERVED"
                and (outcomes != 0 or cohorts != 0 or probability != 0))
            or (source["status"] == "PRODUCT_COHORT_PRESENT_OWNER_AUTHENTICATION_STILL_REQUIRED"
                and outcomes == 0)):
        raise ScientificProtocolHold("self-contradictory product research source")
    return product_count, outcomes, probability


def _holdout_review(holdout: Mapping[str, Any] | None) -> dict[str, Any]:
    if holdout is None:
        return {
            "score_review_status": "NOT_SUBMITTED",
            "comparable_scored_cases": None,
            "brier_model": None,
            "brier_baseline": None,
            "skill_vs_past_only_baseline": None,
            "model_improves_on_baseline_in_submitted_data": None,
            "commercial_claim_supported": False,
            "reported_statistics_source_authenticated": False,
            "methodology_alerts": ["NO_PROSPECTIVE_HOLDOUT_EVALUATION"],
        }
    if (not isinstance(holdout, Mapping)
            or holdout.get("schema_version") != HOLDOUT_SCHEMA
            or holdout.get("mode") != "OBSERVE"
            or holdout.get("execution_authority") != "none"
            or holdout.get("original_registry_readback_authenticated") is not False
            or holdout.get("original_source_issuer_authenticated") is not False
            or holdout.get("forecast_eligible_for_customer") is not False
            or holdout.get("economic_memory_update_eligible") is not False
            or holdout.get("model_weight_mutation") is not False
            or holdout.get("realized_revenue_verified_by_this_review") is not False):
        raise ScientificProtocolHold("unsafe reported holdout authority")
    status = holdout.get("status")
    if status == "PRODUCT_HOLDOUT_INSUFFICIENT_ORIGINAL_EVIDENCE":
        if (holdout.get("model_brier") is not None
                or holdout.get("historical_baseline_brier") is not None
                or holdout.get("out_of_sample_evaluation_count") != 0):
            raise ScientificProtocolHold("held cohort cannot contain model skill")
        return {
            "score_review_status": "HELD_NO_COMPARABLE_COHORT",
            "comparable_scored_cases": 0,
            "brier_model": None, "brier_baseline": None,
            "skill_vs_past_only_baseline": None,
            "model_improves_on_baseline_in_submitted_data": None,
            "commercial_claim_supported": False,
            "reported_statistics_source_authenticated": False,
            "methodology_alerts": ["INSUFFICIENT_PREOUTCOME_REFERENCED_SAMPLES"],
        }
    if status != "SUPPLIED_PACKET_STATISTICS_ONLY_ORIGINAL_REGISTRY_HOLD":
        raise ScientificProtocolHold("unsupported holdout report status")
    n = _integer(holdout.get("out_of_sample_evaluation_count"), "scored cases")
    past = _integer(holdout.get("historical_baseline_period_count"), "past sample count")
    def bounded(value: Any) -> float:
        if type(value) not in (int, float) or not 0 <= value <= 1:
            raise ScientificProtocolHold("invalid Brier score")
        return float(value)
    if n < MIN_EVALUATIONS or past < MIN_HISTORY:
        raise ScientificProtocolHold("insufficient matched temporal cohort")
    model = bounded(holdout.get("model_brier"))
    baseline = bounded(holdout.get("historical_baseline_brier"))
    gap = bounded(holdout.get("calibration_gap"))
    submitted = _integer(holdout.get("submitted_calibration_count"), "submitted cases")
    if submitted < n or past > submitted:
        raise ScientificProtocolHold("temporal study counts contradictory")
    observed_skill = round((baseline - model) / baseline, 6) if baseline > 0 else None
    declared_skill = holdout.get("skill_vs_past_only_baseline")
    if observed_skill is None:
        if declared_skill is not None:
            raise ScientificProtocolHold("zero baseline cannot claim model skill")
    elif (type(declared_skill) not in (int, float)
          or not abs(declared_skill - observed_skill) <= 0.00001):
        raise ScientificProtocolHold("reported skill contradicts original error totals")
    improvement = model < baseline
    # No statistical significance inference, even when apparent skill is high.
    alerts = ["SOURCE_ISSUER_AND_REGISTRY_ORIGIN_UNVERIFIED",
              "HOLDOUT_DISTRIBUTION_SELECTION_NOT_INDEPENDENTLY_VERIFIED"]
    if not improvement:
        alerts.append("MODEL_NOT_BETTER_THAN_PAST_ONLY_BASELINE")
    if gap > 0.10:
        alerts.append("CALIBRATION_GAP_EXCEEDS_DIAGNOSTIC_TOLERANCE")
    if n < 30:
        alerts.append("LOW_EVALUATION_SAMPLE_COUNT")
    return {
        "score_review_status": "REPORTED_COHORT_DIAGNOSTIC_ONLY",
        "comparable_scored_cases": n,
        "brier_model": model,
        "brier_baseline": baseline,
        "skill_vs_past_only_baseline":
            holdout.get("skill_vs_past_only_baseline"),
        "model_improves_on_baseline_in_submitted_data": improvement,
        "commercial_claim_supported": False,
        "reported_statistics_source_authenticated": False,
        "methodology_alerts": alerts,
    }


def review_product_scientific_agent_protocol(
    *, science_source: Mapping[str, Any],
    holdout: Mapping[str, Any] | None = None,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Reuse existing agent skill custody and experiment governance, not AGI metrics."""
    product_count, outcomes, probability_count = _science_summary(science_source)
    try:
        custody = verify_existing_scientific_agent_skill_lock(root=root)
    except (ValueError, OSError, TypeError):
        raise ScientificProtocolHold("scientific agent skills changed or unavailable") from None
    if (custody.get("status") != "PINNED_EXISTING_SKILLS_VERIFIED"
            or custody.get("execution_authority") != "none"
            or custody.get("autonomous_training_loop_enabled") is not False):
        raise ScientificProtocolHold("scientific agent skill contract invalid")
    metrics = _holdout_review(holdout)
    protocol = ExperimentRegistryRecord(
        experiment_key=EXPERIMENT_KEY,
        hypothesis=HYPOTHESIS,
        metric=PRIMARY_METRIC,
        control_variant="historical_available_before_prediction_laplace_baseline",
        treatment_variants=("source_bound_product_conversion_forecast",),
        # The *proposed* protocol has no original registry/release evidence.
        assignment_integrity_verified=False,
        exposure_integrity_verified=False,
        outcome_window_closed=False,
        evidence={
            "protocol_frozen_in_source_code": True,
            "temporal_train_cutoff_required": True,
            "minimum_resolved_history": MIN_HISTORY,
            "minimum_out_of_sample_evaluations": MIN_EVALUATIONS,
            "product_version_and_tenant_separation_required": True,
            "frozen_original_forecast_registry_proof_missing": True,
            "individual_propensity_or_causality_inferred": False,
            "research_output_not_sales_or_payment_evidence": True,
        },
    ).as_dict()
    digest = sha256(json.dumps(
        protocol, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": (
            "SCIENTIFIC_AGENT_UNSCOPED_SOURCE_QUARANTINED"
            if science_source["status"] == "UNSCOPED_ORIGINAL_OUTCOMES_QUARANTINED" else
            "SCIENTIFIC_AGENT_PROTOCOL_READY_WAITING_FOR_REAL_PRODUCT_COHORT"
            if outcomes == 0 else
            "SCIENTIFIC_AGENT_PROTOCOL_READY_ORIGINAL_SOURCE_AUTHENTICATION_HOLD"
        ),
        "existing_scientific_research_agent_skill_custody_verified": True,
        "existing_scientific_skill_count": len(custody["existing_contracts"]),
        "existing_experiment_registry_contract_reused": True,
        "existing_scientific_agent_world_model_benchmark_not_substituted_for_revenue": True,
        "existing_scientific_agent_inference_invoked": False,
        "experiment": protocol,
        "experiment_plan_sha256_integrity_only": digest,
        "original_forecast_experiment_registered": False,
        "product_skus_mapped": product_count,
        "source_reported_original_outcomes": outcomes,
        "source_rows_quarantined_from_legacy_reader": science_source.get("unscoped_source_rows_quarantined_count", 0),
        "source_reported_probability_cohorts": probability_count,
        "reported_holdout": metrics,
        "original_tenant_source_authenticated": False,
        "customer_model_validated": False,
        "scientific_model_promotion_approved": False,
        "economic_memory_update_eligible": False,
        "automated_agent_execution_authorized": False,
        "outbound_authorized": False,
        "payment_authorized": False,
        "production_activated": False,
        "database_writes": False,
        "execution_authority": "none",
    }
