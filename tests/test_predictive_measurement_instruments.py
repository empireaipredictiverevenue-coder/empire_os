"""Read-only, multi-owner Predictive + Storm measurement scorecard tests."""
from copy import deepcopy
from datetime import datetime, timezone
import json

from empire_os.predictive_measurement_instruments import build_predictive_measurement_instruments
from empire_os.predictive_storm_measurement import review_storm_measurement
from test_storm_intelligence_runtime import build as storm_build, NOW as STORM_NOW
from test_predictive_market_restricted_provenance import source as market_source
from test_predictive_market_evidence_binding import review as market_review, NOW
from empire_os.predictive_market_restricted_provenance import review_restricted_reply_lineage
from empire_os.predictive_customer_value_outcome_readiness import review_customer_value_outcome_readiness
from test_predictive_customer_value_outcome_readiness import sources as readiness_sources
from test_predictive_profitability_governed_decision import truth


def inputs(storm=None):
    gps=market_source()
    territory=market_review(gps)
    lineage=review_restricted_reply_lineage(gps,territory,as_of=NOW)
    outcomes=review_customer_value_outcome_readiness(
        readiness_sources(),
        as_of=datetime(2026,10,19,22,40,tzinfo=timezone.utc),
    )
    producer={
        "schema_version":"empire.predictive_revenue.market_producer_compatibility.v1",
        "status":"SOURCE_OWNER_MERGE_REVIEW_REQUIRED",
        "execution_authority":"none",
        "merge_source_producer_authorized":False,
        "feature_producer_uses_production_restricted_contract":False,
        "production_source_uses_restricted_read_only_query":True,
        "exact_producer_code_revision_equal":False,
    }
    storm_packet=(
        storm if storm is not None else
        review_storm_measurement(storm_build(),as_of=STORM_NOW)
    )
    return territory,lineage,outcomes,truth(),producer,storm_packet


def review(storm=None):
    return build_predictive_measurement_instruments(
        *inputs(storm),as_of=NOW,
    )


def by_name(r):
    return {m["key"]:m for m in r["measurements"]}


def test_full_source_measurement_inventory_keeps_market_and_storm_separate():
    report=review()
    assert report["status"]=="MEASUREMENT_INSTRUMENT_EVIDENCE_READINESS_REVIEWED"
    assert report["source_check_status"]["storm_source"] is True
    assert report["source_check_status"]["territory_research"] is True
    assert report["source_check_status"]["restricted_reply_lineage"] is True
    assert report["storm_events_are_geo_bound_to_revenue_gps_markets"] is False
    assert report["storm_correlation_is_verified_causal_impact"] is False
    m=by_name(report)
    assert m["storm_events_observed"]["value"]==1
    assert m["storm_events_observed"]["source_scope"]=="separate_storm_source_snapshot"
    assert m["storm_events_observed"]["observation_window_days"] is None
    assert m["storm_events_observed"]["source_revision_sha256"]
    assert m["storm_opportunity_candidates"]["value"]==1
    assert m["territory_market_research_count"]["value"]==3
    assert m["restricted_reply_records_observed"]["value"]==10
    assert m["restricted_reply_records_observed"]["observation_window_days"]==90
    assert m["territory_market_research_count"]["observation_window_days"]==7
    assert m["verified_paid_orders_by_opportunity"]["value"] is None
    assert m["forecast_brier_score"]["value"] is None
    assert m["forecast_profit_mae"]["value"] is None
    assert all(m["may_be_used_for_live_profit_calibration"] is False
               for m in report["measurements"])
    assert report["model_metrics_computed"] is False
    assert report["model_training_allowed"] is False
    assert report["new_external_service_started"] is False
    assert report["source_merge_compatibility_review_needed"] is True
    assert "tenant-1" not in json.dumps(report)
    assert "private@buyer.example" not in json.dumps(report)


