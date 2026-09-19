import pytest

from empire_os.experiment_engine import (
    ExperimentDefinition,
    estimate_incrementality,
    plan_assignment,
)


def definition():
    return ExperimentDefinition(
        experiment_id="exp-1",
        hypothesis="New landing message increases qualified conversion.",
        metric="qualified_conversion",
        control_variant="control",
        treatment_variants=("treatment_a", "treatment_b"),
        holdout_fraction=0.2,
        minimum_sample_size=20,
    )


def test_assignment_is_deterministic_for_same_subject():
    a = plan_assignment(definition(), subject_key="prospect-123")
    b = plan_assignment(definition(), subject_key="prospect-123")
    assert a == b
    assert a.arm in {"control", "treatment_a", "treatment_b"}


def test_assignment_plan_has_no_execution_side_effect():
    planned = plan_assignment(definition(), subject_key="prospect-456")
    assert planned.assignment_kind in {"holdout_control", "treatment"}
    assert 0 <= planned.deterministic_bucket <= 9999


def test_invalid_holdout_is_rejected():
    bad = ExperimentDefinition(
        experiment_id="exp-1",
        hypothesis="h",
        metric="m",
        control_variant="control",
        treatment_variants=("a",),
        holdout_fraction=1.0,
        minimum_sample_size=5,
    )
    with pytest.raises(ValueError, match="holdout_fraction"):
        bad.validate()


def test_incrementality_requires_enough_observed_samples():
    estimate = estimate_incrementality(
        control_values=[1, 1, 0],
        treatment_values=[1, 1, 1],
        minimum_per_arm=5,
    )
    assert estimate.available is False
    assert estimate.reason == "insufficient_arm_samples"


def test_incrementality_reports_observed_lift_only():
    estimate = estimate_incrementality(
        control_values=[10, 10, 10, 10, 10],
        treatment_values=[12, 12, 12, 12, 12],
        minimum_per_arm=5,
    )
    assert estimate.available is True
    assert estimate.control_mean == 10.0
    assert estimate.treatment_mean == 12.0
    assert estimate.absolute_lift == 2.0
    assert estimate.relative_lift == 0.2
