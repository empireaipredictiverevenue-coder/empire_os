"""Future trend research: strict time custody, backtesting, no commercial authority."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import json
import math
import pytest
from empire_os.predictive_trend_horizon_review import (
    TrendHorizonHold, review_trend_horizons, HORIZONS,
)

START=datetime(2026,5,1,tzinfo=timezone.utc)
CUTOFF=(START+timedelta(days=91)).isoformat()
LATER=(START+timedelta(days=105)).isoformat()
KW=dict(series_id="roofing_near_me_us_il_v1",source_kind="search_interest_index",
        unit="index_0_100",geography="US-IL",vertical="roofing",
        source_name="owned_historical_observation")

def source(i,value=None,revision=1):
    seen=START+timedelta(days=i*7)
    return dict(
        **KW, observed_at=seen.isoformat(),
        first_available_at=(seen+timedelta(hours=1)).isoformat(),
        ingested_at=(seen+timedelta(hours=2)).isoformat(),
        revision=revision,value=(10+i*4 if value is None else value),
        evidence_sha256="a"*64,
    )

def review(rows,**changes):
    kw=dict(KW)
    kw.update(changes)
    return review_trend_horizons(rows,as_of=CUTOFF,review_at=LATER,**kw)


def test_chronological_drift_baseline_and_7_30_90_horizon():
    r=review([source(i) for i in range(13)])
    assert r["status"]=="OBSERVED_TREND_RESEARCH_ONLY"
    assert r["distinct_as_of_observations"]==13
    assert r["observed_direction"]=="up"
    assert r["rolling_backtest"]["fold_count"]==8
    assert r["rolling_backtest"]["drift_beats_naive"] is True
    assert r["rolling_backtest"]["drift_mae"]==0
    assert [s["days"] for s in r["future_scenarios"]]==[7,30,90]
    assert r["future_scenarios"][0]["directional_scenario_value"] is not None
    assert r["future_scenarios"][1]["directional_scenario_value"] is not None
    assert r["future_scenarios"][2]["directional_scenario_value"] is None
    assert r["google_trends_index_is_not_absolute_search_volume"] is True
    for key in (
        "source_owner_authenticated","tenant_and_usage_rights_verified",
        "calibrated_prediction_intervals_available","forecast_accuracy_verified_on_customer_outcomes",
        "original_conversion_registry_verified","actual_revenue",
        "commercial_forecast_authorized","outbound_or_payment_action","database_writes",
        "cross_source_numeric_fusion_used",
    ):
        assert r[key] is False
    assert r["execution_authority"]=="none"
    text=json.dumps(r)
    assert KW["series_id"] not in text
    assert KW["source_name"] not in text


def test_late_backfill_cannot_change_old_forecast_manifest_or_numbers():
    source_rows=[source(i) for i in range(13)]
    first=review(source_rows)
    future_revision=source(6,value=99,revision=2)
    future_revision["first_available_at"]=(START+timedelta(days=98)).isoformat()
    future_revision["ingested_at"]=(START+timedelta(days=99)).isoformat()
    second=review([*source_rows,future_revision])
    assert second["late_or_future_revisions_withheld"]==1
    assert second["source_manifest_sha256_change_detection_only"]==first["source_manifest_sha256_change_detection_only"]
    assert second["future_scenarios"]==first["future_scenarios"]
    assert second["rolling_backtest"]==first["rolling_backtest"]


def test_historical_backtest_never_trains_on_revisions_that_arrived_after_target():
    original=[source(i) for i in range(13)]
    base=review(original)
    correction=source(0,value=95,revision=2)
    correction["first_available_at"]=(START+timedelta(days=89)).isoformat()
    correction["ingested_at"]=(START+timedelta(days=90)).isoformat()
    amended=review([*original,correction])
    assert amended["rolling_backtest"]==base["rolling_backtest"]
    assert amended["source_manifest_sha256_change_detection_only"]!=base["source_manifest_sha256_change_detection_only"]
    assert amended["distinct_as_of_observations"]==13


def test_future_observations_held_and_can_not_backfill_historical_signal():
    rows=[source(i) for i in range(13)]+[source(14)]
    r=review(rows)
    assert r["late_or_future_revisions_withheld"]==1
    assert r["distinct_as_of_observations"]==13


def test_insufficient_history_holds_all_future_scenarios():
    r=review([source(i) for i in range(8)])
    assert r["status"]=="INSUFFICIENT_POINT_IN_TIME_HISTORY"
    assert r["future_scenarios"]==[]
    assert r["future_opportunity_status"]=="UNAVAILABLE"


def test_naive_beats_drift_on_flat_values():
    r=review([source(i,value=15) for i in range(13)])
    assert r["rolling_backtest"]["drift_beats_naive"] is False
    assert all(s["directional_scenario_value"] is None for s in r["future_scenarios"])
    assert r["observed_direction"]=="flat"


def test_stale_series_blocks_even_good_historical_fit():
    asof=(START+timedelta(days=110)).isoformat()
    now=(START+timedelta(days=120)).isoformat()
    r=review_trend_horizons(
        [source(i) for i in range(13)],
        as_of=asof,review_at=now,**KW,
    )
    assert r["source_series_stale_at_as_of"] is True
    assert r["rolling_backtest"]["drift_beats_naive"] is True
    assert all(s["directional_scenario_value"] is None for s in r["future_scenarios"])


@pytest.mark.parametrize("attack",[
    lambda a: a.update(value=float("nan")),
    lambda a: a.update(value=float("inf")),
    lambda a: a.update(value=True),
    lambda a: a.update(value=-1),
    lambda a: a.update(value=120),
    lambda a: a.update(geography="UK"),
    lambda a: a.update(source_name="new_sample_window"),
    lambda a: a.update(first_available_at=(START-timedelta(days=1)).isoformat()),
    lambda a: a.update(ingested_at=(START-timedelta(days=1)).isoformat()),
    lambda a: a.update(first_available_at="2026-05-01T01:00:00"),
    lambda a: a.update(evidence_sha256="NOT_A_HASH"),
    lambda a: a.update(revision=True),
    lambda a: a.update(unreviewed="x"),
])
def test_untrusted_source_shape_or_temporal_leakage_held(attack):
    rows=[source(i) for i in range(13)]
    attack(rows[0])
    with pytest.raises(TrendHorizonHold):
        review(rows)


def test_duplicate_timestamp_revision_refused():
    rows=[source(i) for i in range(13)]
    with pytest.raises(TrendHorizonHold):
        review([rows[0],*rows])


def test_observation_order_does_not_change_results():
    rows=[source(i) for i in range(13)]
    assert review(rows)==review(list(reversed(rows)))


def test_irregular_sampling_not_claimed_as_reliable_forecast():
    rows=[source(i) for i in range(13)]
    rows[7]["observed_at"]=(START+timedelta(days=7*7+2)).isoformat()
    rows[7]["first_available_at"]=(START+timedelta(days=7*7+2,hours=1)).isoformat()
    rows[7]["ingested_at"]=(START+timedelta(days=7*7+2,hours=2)).isoformat()
    # The two-day jitter remains within bounded regular sampling.
    assert review(rows)["status"]=="OBSERVED_TREND_RESEARCH_ONLY"
    rows[7]["observed_at"]=(START+timedelta(days=7*7+6)).isoformat()
    rows[7]["first_available_at"]=(START+timedelta(days=7*7+6,hours=1)).isoformat()
    rows[7]["ingested_at"]=(START+timedelta(days=7*7+6,hours=2)).isoformat()
    assert review(rows)["status"]=="IRREGULAR_SAMPLING_REQUIRES_OWNER_REVIEW"


def test_multiple_sources_with_incomparable_measurements_refused():
    rows=[source(i) for i in range(13)]
    rows[2]["unit"]="count"
    with pytest.raises(TrendHorizonHold):
        review(rows)


def test_no_horizon_longer_than_observed_span_and_forecast_does_not_overflow_index():
    rows=[source(i) for i in range(13)]
    for row in rows:
        row["value"]=min(row["value"]+40,100)
    r=review(rows)
    assert all(
        s["directional_scenario_value"] is None or
        0<=s["directional_scenario_value"]<=100
        for s in r["future_scenarios"]
    )
