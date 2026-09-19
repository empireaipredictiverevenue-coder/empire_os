"""Read-only observed experiment analysis for Phase 11."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from empire_os.experiment_engine import (
    IncrementalityEstimate,
    estimate_incrementality,
)


@dataclass(frozen=True)
class ExperimentAnalysis:
    experiment_key: str
    metric: str
    estimate: IncrementalityEstimate
    assignment_integrity_verified: bool
    exposure_integrity_verified: bool
    outcome_window_closed: bool
    evidence_refs: tuple[str, ...]
    causal_claim_eligible: bool
    interpretation: str
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return {
            "experiment_key": self.experiment_key,
            "metric": self.metric,
            "estimate": self.estimate.as_dict(),
            "assignment_integrity_verified": self.assignment_integrity_verified,
            "exposure_integrity_verified": self.exposure_integrity_verified,
            "outcome_window_closed": self.outcome_window_closed,
            "evidence_refs": list(self.evidence_refs),
            "causal_claim_eligible": self.causal_claim_eligible,
            "interpretation": self.interpretation,
            "execution_authority": self.execution_authority,
        }


def analyze_observed_experiment(
    *,
    experiment_key: str,
    metric: str,
    control_values: list[float],
    treatment_values: list[float],
    evidence_refs: tuple[str, ...],
    assignment_integrity_verified: bool = False,
    exposure_integrity_verified: bool = False,
    outcome_window_closed: bool = False,
    minimum_per_arm: int = 5,
) -> ExperimentAnalysis:
    key = str(experiment_key or "").strip()
    metric_name = str(metric or "").strip()
    if not key or not metric_name:
        raise ValueError("experiment_key and metric are required")
    refs = tuple(str(ref).strip() for ref in evidence_refs if str(ref).strip())
    if not refs:
        raise ValueError("experiment analysis requires evidence")

    estimate = estimate_incrementality(
        control_values=control_values,
        treatment_values=treatment_values,
        minimum_per_arm=minimum_per_arm,
    )
    integrity = (
        assignment_integrity_verified
        and exposure_integrity_verified
        and outcome_window_closed
    )
    eligible = bool(estimate.available and integrity)

    if not estimate.available:
        interpretation = "insufficient_observed_samples"
    elif not integrity:
        interpretation = "observed_lift_only_integrity_not_verified"
    else:
        interpretation = "causal_estimate_eligible_for_review"

    return ExperimentAnalysis(
        experiment_key=key,
        metric=metric_name,
        estimate=estimate,
        assignment_integrity_verified=assignment_integrity_verified,
        exposure_integrity_verified=exposure_integrity_verified,
        outcome_window_closed=outcome_window_closed,
        evidence_refs=refs,
        causal_claim_eligible=eligible,
        interpretation=interpretation,
    )
