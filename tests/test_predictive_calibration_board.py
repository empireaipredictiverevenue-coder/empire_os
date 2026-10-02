from empire_os.predictive_calibration import ForecastCalibrationReview
from empire_os.predictive_calibration_board import (
    VerifiedCalibrationMetrics,
    build_predictive_calibration_board,
)


def review(*, ready=True, absolute=10.0, relative=0.1, bias="under_predicted", ref="actual:1"):
    return ForecastCalibrationReview(
        metric="revenue",
        target_date="2026-10-01",
        actual_date="2026-10-01",
        predicted_value=100.0,
        actual_value=110.0,
        signed_error=10.0 if ready else None,
        absolute_error=absolute if ready else None,
        relative_error=relative if ready else None,
        bias=bias if ready else "unknown",
        calibration_ready=ready,
        blockers=() if ready else ("forecast_not_available_for_calibration",),
        evidence_refs=(ref,),
    )


def test_board_computes_error_metrics_only_from_ready_reviews():
    board = build_predictive_calibration_board([
        review(absolute=10.0, relative=0.1, ref="actual:1"),
        review(absolute=20.0, relative=-0.2, bias="over_predicted", ref="actual:2"),
        review(ready=False, ref="actual:blocked"),
    ])

    assert board.review_count == 3
    assert board.ready_review_count == 2
    assert board.verified_cohort_size == 2
    assert board.mean_absolute_error == 15.0
    assert board.mean_relative_error == -0.05
    assert board.bias_counts == (("over_predicted", 1), ("under_predicted", 1))
    assert board.brier_score is None
    assert board.interval_coverage is None
    assert board.drift_score is None
    assert board.evidence_refs == ("actual:1", "actual:2")
    assert board.blockers == ()


def test_probability_interval_and_drift_metrics_require_explicit_verified_evidence():
    metrics = VerifiedCalibrationMetrics(
        cohort_size=25,
        evidence_refs=("verified-cohort:25",),
        brier_score=0.12,
        interval_coverage=0.92,
        drift_score=0.08,
    )
    board = build_predictive_calibration_board([review()], verified_metrics=metrics)

    assert board.verified_cohort_size == 25
    assert board.brier_score == 0.12
    assert board.interval_coverage == 0.92
    assert board.drift_score == 0.08
    assert "verified-cohort:25" in board.evidence_refs


def test_empty_verified_cohort_fails_closed_without_fabricated_metrics():
    board = build_predictive_calibration_board([review(ready=False)])

    assert board.ready_review_count == 0
    assert board.mean_absolute_error is None
    assert board.mean_relative_error is None
    assert board.brier_score is None
    assert "verified_outcome_cohort_insufficient" in board.blockers


def test_board_has_no_execution_or_mutation_authority():
    board = build_predictive_calibration_board([review()])

    assert board.mode == "OBSERVE"
    assert board.execution_authority == "none"
    assert board.model_weight_mutation is False
    assert board.forecast_mutation is False
    assert board.capital_mutation is False
    assert board.pricing_mutation is False
    assert board.commercial_execution is False
    assert board.accounting_mutation is False
    assert board.creates_actual_revenue is False


def test_verified_metrics_validate_ranges_and_evidence():
    bad = [
        VerifiedCalibrationMetrics(1, (), brier_score=0.1),
        VerifiedCalibrationMetrics(1, ("e",), brier_score=1.1),
        VerifiedCalibrationMetrics(1, ("e",), interval_coverage=-0.1),
        VerifiedCalibrationMetrics(1, ("e",), drift_score=-1),
    ]
    for item in bad:
        try:
            build_predictive_calibration_board([review()], verified_metrics=item)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid verified metrics must fail closed")
