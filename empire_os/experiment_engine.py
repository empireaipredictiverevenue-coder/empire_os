"""Phase 11 experiment and causal-evidence foundation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any


@dataclass(frozen=True)
class ExperimentDefinition:
    experiment_id: str
    hypothesis: str
    metric: str
    control_variant: str
    treatment_variants: tuple[str, ...]
    holdout_fraction: float
    minimum_sample_size: int

    def validate(self) -> None:
        if not self.experiment_id.strip():
            raise ValueError("experiment_id required")
        if not self.hypothesis.strip() or not self.metric.strip():
            raise ValueError("hypothesis and metric required")
        if not self.control_variant.strip():
            raise ValueError("control_variant required")
        if not self.treatment_variants:
            raise ValueError("at least one treatment variant required")
        if self.control_variant in self.treatment_variants:
            raise ValueError("control cannot also be a treatment")
        if not 0 <= self.holdout_fraction < 1:
            raise ValueError("holdout_fraction must be between 0 and 1")
        if self.minimum_sample_size < 1:
            raise ValueError("minimum_sample_size must be positive")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class PlannedAssignment:
    experiment_id: str
    subject_key: str
    arm: str
    assignment_kind: str
    deterministic_bucket: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
def plan_assignment(
    definition: ExperimentDefinition,
    *,
    subject_key: str,
) -> PlannedAssignment:
    definition.validate()
    subject = str(subject_key or "").strip()
    if not subject:
        raise ValueError("subject_key required")

    digest = sha256(
        f"{definition.experiment_id}:{subject}".encode("utf-8")
    ).hexdigest()
    bucket = int(digest[:8], 16) % 10_000
    holdout_cutoff = int(definition.holdout_fraction * 10_000)

    if bucket < holdout_cutoff:
        return PlannedAssignment(
            experiment_id=definition.experiment_id,
            subject_key=subject,
            arm=definition.control_variant,
            assignment_kind="holdout_control",
            deterministic_bucket=bucket,
        )

    treatments = definition.treatment_variants
    treatment_bucket = bucket - holdout_cutoff
    arm = treatments[treatment_bucket % len(treatments)]
    return PlannedAssignment(
        experiment_id=definition.experiment_id,
        subject_key=subject,
        arm=arm,
        assignment_kind="treatment",
        deterministic_bucket=bucket,
    )


@dataclass(frozen=True)
class IncrementalityEstimate:
    available: bool
    control_count: int
    treatment_count: int
    control_mean: float | None
    treatment_mean: float | None
    absolute_lift: float | None
    relative_lift: float | None
    reason: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def estimate_incrementality(
    *,
    control_values: list[float],
    treatment_values: list[float],
    minimum_per_arm: int = 5,
) -> IncrementalityEstimate:
    control = [float(value) for value in control_values]
    treatment = [float(value) for value in treatment_values]
    if any(value < 0 for value in control + treatment):
        raise ValueError("experiment outcomes must be nonnegative")
    minimum = max(int(minimum_per_arm), 1)
    if len(control) < minimum or len(treatment) < minimum:
        return IncrementalityEstimate(
            available=False,
            control_count=len(control),
            treatment_count=len(treatment),
            control_mean=None,
            treatment_mean=None,
            absolute_lift=None,
            relative_lift=None,
            reason="insufficient_arm_samples",
        )

    control_mean = sum(control) / len(control)
    treatment_mean = sum(treatment) / len(treatment)
    absolute = treatment_mean - control_mean
    relative = None if control_mean == 0 else absolute / control_mean

    return IncrementalityEstimate(
        available=True,
        control_count=len(control),
        treatment_count=len(treatment),
        control_mean=round(control_mean, 4),
        treatment_mean=round(treatment_mean, 4),
        absolute_lift=round(absolute, 4),
        relative_lift=(round(relative, 4) if relative is not None else None),
        reason=None,
    )
