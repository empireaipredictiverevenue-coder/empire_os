"""Strict synthetic cohort audit: no fake calibration, sales or DB authentication."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from empire_os.flagship_forecast_population_audit import (
    MANIFEST_SCHEMA, review_forecast_population,
)
from test_verified_outcome_learning_continuity import memory as source_memory, TENANT

NOW = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)



def memory():
    # The original fixture builder timestamps snapshots with the current
    # real clock. Pin this artificial October 5 cohort to its fixture clock.
    result = source_memory()
    result["generated_at"] = NOW.isoformat()
    return result


def export(*records):
    return {
        "schema_version": MANIFEST_SCHEMA,
        "mode": "OBSERVE",
        "tenant_id": TENANT,
        "records": list(records),
    }


def original(**changes):
    sample = deepcopy(memory()["calibration_evidence"][0]["prediction"])
    sample.update(changes)
    return sample


def record(prediction=None, recorded="2026-10-01T12:05:00+00:00", readback="2026-10-01T12:06:00+00:00"):
    return {
        "prediction": prediction or original(),
        "registry_recorded_at": recorded,
        "reader_observed_at": readback,
    }


def test_missing_population_is_unknown_not_zero_or_accurate():
    report = review_forecast_population(memory(), tenant_id=TENANT, as_of=NOW)
    assert report["status"] == "FORECAST_UNIVERSE_NOT_SUPPLIED"
    assert report["supplied_forecast_count"] is None
    assert report["matched_terminal_win"] is None
    assert report["scientific_precision_claim_authorized"] is False
    assert report["verified_economic_memory_paired_reviews"] == 1


def test_unverified_pending_expired_and_verified_win_are_three_distinct_states():
    pending = original(
        prediction_ref="pending-1", opportunity_key="pending-op",
        predicted_at="2026-10-04T12:00:00+00:00",
        horizon_until="2026-10-08T12:00:00+00:00",
    )
    expired = original(
        prediction_ref="expired-1", opportunity_key="expired-op",
        predicted_at="2026-09-28T12:00:00+00:00",
        horizon_until="2026-10-03T12:00:00+00:00",
    )
    m = export(
        record(),
        record(pending, "2026-10-04T12:02:00+00:00", "2026-10-04T12:03:00+00:00"),
        record(expired, "2026-09-28T12:02:00+00:00", "2026-09-28T12:03:00+00:00"),
    )
    report = review_forecast_population(memory(), tenant_id=TENANT, as_of=NOW, manifest=m)
    assert report["supplied_forecast_count"] == 3
    assert report["matched_terminal_win"] == 1
    assert report["matched_terminal_loss"] == 0
    assert report["pending_before_horizon"] == 1
    assert report["horizon_elapsed_unverified"] == 1
    assert report["unmatched_memory_predictions"] == 0
    assert report["matured_unknowns_counted_as_losses"] is False
    assert report["complete_registered_forecast_denominator_verified"] is False
    assert report["manifest_is_authenticated_registry_readback"] is False
    assert report["scientific_precision_claim_authorized"] is False
    assert report["next_evidence_action"] == "RESOLVE_MATURED_UNKNOWN_OUTCOMES_WITH_ORIGINAL_EVIDENCE"


def test_empty_supplied_manifest_is_not_zero_real_forecasts():
    r = review_forecast_population(memory(), tenant_id=TENANT, as_of=NOW, manifest=export())
    assert r["unmatched_memory_predictions"] == 1
    assert r["supplied_forecast_count"] == 0
    assert r["complete_registered_forecast_denominator_verified"] is False
    assert r["next_evidence_action"] == "RECONCILE_ALL_ORIGINAL_FORECASTS_AND_OUTCOMES"


@pytest.mark.parametrize("bad", [
    lambda x: x.update(tenant_id="other"),
    lambda x: x["records"].append(deepcopy(x["records"][0])),
    lambda x: x["records"][0]["prediction"].update(tenant_id="other"),
    lambda x: x["records"][0]["prediction"].update(predicted_probability=float("nan")),
    lambda x: x["records"][0]["prediction"].update(predicted_probability=True),
    lambda x: x["records"][0]["prediction"].update(horizon_until="2026-09-30T00:00:00+00:00"),
    lambda x: x["records"][0].update(registry_recorded_at="2026-10-04T14:00:00+00:00"),
    lambda x: x["records"][0].update(reader_observed_at="2026-10-06T14:00:00+00:00"),
    lambda x: x["records"][0]["prediction"].update(predicted_at="2026-10-07T00:00:00+00:00"),
    lambda x: x["records"][0]["prediction"].update(evidence_refs=[]),
    lambda x: x["records"][0]["prediction"].update(irrelevant_source_claim=True),
])
def test_fail_closed_invalid_or_poisoned_manifest(bad):
    m = export(record())
    bad(m)
    with pytest.raises(ValueError):
        review_forecast_population(memory(), tenant_id=TENANT, as_of=NOW, manifest=m)


def test_memory_must_still_pass_original_outcome_validation():
    m = memory()
    m["calibration_evidence"][0]["predicted_value"] = .99
    with pytest.raises(ValueError):
        review_forecast_population(m, tenant_id=TENANT, as_of=NOW, manifest=export(record()))


def test_outcome_cannot_precede_supplied_registry_proof():
    with pytest.raises(ValueError, match="after terminal outcome"):
        review_forecast_population(
            memory(), tenant_id=TENANT, as_of=NOW,
            manifest=export(record(recorded="2026-10-05T10:00:00+00:00",
                                   readback="2026-10-05T10:01:00+00:00")),
        )


def test_global_access_to_tenant_data_is_forbidden():
    with pytest.raises(ValueError):
        review_forecast_population(memory(), tenant_id=None, as_of=NOW)
    with pytest.raises(ValueError):
        review_forecast_population(memory(), tenant_id="other", as_of=NOW)


def test_missing_registered_population_empty_memory_is_not_accuracy():
    empty = {
        "schema_version": "empire.economic_memory.v1", "mode": "OBSERVE",
        "execution_authority": "none", "promoted_learning": False,
        "tenant_id": None, "calibration_evidence": [],
        "verified_learning_feedback": [],
    }
    r = review_forecast_population(empty, tenant_id=None, as_of=NOW)
    assert r["verified_economic_memory_paired_reviews"] == 0
    assert r["supplied_forecast_count"] is None
    assert r["scientific_precision_claim_authorized"] is False
    assert r["automatic_model_calibration"] is False


def test_verified_negative_comes_only_from_original_commercial_outcome():
    """Use existing canonical fixture verification, not a forged zero label."""
    from test_verified_outcome_learning_continuity import (
        feedback, prediction, twin,
    )
    from empire_os.economic_memory import build_economic_memory_snapshot
    from empire_os.predictive_calibration import review_commercial_prediction

    source = twin()
    source["outcomes"]["history"][0]["conversion_outcome"] = "lost"
    source["commercial"]["payment_evidence"] = []
    source["commercial"]["fulfilment_orders"] = []
    f = feedback(source)
    assert f["verified_label"] == 0
    review = review_commercial_prediction(
        prediction=prediction(), feedback=f, tenant_id=TENANT, as_of=NOW,
    )
    m = build_economic_memory_snapshot(
        executive_evaluation={}, department_work=[],
        cortex_learning={"packets": [f["cortex_packet"]]},
        tenant_id=TENANT, verified_feedback=[f],
        calibration_reviews=[review], as_of=NOW,
    )
    m["generated_at"] = NOW.isoformat()
    report = review_forecast_population(
        m, tenant_id=TENANT, as_of=NOW, manifest=export(record()),
    )
    assert report["matched_terminal_win"] == 0
    assert report["matched_terminal_loss"] == 1
    assert report["horizon_elapsed_unverified"] == 0
    assert report["scientific_precision_claim_authorized"] is False


def test_future_or_unbounded_memory_must_not_enter_population_audit():
    m = memory()
    m["generated_at"] = (NOW + timedelta(seconds=1)).isoformat()
    with pytest.raises(ValueError, match="future economic memory"):
        review_forecast_population(m, tenant_id=TENANT, as_of=NOW)
    m = memory()
    m["verified_learning_feedback"] = [{}] * 501
    with pytest.raises(ValueError, match="bounded"):
        review_forecast_population(m, tenant_id=TENANT, as_of=NOW)
