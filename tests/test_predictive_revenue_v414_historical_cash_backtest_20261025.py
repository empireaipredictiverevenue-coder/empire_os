"""V4.14 time-frozen revenue CASH backtest: conditional metrics, never proof."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import runpy

import pytest

from empire_os.predictive_revenue_v414_historical_cash_backtest import (
    FIELDS, MIN_COHORTS, MAX_COHORTS, review_v414_historical_cash_backtest_held,
)
from empire_os.predictive_revenue_v412_scenario_twin import simulate_revenue_twin_held
from empire_os.predictive_revenue_v413_canonical_coverage import SCHEMA as V413_SCHEMA

NOW=datetime(2026,10,25,14,0,tzinfo=timezone.utc)
TENANT="00000000-0000-0000-0000-000000000101"
SOURCE="a"*64
_CRED=runpy.run_path(str(
    Path(__file__).resolve().parent /
    "test_predictive_revenue_v412_scenario_twin_20261025.py"
))


@pytest.fixture
def live_shape():
    # Original V4.12 signed Ed25519 fixture, not a caller-invented tenant.
    auth=_CRED["fixture_credentials"]()
    research_twin=simulate_revenue_twin_held(_CRED["scenario"](),**auth)
    coverage={
        "schema_version":V413_SCHEMA, "mode":"OBSERVE",
        "execution_authority":"none",
        "simulated_currency":"GBP",
        "recognition_vs_cash_metric_mismatch":True,
        "event_currency_verified":False,
        "revenue_forecast_calibration_eligible":False,
        "complete_30_60_90_cohort_census_verified":False,
        "actual_revenue_total_cents":None,
        "cash_collected_total_cents":None,
    }
    return research_twin,coverage,auth


def cases(*,count=12,horizon=30,predicted=100000,baseline=50000,actual=98000):
    start=datetime(2026,6,1,tzinfo=timezone.utc)
    result=[]
    for i in range(count):
        began=start+timedelta(days=i)
        horizon_at=began+timedelta(days=horizon)
        result.append({
            "cohort_ref":f"cohort:organic-revenue-case-{i:03}",
            "tenant_id":TENANT,
            "source_evidence_digest":SOURCE,
            "currency_code":"GBP",
            "cohort_start_utc":began.isoformat(),
            "forecast_locked_at":(began-timedelta(hours=1)).isoformat(),
            "horizon_days":horizon,
            "predicted_cash_minor_units":predicted,
            "naive_baseline_cash_minor_units":baseline,
            "claimed_cash_minor_units":actual,
            "outcome_finalized_at":(horizon_at+timedelta(days=1)).isoformat(),
            "outcome_source_ref":f"claim:fictional-cash-event-{i:03}",
        })
    return tuple(result)


def review(live_shape, *, rows=None, twin=None, coverage=None, auth=None, now=NOW):
    orig,orig_cov,orig_auth=live_shape
    return review_v414_historical_cash_backtest_held(
        research_twin=orig if twin is None else twin,
        v413_evidence_coverage=orig_cov if coverage is None else coverage,
        claimed_historical_cohorts=cases() if rows is None else rows,
        as_of=now,
        signed_crm_bearer=(orig_auth if auth is None else auth)["signed_crm_bearer"],
        crm_verifier=(orig_auth if auth is None else auth)["crm_verifier"],
    )


def test_v414_organic_twin_time_holdout_skill_does_not_promote(live_shape):
    result=review(live_shape)
    assert result["status"]=="COMPLETE_CLAIMED_HISTORICAL_SCORECARD_EVIDENCE_HELD"
    assert result["selected_cohort_count"]==12
    assert result["chronological_split_index"]==8
    assert result["all_fixed_selection_mature_claims_present"] is True
    assert result["older_segment"]["scored_cohorts"]==8
    assert result["held_out_recent_segment"]["scored_cohorts"]==4
    assert result["held_out_recent_segment"]["model_mae_minor_units"]==2000
    assert result["held_out_recent_segment"]["naive_baseline_mae_minor_units"]==48000
    assert result["held_out_recent_segment"]["model_skill_vs_baseline_basis_points"]>0
    assert result["all_observed_claims"]["scored_cohorts"]==12
    assert result["currency_code"]=="GBP"
    assert result["p10_p50_p90_empirically_calibrated"] is False
    for flag in (
        "cash_proof_from_canonical_finance", "historical_forecast_registry_verified",
        "tenant_cohort_completeness_verified", "actual_revenue_recognized_by_review",
        "actual_cash_collected_verified", "calibration_release_authorized",
        "model_updated", "economic_memory_written", "outbound_authorized",
        "paid_traffic_authorized", "funds_moved",
    ):
        assert result[flag] is False


@pytest.mark.parametrize("horizon", [30,60,90])
def test_v414_only_fixed_30_60_90_day_horizons(live_shape,horizon):
    result=review(live_shape,rows=cases(horizon=horizon))
    assert result["horizon_days"]==horizon
    assert result["all_observed_claims"]["scored_cohorts"]==12


def test_v414_missing_outcome_is_unknown_never_zero_or_survivor_only(live_shape):
    history=list(cases())
    history[-1]=dict(history[-1],claimed_cash_minor_units=None,
                     outcome_finalized_at=None,outcome_source_ref=None)
    report=review(live_shape,rows=tuple(history))
    assert report["status"]=="HISTORICAL_COHORT_COVERAGE_INCOMPLETE_HELD"
    assert report["unknown_outcome_count"]==1
    assert report["all_observed_claims"]["scored_cohorts"]==0
    assert report["held_out_recent_segment"]["model_mae_minor_units"] is None
    assert "MISSING_OUTCOMES_CANNOT_BE_ZERO" in report["blockers"]


def test_v414_unmatured_cohort_blocked_not_labeled_performance(live_shape):
    history=list(cases())
    last=datetime(2026,10,20,tzinfo=timezone.utc)
    history[-1]=dict(
        history[-1],
        cohort_start_utc=last.isoformat(),
        forecast_locked_at=(last-timedelta(hours=1)).isoformat(),
        claimed_cash_minor_units=None,outcome_finalized_at=None,outcome_source_ref=None,
    )
    report=review(live_shape,rows=tuple(history))
    assert report["immature_outcome_count"]==1
    assert report["all_observed_claims"]["scored_cohorts"]==0
    assert "COHORT_HAS_NOT_REACHED_FORECAST_HORIZON" in report["blockers"]


def test_v414_inaccurate_prediction_blocked_even_as_research_skill(live_shape):
    report=review(live_shape,rows=cases(predicted=250000,baseline=97000))
    assert report["held_out_recent_segment"]["model_skill_vs_baseline_basis_points"]<0
    assert "MODEL_NOT_BETTER_THAN_HISTORICAL_BASELINE" in report["blockers"]


@pytest.mark.parametrize("field,value,expected",[
    ("tenant_id","00000000-0000-0000-0000-000000000102","V414_COHORT_SOURCE"),
    ("currency_code","USD","V414_COHORT_SOURCE"),
    ("source_evidence_digest","b"*64,"V414_COHORT_SOURCE"),
    ("horizon_days",31,"V414_HORIZON"),
    ("horizon_days",True,"V414_HORIZON"),
    ("predicted_cash_minor_units",True,"V414_INTEGER"),
    ("claimed_cash_minor_units",-5,"V414_INTEGER"),
    ("naive_baseline_cash_minor_units",10**16,"V414_INTEGER"),
    ("forecast_locked_at","2026-06-01T00:00:00+00:00","V414_TEMPORAL"),
    ("outcome_source_ref","canonical:commercial_events:faked","V414_EXPLICIT_UNVERIFIED"),
    ("outcome_finalized_at","2026-06-29T00:00:00+00:00","V414_OUTCOME_FINALITY"),
    ("cohort_ref"," ", "V414_BOUNDED_UNIQUE"),
])
def test_v414_forged_row_fields_fail_closed(live_shape,field,value,expected):
    history=list(cases())
    history[0]=dict(history[0],**{field:value})
    with pytest.raises(ValueError,match=expected):
        review(live_shape,rows=tuple(history))


def test_v414_duplicate_or_out_of_order_cohorts_fail(live_shape):
    history=list(cases())
    history[-1]=dict(history[-1],cohort_ref=history[0]["cohort_ref"])
    with pytest.raises(ValueError,match="UNIQUE_COHORT"):
        review(live_shape,rows=tuple(history))
    history=list(cases())
    history[-1]=dict(history[-1],cohort_start_utc=history[0]["cohort_start_utc"])
    with pytest.raises(ValueError,match="TEMPORAL"):
        review(live_shape,rows=tuple(history))


def test_v414_mixed_time_horizons_and_explicit_missing_fields_rejected(live_shape):
    history=list(cases())
    history[-1]=dict(history[-1],horizon_days=60)
    with pytest.raises(ValueError,match="MIXED_HORIZON"):
        review(live_shape,rows=tuple(history))
    history=list(cases())
    del history[-1]["currency_code"]
    with pytest.raises(ValueError,match="EXACT_HISTORICAL"):
        review(live_shape,rows=tuple(history))


@pytest.mark.parametrize("length", [0,11,241])
def test_v414_12_to_240_historical_cohort_bounds(live_shape,length):
    with pytest.raises(ValueError,match="BOUNDED_COHORT"):
        review(live_shape,rows=cases(count=length))


def test_v414_untrusted_twin_or_coverage_promotion_rejected(live_shape):
    twin=deepcopy(live_shape[0])
    twin["approved_commercial_forecast"]=True
    with pytest.raises(ValueError,match="ORIGINAL_NONPROMOTABLE_TWIN"):
        review(live_shape,twin=twin)
    coverage=deepcopy(live_shape[1])
    coverage["revenue_forecast_calibration_eligible"]=True
    with pytest.raises(ValueError,match="CANONICAL_COVERAGE_HOLD"):
        review(live_shape,coverage=coverage)


def test_v414_original_crm_active_membership_and_tamper_checks(live_shape):
    auth=dict(live_shape[2])
    auth["signed_crm_bearer"] += "junk"
    with pytest.raises(ValueError,match="ACTIVE_ORIGINAL_CRM"):
        review(live_shape,auth=auth)
    auth=dict(live_shape[2])
    auth["crm_verifier"]=object()
    with pytest.raises(ValueError,match="ORIGINAL_CRM_VERIFIER"):
        review(live_shape,auth=auth)


def test_v414_no_extra_services_or_database_actions():
    source=(Path(__file__).resolve().parents[1] /
        "empire_os/predictive_revenue_v414_historical_cash_backtest.py").read_text()
    for forbidden in (
        "CREATE TABLE", "psycopg.connect(", "systemctl", "send_message(",
        "send_email(", "commit(", "redis.Redis(", "app.include_router(",
        "execute_payment(", "execute_trade(", "trainer.fit(",
    ):
        assert forbidden not in source
    assert MIN_COHORTS==12 and MAX_COHORTS==240
    assert FIELDS and "currency_code" in FIELDS