def test_stale_storm_produces_unknown_not_zero_and_leaves_other_source_intact():
    old=review_storm_measurement(
        storm_build(),as_of=STORM_NOW.replace(year=2026,month=10,day=20)
    )
    assert old["status"]=="STORM_SOURCE_STALE_HOLD"
    report=review(old)
    metrics=by_name(report)
    assert report["source_check_status"]["storm_source"] is False
    assert metrics["storm_events_observed"]["value"] is None
    assert metrics["storm_events_observed"]["evidence_status"]=="SOURCE_HOLD"
    assert metrics["storm_opportunity_candidates"]["value"] is None
    assert metrics["territory_market_research_count"]["value"]==3
    assert metrics["forecast_brier_score"]["value"] is None
    assert report["storm_source_age_hours"] > 24


def test_storm_metric_authenticity_cannot_be_self_certified():
    storm=review_storm_measurement(storm_build(),as_of=STORM_NOW)
    forged=deepcopy(storm)
    forged["actual_storm_damage_verified"]=True
    report=review(forged)
    assert by_name(report)["storm_events_observed"]["value"] is None
    assert report["source_check_status"]["storm_source"] is False
    assert report["verified_customer_profit_by_market_computed"] is False


def test_lineage_revision_drift_is_held_not_merged_to_storm():
    a=list(inputs())
    a[1]["original_territory_revision_sha256"]="0"*64
    x=build_predictive_measurement_instruments(*a,as_of=NOW)
    assert x["source_check_status"]["restricted_reply_lineage"] is False
    assert x["source_check_status"]["storm_source"] is True
    assert by_name(x)["restricted_reply_records_observed"]["value"] is None


def test_missing_quant_outcomes_never_result_in_accuracy_or_profit():
    report=review()
    metrics=by_name(report)
    assert metrics["quant_source_outcome_labels"]["value"]==0
    assert metrics["probability_ready_products"]["value"]==0
    assert metrics["economic_memory_outcome_memories"]["value"]==0
    assert metrics["profit_prediction_error_minor"]["value"] is None
    assert metrics["verified_customer_value_saved"]["value"] is None
    assert report["model_training_allowed"] is False


def test_optional_bls_index_source_attaches_to_existing_scorecard_without_cost_fiction():
    from test_predictive_bls_cost_index import owner as sample_bls
    from empire_os.predictive_bls_cost_index import review_bls_cost_index_owner
    packet=sample_bls()
    packet["generated_at"]=NOW.isoformat()
    bls=review_bls_cost_index_owner(packet,as_of=NOW)
    report=build_predictive_measurement_instruments(
        *inputs(),as_of=NOW,bls=bls,
    )
    assert report["source_check_status"]["bls_cost_index_research"] is True
    assert report["bls_cost_index_source_status"]=="BLS_OFFICIAL_INDEX_RESEARCH_REVIEWED"
    assert by_name(report)["bls_original_index_series_count"]["value"]==1
    assert report["bls_year_over_year_research_cards"][0][
        "year_over_year_index_change_pct_research_only"]==10
    assert report["bls_series_are_verified_local_supplier_costs"] is False
    assert report["bls_series_joined_to_original_market_twin"] is False
    assert report["model_training_allowed"] is False
    assert report["verified_customer_profit_by_market_computed"] is False


def test_bls_source_unknown_does_not_change_existing_real_market_and_storm_evidence():
    report=review()
    metrics=by_name(report)
    assert report["source_check_status"]["bls_cost_index_research"] is False
    assert report["bls_cost_index_source_status"]=="BLS_OWNER_SOURCE_NOT_CONNECTED"
    assert metrics["bls_original_index_series_count"]["value"] is None
    assert metrics["territory_market_research_count"]["value"]==3
    assert metrics["storm_events_observed"]["value"]==1
    assert report["bls_year_over_year_research_cards"]==[]


def test_forged_bls_local_spend_or_profit_authentication_blocks_metric_promotion():
    from test_predictive_bls_cost_index import owner as sample_bls
    from empire_os.predictive_bls_cost_index import review_bls_cost_index_owner
    packet=sample_bls();packet["generated_at"]=NOW.isoformat()
    bls=review_bls_cost_index_owner(packet,as_of=NOW)
    bls["actual_material_or_labor_cost_authenticated"]=True
    report=build_predictive_measurement_instruments(*inputs(),as_of=NOW,bls=bls)
    assert report["source_check_status"]["bls_cost_index_research"] is False
    assert by_name(report)["bls_original_index_series_count"]["value"] is None
    assert report["bls_year_over_year_research_cards"]==[]
