"""V4.21 brain mathematical gates: test-only inputs, no business fixtures."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from empire_os.predictive_revenue_brain_staging_v421 import (
    SCHEMA, HALF_LIFE_HOURS, decay_weight, rpc_risk_screen,
    historical_z_shield, inspect_signed_company_brain,
)
from empire_os.predictive_revenue_universal_margin import _canonical_hash

NOW = datetime(2026, 10, 25, 21, tzinfo=timezone.utc)


@pytest.mark.parametrize("family,hours", [
    ("WEATHER_STORM",12),("SEARCH_DEMAND",24),
    ("PERMIT_FILING",168),("CRM_CAPACITY",1),
])
def test_decay_exact_half_life_and_zero_age(family,hours):
    as_of=NOW.isoformat()
    issued=(NOW-timedelta(hours=hours)).isoformat()
    r=decay_weight(signal_family=family,occurred_at_utc=issued,
                   published_at_utc=issued,as_of_utc=as_of)
    assert r["half_life_hours"]==hours
    assert r["decay_weight_research_only"]==pytest.approx(0.5)
    assert r["live_forecast_impact_authorized"] is False
    fresh=decay_weight(signal_family=family,occurred_at_utc=as_of,
                       published_at_utc=as_of,as_of_utc=as_of)
    assert fresh["decay_weight_research_only"]==1.0
    assert r["execution_authority"]=="none"


def test_decay_very_stale_not_negative_and_no_fallback():
    r=decay_weight(signal_family="CRM_CAPACITY",
                   occurred_at_utc=(NOW-timedelta(days=180)).isoformat(),
                   published_at_utc=(NOW-timedelta(days=179)).isoformat(),
                   as_of_utc=NOW.isoformat())
    assert r["decay_weight_research_only"]==0
    with pytest.raises(ValueError,match="brain_unknown_signal_family_no_fallback"):
        decay_weight(signal_family="NEW_UNAUTHORIZED_SIGNAL",
                     occurred_at_utc=NOW.isoformat(),
                     published_at_utc=NOW.isoformat(),
                     as_of_utc=NOW.isoformat())


@pytest.mark.parametrize("published,occurred", [
    (1,0),(-1,1),
])
def test_decay_refuses_lookahead_and_future_published(published,occurred):
    with pytest.raises(ValueError,match="brain_signal_future_or_unpublished_at_cutoff"):
        decay_weight(signal_family="WEATHER_STORM",
                     occurred_at_utc=(NOW+timedelta(hours=occurred)).isoformat(),
                     published_at_utc=(NOW+timedelta(hours=published)).isoformat(),
                     as_of_utc=NOW.isoformat())


def test_usd_risk_uses_15_usd_without_claiming_bayesian_interval():
    high=rpc_risk_screen(currency="USD",predicted_rpc_minor=3000,
                         signal_uncertainty_minor=500)
    low=rpc_risk_screen(currency="USD",predicted_rpc_minor=2000,
                        signal_uncertainty_minor=400)
    assert high["target_margin_minor"]==1500
    assert high["research_interval_lower_minor"]=="2020.00"
    assert high["research_lower_below_target"] is False
    assert high["capital_throttle_active_fail_closed"] is True
    assert high["coverage_95_percent_independently_calibrated"] is False
    assert high["decision"]=="HOLD_NORMAL_BAND_NOT_CALIBRATED_NO_CAPITAL_AUTHORITY"
    assert low["research_interval_lower_minor"]=="1216.00"
    assert low["research_lower_below_target"] is True
    assert low["decision"]=="THROTTLE_RESEARCH_LOWER_BOUND_BELOW_TARGET"
    assert low["paid_media_or_funds_authorized"] is False


def test_risk_unsupported_currency_implicitly_has_no_exchange_rate():
    r=rpc_risk_screen(currency="GBP",predicted_rpc_minor=2000,
                      signal_uncertainty_minor=400)
    assert r["target_margin_minor"] is None
    assert r["research_interval_lower_minor"] is None
    assert r["capital_throttle_active_fail_closed"] is True
    assert "HOLD_" in r["decision"]
    explicit=rpc_risk_screen(currency="GBP",predicted_rpc_minor=2000,
                             signal_uncertainty_minor=400,
                             target_margin_minor=1500)
    assert explicit["target_margin_minor"]==1500
    assert explicit["paid_media_or_funds_authorized"] is False


@pytest.mark.parametrize("field,value",[
    ("predicted_rpc_minor", True),
    ("predicted_rpc_minor",-1),
    ("predicted_rpc_minor",1.0),
    ("signal_uncertainty_minor",-1),
    ("signal_uncertainty_minor",False),
    ("target_margin_minor",-2),
])
def test_risk_refuses_invalid_money_numeric_types(field,value):
    args=dict(currency="USD",predicted_rpc_minor=2000,
              signal_uncertainty_minor=400,target_margin_minor=1500)
    args[field]=value
    with pytest.raises(ValueError,match="brain_invalid_.*_minor"):
        rpc_risk_screen(**args)


def test_anomaly_shields_using_only_previous_history_and_preserves_source():
    rows=[5]*12
    before=deepcopy(rows)
    unexpected=historical_z_shield(previous_counts=rows,candidate_count=100)
    equal=historical_z_shield(previous_counts=rows,candidate_count=5)
    assert rows==before
    assert unexpected["flag_for_manual_review"] is True
    assert unexpected["absolute_z_score"] is None
    assert "ZERO_VARIANCE" in unexpected["decision"]
    assert unexpected["raw_records_deleted_or_modified"] is False
    assert equal["flag_for_manual_review"] is False


def test_anomaly_greater_than_three_not_moving_baseline_with_current_sample():
    baseline=[0]*11+[12]
    record=historical_z_shield(previous_counts=baseline,candidate_count=20)
    assert record["flag_for_manual_review"] is True
    assert float(record["absolute_z_score"])>3
    reasonable=historical_z_shield(previous_counts=baseline,candidate_count=4)
    assert reasonable["flag_for_manual_review"] is False
    assert reasonable["historical_population_completeness_proven"] is False


@pytest.mark.parametrize("rows,candidate",[
    ([1]*11,2),([1]*366,2),([True]*12,2),([1]*12,-1),
])
def test_anomaly_refuses_missing_or_invalid_baselines(rows,candidate):
    with pytest.raises(ValueError,match="brain_"):
        historical_z_shield(previous_counts=rows,candidate_count=candidate)


def signed_read_only_history(months: int=13, spike: int=100):
    start_index=2025*12+9
    series=[]
    for idx in range(months):
        absolute=start_index+idx
        year=(absolute-1)//12
        month=(absolute-1)%12+1
        series.append({
            "event_month_utc":f"{year:04d}-{month:02d}",
            "opportunities_opened_events":spike if idx==months-1 else 5,
        })
    return {
        "mode":"SIGNED_COMPANY_EXPORT_REVIEW_ONLY",
        "signature_mathematically_valid_for_supplied_trusted_key":True,
        "execution_authority":"none",
        "eligible_for_training_or_live_prediction":False,
        "tenant_scope":"tenant:brain_fixture","company_scope":"company:brain_fixture",
        "currency":"GBP","as_of_utc":NOW.isoformat(),
        "snapshot_sha256_not_external_attestation":"fixture-not-proof",
        "historical_company_timeline":{
            "tenant_scope":"tenant:brain_fixture",
            "company_scope":"company:brain_fixture","currency":"GBP",
            "execution_authority":"none",
            "monthly_event_time_timeline_not_issued_forecasts":series,
        },
    }


def test_company_brain_integrates_13_historic_months_as_review_only():
    report=inspect_signed_company_brain(signed_review=signed_read_only_history())
    assert report["schema_version"]==SCHEMA
    assert report["historical_activity_anomaly"]["flag_for_manual_review"] is True
    assert report["adaptive_decay"]["weights_computed_for_company_export"] is False
    assert report["rpc_risk"]["capital_throttle_active_fail_closed"] is True
    assert report["training_or_model_promotion_authorized"] is False
    assert report["automatic_data_quarantine_or_deletion_executed"] is False
    assert report["execution_authority"]=="none"
    assert report["snapshot_sha256_not_source_attestation"]==_canonical_hash({
        k:v for k,v in report.items() if k!="snapshot_sha256_not_source_attestation"
    })


def test_company_brain_missing_months_and_actual_data_do_not_fake_anomaly():
    report=inspect_signed_company_brain(
        signed_review=signed_read_only_history(months=3))
    assert report["historical_activity_anomaly"] is None
    assert report["historical_activity_anomaly_status"].startswith("HOLD_")
    assert report["real_30_60_90_day_model_accuracy_proven"] is False


def test_company_brain_holds_noncontiguous_historical_months():
    data=signed_read_only_history()
    data["historical_company_timeline"][
        "monthly_event_time_timeline_not_issued_forecasts"][3]["event_month_utc"]="2025-02"
    result=inspect_signed_company_brain(signed_review=data)
    assert result["historical_activity_anomaly"] is None


def test_company_brain_refuses_unsigned_or_unscoped_data():
    data=signed_read_only_history()
    data["signature_mathematically_valid_for_supplied_trusted_key"]=False
    with pytest.raises(ValueError,match="brain_requires_prior_signed_readonly_company_review"):
        inspect_signed_company_brain(signed_review=data)
    data=signed_read_only_history()
    data["historical_company_timeline"]["company_scope"]="company:other"
    with pytest.raises(ValueError,match="brain_mismatched_company_timeline"):
        inspect_signed_company_brain(signed_review=data)


from empire_os.predictive_revenue_brain_staging_v421 import (
    V5_CORE_NICHES, V5_CLOUD_SCHEMA, V5_USD_FLOOR_MINOR,
    review_v5_cloud_staging,
)


def v5_signed_company(currency="USD"):
    row=signed_read_only_history(months=3)
    row["currency"]=currency
    row["historical_company_timeline"]["currency"]=currency
    row["model_promotion_or_payment_authorized"]=False
    row["financial_settlement_refunds_or_costs_reconciled"]=False
    row["source_registry_and_data_rights_independently_authenticated"]=False
    return row


def v5_signal(i,sector,family):
    stamp=(NOW-timedelta(hours=4)).isoformat()
    return {
        "signal_id":f"source-event-{i:03d}",
        "tenant_scope":"tenant:brain_fixture",
        "company_scope":"company:brain_fixture",
        "sector":sector,
        "family":family,
        "source_id":f"original-owner-{i:03d}",
        "source_receipt_sha256":"a"*64,
        "occurred_at_utc":stamp,
        "published_at_utc":(NOW-timedelta(hours=2)).isoformat(),
        "ingested_at_utc":(NOW-timedelta(hours=1)).isoformat(),
        "observed_count":100 if i==1 else 5,
        "previous_counts":[5]*12,
        "evidence_basis":"UNRECONCILED",
    }


def v5_forecast(i,sector,horizon):
    issued=NOW-timedelta(days=2)
    return {
        "forecast_id":f"predictive-issued-{i:03d}",
        "opportunity_id":f"opportunity-{i:03d}",
        "tenant_scope":"tenant:brain_fixture",
        "company_scope":"company:brain_fixture",
        "sector":sector,
        "currency":"USD",
        "horizon_days":horizon,
        "issued_at_utc":issued.isoformat(),
        "feature_published_at_utc":(issued-timedelta(days=1)).isoformat(),
        "target_at_utc":(issued+timedelta(days=horizon)).isoformat(),
        "predicted_rpc_minor":2000 if i==1 else 3000,
        "uncertainty_minor":400 if i==1 else 500,
        "predicted_cvr_bps":2800,
        "original_issuance_receipt_sha256":"b"*64,
        "evidence_basis":"UNRECONCILED",
    }


def test_v5_four_niche_signed_signal_and_horizon_risk_pipeline_is_observer_only():
    names=V5_CORE_NICHES
    families=tuple(HALF_LIFE_HOURS)
    signals=[v5_signal(i+1,name,families[i]) for i,name in enumerate(names)]
    forecast=[
        v5_forecast(1,names[0],30),
        v5_forecast(2,names[1],60),
        v5_forecast(3,names[2],90),
        v5_forecast(4,names[3],90),
    ]
    r=review_v5_cloud_staging(
        signed_company_review=v5_signed_company(),
        signal_rows=signals,
        issued_forecast_rows=forecast,
    )
    assert r["schema_version"]==V5_CLOUD_SCHEMA
    assert r["usd_rpc_floor_minor"]==1800
    assert r["horizons_days"]==[30,60,90]
    assert tuple(r["all_four_core_niches"])==names
    assert len(r["signal_ingest_research_rows_unverified"])==4
    assert len(r["issued_forecast_risk_screens_unverified"])==4
    assert r["all_four_core_niches"]["PAY_PER_CALL"]["anomaly_manual_review_flags"]==1
    assert r["all_four_core_niches"]["PAY_PER_CALL"][
        "research_lower_bound_below_floor_rows"]==1
    assert r["all_four_core_niches"]["HOME_SERVICES"][
        "research_lower_bound_below_floor_rows"]==0
    assert all(niche["approved_bids_observed_or_authorized"]==0
               for niche in r["all_four_core_niches"].values())
    assert all(niche["risk_throttle_active"] is True
               for niche in r["all_four_core_niches"].values())
    assert r["capital_risk_throttle_active_all_niches"] is True
    assert r["mature_30_60_90_forecast_outcome_evaluation"] is None
    assert r["model_arena_human_promotion_or_retraining_authorized"] is False
    assert r["anomaly_original_records_deleted_or_quarantined"] is False
    assert r["claim_100000_real_staging_events_independently_verified"] is False
    assert r["claim_22_2_percent_real_mae_gain_independently_verified"] is False
    assert r["snapshot_sha256_not_production_attestation"]==_canonical_hash({
        k:v for k,v in r.items() if k!="snapshot_sha256_not_production_attestation"
    })


def test_v5_no_signals_no_forecasts_holds_no_fabricated_approval_metrics():
    r=review_v5_cloud_staging(signed_company_review=v5_signed_company())
    assert r["signal_ingest_research_rows_unverified"]==[]
    assert r["issued_forecast_risk_screens_unverified"]==[]
    assert all(niche["real_world_bid_approval_rate_verified"] is None
               for niche in r["all_four_core_niches"].values())
    assert r["decision"].startswith("HOLD_")
    assert r["execution_authority"]=="none"


@pytest.mark.parametrize("bad_field,bad_value,error",[
    ("tenant_scope","tenant:other","v5_cross_tenant_company_or_niche_signal_denied"),
    ("company_scope","company:other","v5_cross_tenant_company_or_niche_signal_denied"),
    ("sector","NATIVE_ADS","v5_cross_tenant_company_or_niche_signal_denied"),
    ("family","UNKNOWN_SIGNAL","v5_unverified_or_unknown_signal_family"),
    ("evidence_basis","SYNTHETIC","v5_unverified_or_unknown_signal_family"),
    ("source_receipt_sha256","xyz","v5_signal_receipt_fingerprint_required"),
    ("ingested_at_utc",(NOW+timedelta(days=1)).isoformat(),
     "v5_signal_timeline_future_information_denied"),
])
def test_v5_rejects_untrusted_signal_context(bad_field,bad_value,error):
    row=v5_signal(1,"PAY_PER_CALL","WEATHER_STORM")
    row[bad_field]=bad_value
    with pytest.raises(ValueError,match=error):
        review_v5_cloud_staging(signed_company_review=v5_signed_company(),
                                signal_rows=[row])


def test_v5_rejects_duplicate_and_false_anomaly_baseline():
    a=v5_signal(1,"PAY_PER_CALL","WEATHER_STORM")
    with pytest.raises(ValueError,match="v5_invalid_or_duplicate_signal_id"):
        review_v5_cloud_staging(signed_company_review=v5_signed_company(),
                                signal_rows=[a,a])
    a["previous_counts"]=[1]*11
    with pytest.raises(ValueError,match="brain_anomaly_requires_historical_baseline"):
        review_v5_cloud_staging(signed_company_review=v5_signed_company(),
                                signal_rows=[a])


@pytest.mark.parametrize("field,value,match",[
    ("currency","GBP","v5_cross_tenant_company_currency_or_basis_forecast"),
    ("tenant_scope","tenant:other","v5_cross_tenant_company_currency_or_basis_forecast"),
    ("evidence_basis","SYNTHETIC","v5_cross_tenant_company_currency_or_basis_forecast"),
    ("horizon_days",15,"v5_exact_30_60_90_horizons_required"),
    ("predicted_cvr_bps",12000,"v5_invalid_predicted_cvr_basis_points"),
    ("issued_at_utc",(NOW+timedelta(days=1)).isoformat(),
     "v5_hindsight_or_wrong_horizon_denied"),
    ("original_issuance_receipt_sha256","test","v5_original_issuance_receipt_fingerprint_required"),
])
def test_v5_rejects_invalid_forecast_evidence(field,value,match):
    row=v5_forecast(1,"PAY_PER_CALL",30)
    row[field]=value
    with pytest.raises(ValueError,match=match):
        review_v5_cloud_staging(signed_company_review=v5_signed_company(),
                                issued_forecast_rows=[row])


def test_v5_rejects_double_counted_opportunity_horizon():
    one=v5_forecast(1,"PAY_PER_CALL",30)
    two=v5_forecast(2,"PAY_PER_CALL",30)
    two["opportunity_id"]=one["opportunity_id"]
    with pytest.raises(ValueError,match="v5_duplicate_opportunity_horizon"):
        review_v5_cloud_staging(signed_company_review=v5_signed_company(),
                                issued_forecast_rows=[one,two])


def test_v5_never_silently_equates_usd_floor_to_gbp():
    r=review_v5_cloud_staging(signed_company_review=v5_signed_company("GBP"))
    assert r["usd_rpc_floor_minor"]==V5_USD_FLOOR_MINOR
    assert r["all_four_core_niches"]["ECOMMERCE"][
        "real_world_bid_approval_rate_verified"] is None


def test_v5_refuses_unsigned_client_history_even_with_plausible_signals():
    row=v5_signed_company()
    row["signature_mathematically_valid_for_supplied_trusted_key"]=False
    with pytest.raises(ValueError,match="v5_requires_signed_readonly_source_and_negative_authority"):
        review_v5_cloud_staging(signed_company_review=row,
                                signal_rows=[v5_signal(1,"PAY_PER_CALL","WEATHER_STORM")])
