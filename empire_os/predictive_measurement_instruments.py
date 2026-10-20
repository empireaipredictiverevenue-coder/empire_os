"""Evidence-quality measurement instruments for Predictive Revenue.

Never turns aggregate research, reply pointers, catalogues or company-wide GP
into verified buyer, product-unit profit, registered forecast or calibration.
Pure adapter to EXISTING source owners, existing registry and existing telemetry.
No optional packages, network, DB, source writes or model fitting required.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping
from math import isfinite

from empire_os.predictive_market_evidence_binding import SCHEMA as TERRITORY_SCHEMA
from empire_os.predictive_market_restricted_provenance import (
    SCHEMA as LINEAGE_SCHEMA, PRODUCER_SCHEMA,
)
from empire_os.predictive_customer_value_outcome_readiness import SCHEMA as OUTCOME_SCHEMA
from empire_os.predictive_profitability_governed_decision import TRUTH_SCHEMA
from empire_os.predictive_storm_measurement import SCHEMA as STORM_SCHEMA
from empire_os.predictive_bls_cost_index import SCHEMA as BLS_SCHEMA

SCHEMA = "empire.predictive_revenue.measurement_instruments.v1"

# Developer/operator integration registry; not installed/not authorised by listing.
OPEN_INSTRUMENTS = (
    ("event_tracing", "opentelemetry", "existing empire_os.telemetry and otel_telemetry", "original observation, source-hold and decision event traces"),
    ("data_provenance", "openlineage", "future source-owner integration", "dataset/job lineage with tenant and epoch privacy constraints"),
    ("model_experiments", "mlflow", "future scientific quant owner integration", "immutable model version and prospective experiment artifacts"),
    ("drift_monitoring", "evidently", "future scientific quant owner integration", "feature/outcome drift on genuine matched cohorts"),
    ("calibration", "existing_quant_brain", "existing original conversion registry and predictive calibration board", "Brier and calibration metrics only with original verified forecast/outcome pairs"),
    ("controlled_outcomes", "existing_customer_value_pilot", "existing customer value measurement preflight", "baseline, control, treatment, refunds, consent and observed value"),
    ("financial_outcomes", "existing_economic_memory", "existing accounting/commerce owner", "recognised revenue/actual gross profit separate from hypothetical profit"),
)


def _metric(name: str, *, value: int | float | None,
            unit: str, status: str, owner: str,
            scope: str, window_days: int | None,
            source_ref: str | None, limitation: str) -> dict[str, Any]:
    if value is not None and (type(value) not in (int, float) or not isfinite(value)):
        raise ValueError("a measured number must be finite, not a bool")
    if status not in ("AGGREGATE_RESEARCH_OBSERVED","AGGREGATE_GLOBAL_FINANCE_OBSERVED",
                      "SOURCE_HOLD","NOT_CONNECTED_OR_AUTHENTICATED"):
        raise ValueError("unknown metric evidence classification")
    if status in ("SOURCE_HOLD","NOT_CONNECTED_OR_AUTHENTICATED") and value is not None:
        raise ValueError("unavailable data must be null, never a fabricated zero")
    return {
        "key": name, "value": value, "unit": unit,
        "evidence_status": status,
        "owner": owner, "source_scope": scope,
        "observation_window_days": window_days,
        "source_revision_sha256": source_ref,
        "source_limitations": limitation,
        "is_verified_original_forecast_outcome_pair": False,
        "may_be_used_for_live_profit_calibration": False,
    }


def build_predictive_measurement_instruments(
    territory: Mapping[str, Any],
    lineage: Mapping[str, Any],
    outcomes: Mapping[str, Any],
    economic_truth: Mapping[str, Any],
    producer: Mapping[str, Any],
    storm: Mapping[str, Any],
    *, as_of: datetime,
    bls: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Score measurement coverage, not commercial success or model accuracy."""
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("trusted timezone-aware instrument review clock required")
    if any(not isinstance(x, Mapping) for x in
           (territory, lineage, outcomes, economic_truth, producer, storm)):
        raise ValueError("original owner review packets required")

    t = (
        territory.get("schema_version") == TERRITORY_SCHEMA
        and territory.get("status") == "TERRITORY_LEVEL_MARKET_RESEARCH_JOIN_READY"
        and territory.get("execution_authority") == "none"
        and territory.get("live_economic_forecast_issuance_authorized") is False
        and territory.get("market_research_is_verified_buying_demand") is False
    )
    l = (
        lineage.get("schema_version") == LINEAGE_SCHEMA
        and lineage.get("status") == "RESTRICTED_REPLY_PROVENANCE_RESEARCH_ONLY"
        and lineage.get("execution_authority") == "none"
        and lineage.get("calibration_training_allowed") is False
        and lineage.get("canonical_provider_message_authenticated") is False
    )
    o = (
        outcomes.get("schema_version") == OUTCOME_SCHEMA
        and outcomes.get("status") == "CUSTOMER_VALUE_OUTCOME_SOURCE_READINESS_REVIEWED"
        and outcomes.get("execution_authority") == "none"
        and outcomes.get("model_outcome_calibration_authorized") is False
    )
    e = (
        economic_truth.get("schema_version") == TRUTH_SCHEMA
        and economic_truth.get("status")
        == "GLOBAL_ECONOMIC_SNAPSHOT_REVIEWED_NO_OPPORTUNITY_ATTRIBUTION"
        and economic_truth.get("execution_authority") == "none"
        and economic_truth.get("original_pilot_to_global_profit_attribution_verified") is False
        and economic_truth.get("source_owner_payment_authentication_independently_proven") is False
    )
    p = (
        producer.get("schema_version") == PRODUCER_SCHEMA
        and producer.get("status") in (
            "SOURCE_OWNER_MERGE_REVIEW_REQUIRED","STATIC_SOURCE_COMPATIBILITY_REVIEWED"
        )
        and producer.get("execution_authority") == "none"
        and producer.get("merge_source_producer_authorized") is False
    )

    if t and l and lineage.get("original_territory_revision_sha256") != territory.get("source_revision_fingerprint"):
        l = False  # Do not join a different source revision, even if both reviewers passed.
    s = (
        storm.get("schema_version") == STORM_SCHEMA
        and storm.get("status") == "STORM_SOURCE_RESEARCH_MEASURED"
        and storm.get("execution_authority") == "none"
        and storm.get("actual_storm_damage_verified") is False
        and storm.get("storm_opportunity_revenue_verified") is False
        and storm.get("forecast_outcome_calibration_allowed") is False
    )
    b = (
        isinstance(bls,Mapping)
        and bls.get("schema_version")==BLS_SCHEMA
        and bls.get("status")=="BLS_OFFICIAL_INDEX_RESEARCH_REVIEWED"
        and bls.get("execution_authority")=="none"
        and bls.get("realized_profit_verified") is False
        and bls.get("actual_material_or_labor_cost_authenticated") is False
        and bls.get("external_fetch_or_paid_query_performed") is False
        and isinstance(bls.get("series_research_cards"),list)
        and type(bls.get("series_observation_count")) is int
        and bls["series_observation_count"]==len(bls["series_research_cards"])
        and 1<=bls["series_observation_count"]<=12
        and isinstance(bls.get("source_revision_sha256"),str)
        and len(bls["source_revision_sha256"])==64
    )
    checks = {
        "bls_cost_index_research": b,
        "storm_source": s,
        "territory_research": t,
        "restricted_reply_lineage": l,
        "predictive_outcome_readiness": o,
        "global_economic_truth": e,
        "producer_compatibility": p,
    }
    metrics = []
    def count(key: str, record: Mapping[str,Any], field: str,
              ok: bool, owner: str, scope: str, window: int | None,
              limitation: str, status: str="AGGREGATE_RESEARCH_OBSERVED") -> None:
        observed: int | None = None
        if ok:
            raw = record.get(field)
            if type(raw) is int and 0 <= raw <= 100_000_000:
                observed = raw
            else:
                ok = False
        metrics.append(_metric(
            key,value=observed,unit="count",
            status=status if ok else "SOURCE_HOLD",
            owner=owner,scope=scope,window_days=window,
            source_ref=(territory.get("source_revision_fingerprint")
                if owner in ("market_gps","restricted_reply_lineage")
                else storm.get("source_revision_sha256")
                if owner == "storm_intelligence_runtime" else None)
                if ok else None,
            limitation=limitation,
        ))

    market_window: int | None = None
    if t:
        cards = territory.get("territory_research_cards")
        if (not isinstance(cards,list)
                or type(territory.get("market_count")) is not int
                or len(cards)!=territory["market_count"]
                or not cards
                or any(not isinstance(row,Mapping) or
                       type(row.get("source_window_days")) is not int or
                       row["source_window_days"] != cards[0].get("source_window_days")
                       for row in cards)):
            t = False
            checks["territory_research"] = False
        else:
            market_window = cards[0]["source_window_days"]
    count("territory_market_research_count",territory,"market_count",t,
          "market_gps","niche_territory_aggregate",market_window,
          "Number of reported territory/niche research records, not verified buyers")
    count("territory_commercial_observation_market_count",territory,
          "reported_commercial_demand_market_count",t,"market_gps",
          "niche_territory_aggregate",market_window,
          "Reported source observations only, not independently authenticated purchases")
    count("territory_competitor_coverage_market_count",territory,
          "reported_competitor_research_market_count",t,"market_gps",
          "niche_territory_aggregate",market_window,
          "Coverage is not market share or paid demand")
    # Source lineage is usable only if its referenced territory cohort is
    # still structurally valid and source revision matched.
    l = l and t
    checks["restricted_reply_lineage"] = l
    if l:
        lineage_counts=lineage.get("source_reported_lineage_counts")
        if not isinstance(lineage_counts,Mapping):
            l=False
            checks["restricted_reply_lineage"]=False
        else:
            l = (
                type(lineage.get("reply_lineage_window_days")) is int
                and lineage.get("reply_lineage_window_days")==90
                and type(lineage.get("territory_research_window_days")) is int
                and lineage.get("territory_research_window_days")==market_window
            )
            checks["restricted_reply_lineage"]=l
    for key,field in (
        ("restricted_reply_records_observed","reply_records_observed"),
        ("restricted_replies_matched_to_prospect","reply_records_matched_to_prospect"),
        ("unverified_positive_reply_classifications","positive_classification_records_unverified"),
    ):
        count(key,lineage_counts if l else {},field,l,"restricted_reply_lineage",
              "90_day_reply_lineage_global",90,
              "Independent 90-day reply aggregate cannot be attributed to a 7-day territory or called a buyer")
    for key,field,comment in (
        ("storm_events_observed", "storm_event_observation_count",
         "Producer-reported storm observations, not verified local damage or demand"),
        ("storm_events_source_valid", "source_valid_storm_event_count",
         "Source-validated storm events do not prove exposed customers or properties"),
        ("storm_exposed_subjects_source_supported", "supported_subject_count",
         "Exposed subject association is not an independently verified damage claim"),
        ("storm_buyer_product_matches_considered", "matched_buyer_product_record_count",
         "A matching product/buyer record is not an accepted buyer contract"),
        ("storm_opportunity_candidates", "source_opportunity_candidate_count",
         "Opportunity candidates are research, not paid business"),
        ("storm_blocked_assessments", "blocked_assessment_count",
         "Blocked attempts are not opportunities or completed commercial actions"),
    ):
        count(key,storm,field,s,"storm_intelligence_runtime",
              "separate_storm_source_snapshot",None,comment)
    for key,field,comment in (
        ("quant_source_outcome_labels","predictive_source_outcome_count",
         "Non-exhaustive source labels, not the count of paid outcomes"),
        ("probability_ready_products","probability_ready_product_count",
         "Product-model readiness, not issued/registered original predictions"),
        ("buyer_terms_observed_by_capacity_owner","canonical_capacity_terms_verified_count",
         "Owner-reported terms count; not independently audited buybox"),
        ("buyer_capacity_observed_by_owner","canonical_capacity_verified_count",
         "Owner-reported capacity count; not verified settlement"),
    ):
        count(key,outcomes,field,o,"predictive_and_buyer_capacity",
              "independent_owner_snapshots",None,comment)
    for key,field,limitation in (
        ("global_recognized_revenue_minor","global_recognized_revenue_minor_from_pulse",
         "Company-wide actual reporting scope; cannot be attributed to this opportunity"),
        ("global_realized_gross_profit_minor","global_realized_gp_minor_from_pulse",
         "Company-wide gross profit may be negative and is not cohort forecast error"),
        ("economic_memory_outcome_memories","economic_memory_outcome_conditioned_count",
         "Independent Economic Memory observation count, not original settled deals"),
        ("economic_memory_calibration_evidence","economic_memory_calibration_evidence_count",
         "Reported calibration evidence count, not proof of complete forecast/outcome pairs"),
    ):
        signed=field=="global_realized_gp_minor_from_pulse"
        value=None
        safe=e
        if e:
            raw=economic_truth.get(field)
            if type(raw) is int and (-10**14 if signed else 0)<=raw<=10**14:
                value=raw
            else:
                safe=False
        metrics.append(_metric(
            key,value=value,unit="minor_currency_unit" if "minor" in key else "count",
            status="AGGREGATE_GLOBAL_FINANCE_OBSERVED" if safe else "SOURCE_HOLD",
            owner="finance_and_economic_memory",scope="global_not_single_opportunity",
            window_days=None,source_ref=None,limitation=limitation,
        ))
    missing=(
        ("authenticated_first_party_buyers","Original contact, source, terms and capacity auth required"),
        ("registered_pre_outcome_profit_forecasts","Signed immutable original forecast registry readback required"),
        ("verified_paid_orders_by_opportunity","Verified provider/settlement/fulfilment source receipts required"),
        ("verified_customer_value_saved","Consented baseline+holdout with owner measurement required"),
        ("forecast_brier_score","Matched original registered probability and verified binary outcome cohort required"),
        ("forecast_profit_mae","Matched original revenue/GP forecast and attributed actuals required"),
        ("profit_prediction_error_minor","Single-cohort original predicted GP and actual GP required"),
    )
    for key,reason in missing:
        metrics.append(_metric(
            key,value=None,
            unit="score" if key=="forecast_brier_score" else
                 "minor_currency_unit" if key in ("forecast_profit_mae","profit_prediction_error_minor") else
                 "count",
            status="NOT_CONNECTED_OR_AUTHENTICATED",
            owner="scientific_quant_and_commerce_finance_source_owners",
            scope="prospective_original_tenant_product_territory_cohort",
            window_days=None,source_ref=None,limitation=reason,
        ))
    count("bls_original_index_series_count",bls if b else {},
          "series_observation_count",b,"bls_economic_source_owner",
          "national_or_source_series_geography",None,
          "Source series coverage only; not verified supplier prices, invoices or margin")
    observed=sum(x["value"] is not None for x in metrics)
    return {
        "schema_version":SCHEMA,"status":"MEASUREMENT_INSTRUMENT_EVIDENCE_READINESS_REVIEWED",
        "mode":"OBSERVE","reviewed_at":as_of.isoformat(),
        "source_check_status":checks,
        "bls_cost_index_source_status":bls.get("status") if isinstance(bls,Mapping) else "BLS_OWNER_SOURCE_NOT_CONNECTED",
        "bls_year_over_year_research_cards":list(bls["series_research_cards"]) if b else [],
        "bls_series_are_verified_local_supplier_costs":False,
        "bls_series_joined_to_original_market_twin":False,
        "storm_source_status":storm.get("status"),
        "storm_source_age_hours":storm.get("source_age_hours"),
        "storm_source_last_observed_at":storm.get("source_snapshot_generated_at"),
        "storm_events_are_geo_bound_to_revenue_gps_markets":False,
        "storm_correlation_is_verified_causal_impact":False,
        "measurement_count":len(metrics),
        "available_aggregate_measurement_count":observed,
        "missing_or_held_measurement_count":len(metrics)-observed,
        "measurements":metrics,
        "open_source_instrument_plan":[
            {"instrument_key":key,"technology":tech,"existing_or_future_owner":owner,
             "intended_role":role,"installed_or_activated_by_this_review":False}
            for key,tech,owner,role in OPEN_INSTRUMENTS
        ],
        "source_merge_compatibility_review_needed":not (
            p and producer.get("feature_producer_uses_production_restricted_contract") is True
            and producer.get("production_source_uses_restricted_read_only_query") is True
            and producer.get("exact_producer_code_revision_equal") is True
        ),
        "source_revisions_are_a_single_atomic_financial_cohort":False,
        "production_otel_sdk_or_mlflow_installed_verified_by_this_review":False,
        "model_metrics_computed":False,"model_training_allowed":False,
        "verified_customer_profit_by_market_computed":False,
        "new_external_service_started":False,"outbound_sent":False,
        "database_writes":False,"execution_authority":"none",
        "next_owner":"existing_source_provenance_scientific_quant_and_economic_memory_owners",
        "next_action":"AUTHENTICATE_AND_REGISTER_FIRST_FORECAST_OUTCOME_PAIRS_THEN_ENABLE_MODEL_INSTRUMENTS",
    }
