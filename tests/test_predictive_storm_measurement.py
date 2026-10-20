"""Storm product instrumentation must never turn an alert into paid demand."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.predictive_storm_measurement import (
    review_storm_measurement, review_storm_measurement_runtime,
)
from test_storm_intelligence_runtime import build, NOW


def source():
    return build()


def review(packet=None,*,time=None):
    return review_storm_measurement(
        source() if packet is None else packet,
        as_of=time if time is not None else NOW + timedelta(hours=1),
    )


def test_original_storm_runtime_emits_measurements_not_authenticated_damage():
    r=review()
    assert r["status"]=="STORM_SOURCE_RESEARCH_MEASURED"
    assert r["storm_event_observation_count"]==1
    assert r["source_valid_storm_event_count"]==1
    assert r["source_opportunity_candidate_count"]==1
    assert r["source_revision_sha256"] and len(r["source_revision_sha256"])==64
    assert r["actual_storm_damage_verified"] is False
    assert r["geographic_property_exposure_verified"] is False
    assert r["buyer_demand_or_terms_verified"] is False
    assert r["storm_opportunity_revenue_verified"] is False
    assert r["economic_twin_weather_shock_calibrated"] is False
    assert r["forecast_outcome_calibration_allowed"] is False
    assert r["candidate_payloads_exposed"] is False
    assert r["execution_authority"]=="none"
    assert "tenant-1" not in json.dumps(r)
    assert "property-1" not in json.dumps(r)
    assert "buyer-1" not in json.dumps(r)


def test_missing_subject_and_match_are_valid_absences_not_paid_opportunities():
    s=build(subjects=[],matches=[])
    r=review(s)
    assert r["status"]=="STORM_SOURCE_RESEARCH_MEASURED"
    assert r["storm_event_observation_count"]==1
    assert r["supported_subject_count"]==0
    assert r["source_opportunity_candidate_count"]==0
    assert r["blocked_assessment_count"]>=1
    assert r["storm_opportunity_revenue_verified"] is False


def test_old_storm_snapshot_does_not_publish_stale_zero_or_old_event_as_live():
    s=source()
    r=review(s,time=NOW+timedelta(days=15))
    assert r["status"]=="STORM_SOURCE_STALE_HOLD"
    assert r["source_snapshot_generated_at"] is not None
    assert r["storm_event_observation_count"] is None
    assert r["source_valid_storm_event_count"] is None
    assert r["source_opportunity_candidate_count"] is None
    assert r["source_diagnostic_counters"] is None
    assert r["economic_twin_weather_shock_calibrated"] is False


@pytest.mark.parametrize("k,v",[
    ("automatic_external_execution_allowed",True),
    ("damage_inferred",True),
    ("buyer_intent_inferred",True),
    ("demand_inferred",True),
    ("pricing_inferred",True),
    ("economics_inferred",True),
    ("execution_authority","send"),
    ("payment_authority","charge"),
    ("unknown_stays_unknown",False),
    ("runtime_schema_version","other"),
    ("available",False),
])
def test_storm_owner_cannot_inflate_commercial_authority(k,v):
    s=source()
    s[k]=v
    r=review(s)
    assert r["status"]=="STORM_SOURCE_CONTRACT_HOLD"
    assert r["source_opportunity_candidate_count"] is None


@pytest.mark.parametrize("k,v",[
    ("candidate_count",100),
    ("candidate_count",True),
    ("candidates",None),
])
def test_candidate_count_and_payload_mismatch_fail_closed(k,v):
    s=source()
    s[k]=v
    assert review(s)["status"]=="STORM_SOURCE_COUNT_HOLD"


@pytest.mark.parametrize("k,v",[
    ("events_valid",100),
    ("events_seen",True),
    ("subjects_supported",100),
    ("opportunities_emitted",500),
    ("events_deduplicated",-1),
    ("source_health","PROFITABLE"),
])
def test_source_diagnostic_forgery_fails_closed(k,v):
    s=source()
    s["diagnostics"][k]=v
    assert review(s)["status"]=="STORM_SOURCE_COUNT_HOLD"


def test_candidate_cannot_self_certify_revenue_or_buyer_intent():
    s=source()
    s["candidates"][0]["commercial_ready"]=True
    assert review(s)["status"]=="STORM_CANDIDATE_AUTHORITY_HOLD"
    s=source()
    s["candidates"][0]["economics"]={"earned_profit":300}
    assert review(s)["status"]=="STORM_CANDIDATE_AUTHORITY_HOLD"


def test_future_storm_report_is_not_current_source():
    r=review(time=NOW-timedelta(hours=1))
    assert r["status"]=="STORM_SOURCE_CLOCK_HOLD"
    assert r["storm_event_observation_count"] is None


def test_read_only_allowlisted_snapshot_does_not_read_private_storm_entities(tmp_path):
    p=tmp_path/"runtime/storm_opportunity/latest.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(source()))
    (p.parent/"private_property_accounts.json").write_text("SECRET_CUSTOMER")
    r=review_storm_measurement_runtime(tmp_path,as_of=NOW+timedelta(hours=1))
    assert r["status"]=="STORM_SOURCE_RESEARCH_MEASURED"
    assert "SECRET_CUSTOMER" not in json.dumps(r)
    p.unlink()
    missing=review_storm_measurement_runtime(tmp_path,as_of=NOW)
    assert missing["status"]=="STORM_SOURCE_UNAVAILABLE"


def test_source_health_unknown_does_not_enable_storm_measurements():
    bad=source()
    bad["diagnostics"]["source_health"]="UNKNOWN"
    out=review(bad)
    assert out["status"]=="STORM_SOURCE_HEALTH_HOLD"
    assert out["storm_event_observation_count"] is None
    assert out["source_research_usable_for_current_market_simulation"] is False


def test_storm_revision_covers_full_candidate_evidence_not_just_counters():
    a=source()
    b=deepcopy(a)
    b["candidates"][0]["exposure"]["state"]="INFERRED"
    b["candidates"][0]["trace_hypothesis_key"]="different_research_source"
    original=review(a)
    changed=review(b)
    assert original["status"]=="STORM_SOURCE_RESEARCH_MEASURED"
    assert changed["status"]=="STORM_SOURCE_RESEARCH_MEASURED"
    assert original["source_revision_sha256"]!=changed["source_revision_sha256"]
    assert "different_research_source" not in json.dumps(changed)
