"""Forward-only value pilot experiment design and leakage guards."""
from datetime import timedelta
import json
import pytest

from test_predictive_customer_value_radar_bridge import inputs, NOW
from empire_os.predictive_customer_value_radar_bridge import review_customer_value_radar_bridge
from empire_os.predictive_customer_value_pilot_preflight import (
    review_prospective_customer_value_pilot,
)


def source():
    c,r=inputs()
    return review_customer_value_radar_bridge(c,r,as_of=NOW)


def design(snapshot=None):
    s=snapshot if snapshot is not None else source()
    card=s["research_cards"][0]
    return {
        "opportunity_key":card["opportunity_key"],
        "source_revision_fingerprint":card["source_revision_fingerprint"],
        "planned_start_at":(NOW+timedelta(days=2)).isoformat(),
        "planned_end_at":(NOW+timedelta(days=32)).isoformat(),
        "baseline_window_days":30,
        "planned_participants":100,
        "comparison_mode":"randomized_holdout",
        "primary_measure":card["proposed_primary_value_metric"],
        "commercial_measure":card["proposed_commercial_validation_metric"],
        "negative_outcomes_recorded":True,
        "refunds_and_cancellations_recorded":True,
        "consent_required":True,
        "original_forecast_must_precede_outcomes":True,
    }


def test_valid_value_experiment_preflight_is_not_forecast_or_customer_measurement():
    s=source()
    x=review_prospective_customer_value_pilot(s, design(s),as_of=NOW)
    assert x["status"]=="PROSPECTIVE_VALUE_PILOT_DESIGN_UNREGISTERED"
    assert x["original_research_revision_checked"] is True
    assert x["planned_horizon_days"]==30
    assert x["comparison_mode"]=="randomized_holdout"
    assert x["planned_participants_not_actual_enrollment"]==100
    assert x["customer_savings_verified"] is False
    assert x["real_cost_and_margin_authenticated"] is False
    assert x["causal_impact_claim_approved"] is False
    assert x["bias_and_sample_power_evaluated"] is False
    assert x["customer_consent_verified"] is False
    assert x["customer_outcomes_collected"] is False
    assert x["original_quant_forecast_registered"] is False
    assert x["original_forecast_probability"] is None
    assert x["model_calibration_performed"] is False
    assert x["prospective_design_durably_registered"] is False
    assert x["automatic_pilot_activation"] is False
    assert x["database_writes"] is False
    assert x["outbound_sent"] is False
    assert len(x["design_revision_sha256"])==64
    assert "secret" not in json.dumps(x)


@pytest.mark.parametrize("override",[
    {"comparison_mode":"MAGIC_CAUSAL_INFERENCE"},
    {"planned_participants":1},
    {"planned_participants":True},
    {"baseline_window_days":0},
    {"baseline_window_days":45.2},
    {"negative_outcomes_recorded":False},
    {"refunds_and_cancellations_recorded":False},
    {"consent_required":False},
    {"original_forecast_must_precede_outcomes":False},
    {"primary_measure":"claimed_roi"},
    {"commercial_measure":"search_clicks"},
    {"planned_start_at":(NOW-timedelta(days=1)).isoformat()},
    {"planned_end_at":(NOW+timedelta(days=95)).isoformat()},
    {"source_revision_fingerprint":"f"*64},
    {"opportunity_key":"market:roofing:little rock, ar"},
])
def test_bad_experiment_claim_timing_identity_or_missing_commitment_rejected(override):
    s=source();d=design(s);d.update(override)
    with pytest.raises(ValueError):
        review_prospective_customer_value_pilot(s,d,as_of=NOW)


def test_stale_bridge_and_duplicate_opportunity_key_are_not_trusted():
    s=source()
    d=design(s)
    assert review_prospective_customer_value_pilot(s,d,as_of=NOW)["original_research_revision_checked"] is True
    s["status"]="EVIDENCE_HOLD"
    with pytest.raises(ValueError):
        review_prospective_customer_value_pilot(s,d,as_of=NOW)


def test_design_fingerprint_changes_with_prospective_cohort_plan_only():
    s=source();d=design(s)
    a=review_prospective_customer_value_pilot(s,d,as_of=NOW)
    d["planned_participants"]=200
    b=review_prospective_customer_value_pilot(s,d,as_of=NOW)
    assert a["design_revision_sha256"] != b["design_revision_sha256"]
    assert a["model_calibration_performed"] is False
    assert b["model_calibration_performed"] is False


def test_observational_design_never_claims_causality():
    s=source()
    d=design(s)
    d["comparison_mode"]="observational_before_after"
    r=review_prospective_customer_value_pilot(s,d,as_of=NOW)
    assert r["comparison_mode"]=="observational_before_after"
    assert r["causal_impact_claim_approved"] is False
