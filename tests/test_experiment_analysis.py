import pytest

from empire_os.experiment_analysis import analyze_observed_experiment


def test_insufficient_samples_cannot_make_causal_claim():
    analysis = analyze_observed_experiment(
        experiment_key="exp-1",
        metric="qualified_conversion",
        control_values=[0, 1, 0],
        treatment_values=[1, 1, 0],
        evidence_refs=("experiment:exp-1",),
        assignment_integrity_verified=True,
        exposure_integrity_verified=True,
        outcome_window_closed=True,
        minimum_per_arm=5,
    )
    assert analysis.estimate.available is False
    assert analysis.causal_claim_eligible is False
    assert analysis.interpretation == "insufficient_observed_samples"
    assert analysis.execution_authority == "none"


def test_observed_lift_without_integrity_is_not_causal():
    analysis = analyze_observed_experiment(
        experiment_key="exp-2",
        metric="revenue_per_subject",
        control_values=[10, 10, 10, 10, 10],
        treatment_values=[12, 12, 12, 12, 12],
        evidence_refs=("experiment:exp-2",),
        assignment_integrity_verified=True,
        exposure_integrity_verified=False,
        outcome_window_closed=True,
    )
    assert analysis.estimate.available is True
    assert analysis.estimate.relative_lift == 0.2
    assert analysis.causal_claim_eligible is False
    assert analysis.interpretation == "observed_lift_only_integrity_not_verified"


def test_fully_verified_observed_experiment_is_eligible_for_review():
    analysis = analyze_observed_experiment(
        experiment_key="exp-3",
        metric="revenue_per_subject",
        control_values=[10, 10, 10, 10, 10],
        treatment_values=[12, 12, 12, 12, 12],
        evidence_refs=("assignment:a", "exposure:b", "outcome:c"),
        assignment_integrity_verified=True,
        exposure_integrity_verified=True,
        outcome_window_closed=True,
    )
    assert analysis.causal_claim_eligible is True
    assert analysis.interpretation == "causal_estimate_eligible_for_review"
    assert analysis.execution_authority == "none"


def test_analysis_requires_evidence():
    with pytest.raises(ValueError, match="requires evidence"):
        analyze_observed_experiment(
            experiment_key="exp-4",
            metric="conversion",
            control_values=[0] * 5,
            treatment_values=[1] * 5,
            evidence_refs=(),
        )


def test_negative_outcomes_fail_closed():
    with pytest.raises(ValueError, match="nonnegative"):
        analyze_observed_experiment(
            experiment_key="exp-5",
            metric="conversion",
            control_values=[0, 0, 0, 0, -1],
            treatment_values=[1, 1, 1, 1, 1],
            evidence_refs=("experiment:exp-5",),
        )
