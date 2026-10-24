"""Precision, accuracy and false-positive truth checks for PRIME shadow only."""
from copy import deepcopy
from datetime import datetime

import pytest

from empire_os.prime_prediction_quality import evaluate_prime_prediction_quality
from empire_os.prime_original_outcome_calibration import review_prime_outcome_calibration
from empire_os.predictive_revenue_prime_status import read_prime_founder_status
from test_authenticated_commercial_outcome_intelligence import NOW, TENANT, ORDER
from test_prime_original_outcome_calibration import valid_row


def score(ps, ys):
    return evaluate_prime_prediction_quality(ps, ys)


def test_binary_confusion_matrix_precision_recall_accuracy():
    row = score([.9,.8,.7,.1,.2,.3], [1,0,1,0,1,0])
    assert (row["true_positive"], row["false_positive"],
            row["true_negative"], row["false_negative"]) == (2,1,2,1)
    assert row["accuracy"] == .666667
    assert row["precision"] == .666667
    assert row["recall"] == .666667
    assert row["specificity"] == .666667
    assert row["f1_score"] == .666667
    assert row["balanced_accuracy"] == .666667
    assert row["positive_outcome_base_rate"] == .5
    assert row["majority_class_accuracy_baseline"] == .5
    assert row["accuracy_beats_majority_baseline"] is None
    assert row["research_threshold"] == .5
    assert row["sample_count"] == 6
    assert row["shadow_minimum_screening_threshold_met"] is False
    assert row["production_accuracy_verified"] is False
    assert row["model_promotion_authorized"] is False
    assert row["execution_authority"] == "none"
    assert row["brier_score"] is not None
    assert row["log_loss"] is not None
    assert row["expected_calibration_error"] is not None
    assert row["precision_wilson95_interval"][0] < row["precision"]
    assert row["precision_wilson95_interval"][1] > row["precision"]


def test_all_negative_accuracy_cannot_hide_no_positive_predictions():
    row = score([.01]*40, [0]*40)
    assert row["accuracy"] == 1.0
    assert row["majority_class_accuracy_baseline"] == 1.0
    assert row["precision"] is None
    assert row["recall"] is None
    assert row["balanced_accuracy"] is None
    assert row["false_positive"] == 0
    assert row["shadow_minimum_screening_threshold_met"] is True
    assert row["accuracy_beats_majority_baseline"] is None
    assert "SINGLE_OUTCOME_CLASS_CANNOT_ASSESS_DISCRIMINATION" in row["blockers"]
    assert row["production_accuracy_verified"] is False


def test_high_accuracy_does_not_mean_high_precision():
    row = score([.9,.9]+[.1]*48, [0,1]+[0]*48)
    assert row["accuracy"] == .98
    assert row["precision"] == .5
    assert row["true_positive"] == 1
    assert row["false_positive"] == 1
    assert row["majority_class_accuracy_baseline"] == .98
    assert row["accuracy_beats_majority_baseline"] is False


def test_recall_must_not_be_mistaken_for_precision():
    row = score([.9,.8,.7,.6], [1,0,0,0])
    assert row["recall"] == 1
    assert row["precision"] == .25
    assert row["accuracy"] == .25
    assert row["true_positive"] == 1 and row["false_positive"] == 3


def test_no_predictions_are_unknown_not_zero():
    row = score([], [])
    assert row["status"] == "NO_PAIRED_OUTCOMES"
    for name in ("precision","accuracy","recall","f1_score","brier_score",
                 "log_loss","expected_calibration_error"):
        assert row[name] is None
    assert row["source_provenance_authenticated_by_metric"] is False


@pytest.mark.parametrize("ps,ys", [
    ([float("nan")],[0]),
    ([float("inf")],[0]),
    ([float("-inf")],[1]),
    ([-.001],[1]),
    ([1.001],[1]),
    ([True],[1]),
    ([.5],[True]),
    ([.5],[2]),
    ([.2,.3],[1]),
    ([.2],[1,0]),
    ([.2]*51,[1]*51),
    ("0.5", [1]),
])
def test_nonfinite_injected_unpaired_or_invalid_inputs_fail_closed(ps,ys):
    with pytest.raises(ValueError):
        score(ps,ys)


def test_confusion_and_reliability_deterministic_and_no_source_rows():
    ps, ys = [.23,.71,.83,.42],[0,1,0,1]
    a,b = score(ps,ys),score(tuple(ps),tuple(ys))
    assert a == b
    assert "tenant_id" not in str(a)
    assert "outcome_ref" not in str(a)
    assert a["prospective_holdout_independently_verified"] is False
    assert a["source_provenance_authenticated_by_metric"] is False


def test_real_original_verified_learning_fixture_only_one_pair_is_unpromoted():
    row = valid_row()
    old = deepcopy(row)
    r = review_prime_outcome_calibration(
        owner_outcome_rows=[row],tenant_id=TENANT,as_of=NOW,
    )
    assert old == row
    q = r["shadow_prediction_quality"]
    assert r["shadow_brier_score"] == q["brier_score"] == .16
    assert q["precision"] == 1 and q["accuracy"] == 1
    assert q["precision_wilson95_interval"][0] < .5
    assert q["shadow_minimum_screening_threshold_met"] is False
    assert q["source_provenance_authenticated_by_metric"] is False
    assert r["calibration_cohort_sufficient"] is False
    assert r["statistical_model_calibration_verified"] is False
    assert r["training_authorized"] is False
    assert r["cash_receipts_or_revenue_verified_by_this_module"] is False
    assert ORDER not in str(q) and TENANT not in str(q)


def test_missing_original_prediction_does_not_manufacture_positive():
    row = valid_row()
    row["original_prediction"] = None
    r = review_prime_outcome_calibration(
        owner_outcome_rows=[row],tenant_id=TENANT,as_of=NOW,
    )
    assert r["shadow_prediction_quality"] is None
    assert r["shadow_prediction_pair_count"] == 0
    assert r["shadow_brier_score"] is None


def test_founder_only_returns_aggregate_accuracy_precision(tmp_path):
    r = read_prime_founder_status(
        repo_root=tmp_path, as_of=NOW, tenant_id=TENANT,
        original_owner_calibration_rows=[valid_row()],
    )
    assert r["original_outcome_shadow_accuracy"] == 1
    assert r["original_outcome_shadow_precision"] == 1
    assert r["original_outcome_shadow_accuracy_baseline"] == 1
    assert r["original_outcome_shadow_false_positives"] == 0
    assert r["original_outcome_shadow_false_negatives"] == 0
    assert r["original_outcome_shadow_pair_count"] == 1
    assert r["original_outcome_calibration_training_authorized"] is False
    assert "tenant_id" not in str(r)
    assert ORDER not in str(r)
    assert r["realized_revenue_cents"] is None


def test_production_founder_with_no_authenticated_cohort_reports_unknown(tmp_path):
    r = read_prime_founder_status(repo_root=tmp_path, as_of=NOW)
    assert r["original_outcome_shadow_accuracy"] is None
    assert r["original_outcome_shadow_precision"] is None
    assert r["original_outcome_shadow_accuracy_baseline"] is None
    assert r["original_outcome_shadow_false_positives"] is None
    assert r["original_outcome_shadow_false_negatives"] is None
