"""Read-only Predictive Cloud calibration board.

Summarises verified forecast/actual reviews without mutating models or inventing
unsupported probability/drift metrics.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean
from typing import Any, Iterable

from empire_os.predictive_calibration import ForecastCalibrationReview


@dataclass(frozen=True)
class VerifiedCalibrationMetrics:
    cohort_size: int
    evidence_refs: tuple[str, ...]
    brier_score: float | None = None
    interval_coverage: float | None = None
    drift_score: float | None = None

    def validate(self) -> None:
        if self.cohort_size <= 0:
            raise ValueError("verified cohort_size must be positive")
        if not self.evidence_refs:
            raise ValueError("verified calibration metrics require evidence")
        if self.brier_score is not None and not 0 <= self.brier_score <= 1:
            raise ValueError("brier_score must be between 0 and 1")
        if (
            self.interval_coverage is not None
            and not 0 <= self.interval_coverage <= 1
        ):
            raise ValueError("interval_coverage must be between 0 and 1")
        if self.drift_score is not None and self.drift_score < 0:
            raise ValueError("drift_score must be nonnegative")


@dataclass(frozen=True)
class PredictiveCalibrationBoard:
    review_count: int
    ready_review_count: int
    verified_cohort_size: int
    mean_absolute_error: float | None
    mean_relative_error: float | None
    brier_score: float | None
    interval_coverage: float | None
    drift_score: float | None
    bias_counts: tuple[tuple[str, int], ...]
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    mode: str = "OBSERVE"
    execution_authority: str = "none"
    model_weight_mutation: bool = False
    forecast_mutation: bool = False
    capital_mutation: bool = False
    pricing_mutation: bool = False
    commercial_execution: bool = False
    accounting_mutation: bool = False
    creates_actual_revenue: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_predictive_calibration_board(
    reviews: Iterable[ForecastCalibrationReview],
    *,
    verified_metrics: VerifiedCalibrationMetrics | None = None,
) -> PredictiveCalibrationBoard:
    rows = tuple(reviews)
    ready = tuple(row for row in rows if row.calibration_ready)
    blockers: list[str] = []

    absolute_errors = [
        float(row.absolute_error)
        for row in ready
        if row.absolute_error is not None
    ]
    relative_errors = [
        float(row.relative_error)
        for row in ready
        if row.relative_error is not None
    ]

    if not ready:
        blockers.append("verified_outcome_cohort_insufficient")

    evidence: list[str] = []
    for row in ready:
        evidence.extend(
            str(ref).strip()
            for ref in row.evidence_refs
            if str(ref).strip()
        )

    brier = interval = drift = None
    cohort_size = len(ready)
    if verified_metrics is not None:
        verified_metrics.validate()
        cohort_size = verified_metrics.cohort_size
        brier = verified_metrics.brier_score
        interval = verified_metrics.interval_coverage
        drift = verified_metrics.drift_score
        evidence.extend(verified_metrics.evidence_refs)

    counts: dict[str, int] = {}
    for row in ready:
        counts[row.bias] = counts.get(row.bias, 0) + 1

    return PredictiveCalibrationBoard(
        review_count=len(rows),
        ready_review_count=len(ready),
        verified_cohort_size=cohort_size,
        mean_absolute_error=(
            round(mean(absolute_errors), 6) if absolute_errors else None
        ),
        mean_relative_error=(
            round(mean(relative_errors), 6) if relative_errors else None
        ),
        brier_score=brier,
        interval_coverage=interval,
        drift_score=drift,
        bias_counts=tuple(sorted(counts.items())),
        blockers=tuple(sorted(set(blockers))),
        evidence_refs=tuple(dict.fromkeys(evidence)),
    )
