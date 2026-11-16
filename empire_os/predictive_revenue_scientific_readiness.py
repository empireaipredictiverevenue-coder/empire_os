"""Read-only scientific readiness bridge for existing Predictive Revenue.

This does not calculate customer forecasts or reclassify outcomes. It reads
only a caller-supplied, already-constructed predictive_intelligence snapshot
and a separately verified synthetic science study, producing a diagnostic
readiness verdict with strict non-promotion controls. No new product, database,
authority, subscriptions, external models or orchestration are created.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from empire_os.predictive_revenue_products import predictive_revenue_product
from empire_os.agi_runlength_causal_study import KEY
from empire_os.agi_scientific_research_agent import PINNED_WORLD_MODEL_SOURCE_SHA256

ALLOWED_PRODUCTS=frozenset({
    "predictive_revenue_diagnostic",
    "predictive_revenue_intelligence_os",
})


def review_predictive_revenue_scientific_readiness(
    product_code:str,
    predictive_snapshot:Mapping[str,Any],
    scientific_study:Mapping[str,Any] | None=None,
)->dict[str,Any]:
    product=predictive_revenue_product(product_code)
    if product.product_code not in ALLOWED_PRODUCTS:
        raise ValueError("scientific readiness is not a commercial catalog migration")
    if not isinstance(predictive_snapshot,Mapping):
        raise ValueError("verified Predictive Intelligence snapshot required")
    if (predictive_snapshot.get("schema_version")!="empire.predictive_intelligence.v1"
        or predictive_snapshot.get("mode")!="OBSERVE"
        or predictive_snapshot.get("probability_source")!=
           "verified_terminal_commercial_outcomes_only"
        or predictive_snapshot.get("prediction_only") is not True
        or predictive_snapshot.get("model_weight_mutation") is not False
        or predictive_snapshot.get("commercial_authority")!="none"
        or predictive_snapshot.get("execution_authority")!="none"):
        raise ValueError("predictive intelligence custody/authority mismatch")
    estimates=predictive_snapshot.get("product_estimates")
    if not isinstance(estimates,Mapping):
        raise ValueError("product cohort estimates unavailable")
    unsupported=[]
    cohort_ready=0
    blocked=0
    for code,row in estimates.items():
        if not isinstance(code,str) or not isinstance(row,Mapping):
            raise ValueError("invalid product cohort")
        if (row.get("product_code")!=code
            or row.get("learning_stage")!="SHADOW_LEARNING"
            or row.get("promoted_learning") is not False
            or row.get("prediction_only") is not True
            or row.get("actual_revenue") is not False
            or row.get("execution_authority")!="none"):
            raise ValueError("product cohort claims commercial authority")
        if row.get("tenant_id")!=predictive_snapshot.get("tenant_id"):
            raise ValueError("cohort tenant binding inconsistent")
        min_terminal=predictive_snapshot.get("minimum_terminal_samples")
        min_timing=predictive_snapshot.get("minimum_timing_samples")
        terminal_count=row.get("terminal_outcome_count")
        timing_count=row.get("time_to_revenue_sample_count")
        if any(type(n) is not int or n<0 for n in (
            min_terminal,min_timing,terminal_count,timing_count
        )) or min_terminal<1 or min_timing<1:
            raise ValueError("invalid verified outcome cohort counts")
        if (row.get("probability_available") is True and
            (terminal_count<min_terminal or
             row.get("probability_success") is None)):
            raise ValueError("unevidenced product conversion probability")
        if (row.get("time_to_revenue_available") is True and
            (timing_count<min_timing or
             row.get("time_to_revenue_days") is None)):
            raise ValueError("unevidenced time-to-revenue estimate")
        ready=(row.get("probability_available") is True and
               row.get("time_to_revenue_available") is True)
        cohort_ready+=int(ready)
        blocked+=int(not ready)
        # Do not export tenant identities or raw customer evidence.
        if not ready:
            unsupported.append(code)
    research_verified=False
    research_status="NOT_EVALUATED"
    if scientific_study is not None:
        if not isinstance(scientific_study,Mapping):
            raise ValueError("scientific result must be a verified mapping")
        if (scientific_study.get("status")!="INTERNAL_RUNLENGTH_CAUSAL_STUDY_COMPLETE"
            or scientific_study.get("mode")!="OBSERVE"
            or scientific_study.get("execution_authority")!="none"
            or scientific_study.get("real_agi_demonstrated") is not False
            or scientific_study.get("independent_external_benchmark") is not False
            or scientific_study.get("real_world_revenue_calibration_demonstrated") is not False
            or scientific_study.get("production_state_changed") is not False
            or scientific_study.get("experiment_registry",{}).get("experiment_key")!=KEY
            or scientific_study.get("source_world_sha256")!=PINNED_WORLD_MODEL_SOURCE_SHA256
            or scientific_study.get("cases_per_policy")!=2016
            or len(scientific_study.get("results",{}))!=21):
            raise ValueError("scientific research provenance/claim mismatch")
        research_verified=True
        research_status="SYNTHETIC_RESEARCH_ONLY"
    return {
        "schema_version":"empire.predictive_revenue.scientific_readiness.v1",
        "status":"READ_ONLY_DIAGNOSTIC_READY",
        "mode":"OBSERVE",
        "product_code":product.product_code,
        "product_existing_in_catalog":True,
        "source_snapshot_schema":"empire.predictive_intelligence.v1",
        "product_cohorts_seen":len(estimates),
        "product_cohorts_evidence_ready":cohort_ready,
        "product_cohorts_blocked":blocked,
        "unsupported_product_codes":sorted(unsupported),
        "verified_science_internal_only":research_verified,
        "scientific_research_status":research_status,
        "scientific_learning_eligible_for_commercial_forecast":False,
        "causal_probability_claimed_for_buyers":False,
        "predictions_recomputed":False,
        "verified_actual_revenue_changed":False,
        "economic_memory_mutated":False,
        "diagnostic_auto_fulfilled":False,
        "production_activated":False,
        "revenue_action_authorized":False,
        "outbound_enabled":False,
        "execution_authority":"none",
    }
