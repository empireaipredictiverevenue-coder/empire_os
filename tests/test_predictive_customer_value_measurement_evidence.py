"""Synthetic customer value before/after and control-arm custody."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import json
import pytest

from test_predictive_customer_value_commerce_evidence import (
    NOW, LATER, TENANT, original,
)
from empire_os.predictive_customer_value_measurement_evidence import (
    review_customer_value_measurement_evidence,
)


def receipt(pilot, *, cohort="a", unique="a1", arm="treatment",
            phase="baseline", value=200, days=1):
    return {
        "tenant_ref_sha256":TENANT,
        "pilot_design_sha256":pilot["design_revision_sha256"],
        "cohort_slot_sha256":sha256(cohort.encode()).hexdigest(),
        "source_measurement_sha256":sha256(unique.encode()).hexdigest(),
        "source_owner":"customer_success_analytics",
        "reuse_scope":"INTERNAL_AGGREGATE_RESEARCH_ONLY",
        "evidence_status":"SOURCE_OWNER_REPORTED_UNAUTHENTICATED",
        "arm":arm, "phase":phase,
        "metric":pilot["primary_value_measure"],
        "unit":"basis_points",
        "value":value,
        "observed_at":(NOW+timedelta(days=days)).isoformat(),
        "evidence_available_at":(NOW+timedelta(days=days,minutes=5)).isoformat(),
    }


def review(records, pilot=None, as_of=LATER):
    return review_customer_value_measurement_evidence(
        pilot if pilot is not None else original(),
        records,tenant_ref_sha256=TENANT,as_of=as_of,
    )


def test_pre_post_treatment_and_control_claims_not_measured_customer_gain():
    p=original()
    records=[
        receipt(p,cohort="a",unique="a1",arm="treatment",phase="baseline",value=200),
        receipt(p,cohort="a",unique="a2",arm="treatment",phase="followup",value=400,days=12),
        receipt(p,cohort="b",unique="b1",arm="control",phase="baseline",value=150),
        receipt(p,cohort="b",unique="b2",arm="control",phase="followup",value=200,days=12),
    ]
    result=review(records,pilot=p)
    assert result["status"]=="CUSTOMER_VALUE_MEASUREMENT_CLAIMS_RECONCILED_UNAUTHENTICATED"
    assert result["source_measurement_receipts"]==4
    assert result["claimed_distinct_cohort_slots"]==2
    assert result["complete_treatment_pairs"]==1
    assert result["complete_control_pairs"]==1
    assert result["unpaired_slots"]==0
    assert result["claimed_treatment_signed_change_unverified"]==200
    assert result["claimed_control_signed_change_unverified"]==50
    assert result["claimed_between_arm_delta_unverified_not_causal"]==150
    assert result["unit"]=="basis_points"
    for field in ("source_owner_authenticated","cohort_identity_or_consent_verified",
                  "baseline_was_prospectively_registered","original_quant_forecast_registered",
                  "negative_customer_outcomes_completely_observed","time_or_cash_saved_verified",
                  "causal_lift_verified","customer_value_calibration_ready",
                  "economic_memory_outcome_write"):
        assert result[field] is False
    assert TENANT not in json.dumps(result)
    assert "a1" not in json.dumps(result)


def test_single_arm_missing_control_or_incomplete_pairs_have_no_causal_estimate():
    p=original()
    solo=[
        receipt(p,unique="a1",phase="baseline"),
        receipt(p,unique="a2",phase="followup",value=220,days=12),
        receipt(p,unique="b1",cohort="b",phase="baseline",arm="control"),
    ]
    r=review(solo,pilot=p)
    assert r["complete_treatment_pairs"]==1
    assert r["complete_control_pairs"]==0
    assert r["unpaired_slots"]==1
    assert r["claimed_between_arm_delta_unverified_not_causal"] is None


def test_zero_receipts_are_unknown_not_zero_savings():
    x=review([])
    assert x["source_measurement_receipts"]==0
    assert x["claimed_treatment_signed_change_unverified"] is None
    assert x["claimed_between_arm_delta_unverified_not_causal"] is None
    assert x["time_or_cash_saved_verified"] is False


@pytest.mark.parametrize("patch", [
    {"tenant_ref_sha256":sha256(b"other").hexdigest()},
    {"pilot_design_sha256":sha256(b"other").hexdigest()},
    {"cohort_slot_sha256":"PII"},
    {"source_measurement_sha256":"PII"},
    {"source_owner":"unauthorized_app"},
    {"reuse_scope":"UNRESTRICTED_PURCHASE_HISTORY"},
    {"evidence_status":"SIGNED_AND_VERIFIED"},
    {"arm":"neither"},
    {"phase":"post_hoc"},
    {"metric":"unapproved_metric"},
    {"unit":"minor_cash"},
    {"value":True},
    {"value":-1},
    {"value":20000},
    {"value":float("nan")},
    {"value":10**100},
    {"observed_at":(NOW+timedelta(days=31)).isoformat()},
    {"evidence_available_at":(NOW+timedelta(days=50)).isoformat()},
])
def test_invalid_original_measurement_or_excess_authority_is_rejected(patch):
    p=original()
    r=receipt(p)
    r.update(patch)
    with pytest.raises(ValueError):
        review([r],pilot=p)


def test_duplicated_measurement_and_changed_assignment_blocked():
    p=original()
    a=receipt(p)
    with pytest.raises(ValueError):
        review([a,deepcopy(a)],pilot=p)
    second=receipt(p,unique="a2",phase="followup",arm="control",days=12)
    with pytest.raises(ValueError):
        review([a,second],pilot=p)


def test_baseline_after_trial_start_and_followup_before_start_rejected():
    p=original()
    with pytest.raises(ValueError):
        review([receipt(p,days=12)],pilot=p)
    with pytest.raises(ValueError):
        review([receipt(p,phase="followup",days=1)],pilot=p)


def test_randomized_holdout_is_not_causal_assurance():
    p=original()
    rows=[
        receipt(p,unique="a1",phase="baseline"),
        receipt(p,unique="a2",phase="followup",days=15,value=200),
        receipt(p,unique="b1",cohort="b",arm="control",phase="baseline",value=300),
        receipt(p,unique="b2",cohort="b",arm="control",phase="followup",days=15,value=290),
    ]
    assert review(rows,pilot=p)["causal_lift_verified"] is False


def test_future_value_results_cannot_be_trained_before_available():
    p=original()
    rec=receipt(p,unique="a2",phase="followup",days=12)
    with pytest.raises(ValueError):
        review([rec],pilot=p,as_of=NOW+timedelta(days=5))
