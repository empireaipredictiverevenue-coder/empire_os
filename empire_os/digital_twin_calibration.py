"""Phase 14 calibration readiness for Digital Twin realization feedback."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from empire_os.digital_twin_realization import ScenarioRealizationReview


@dataclass(frozen=True)
class DigitalTwinCalibrationReadiness:
    scenario_id: str
    ready_for_model_review: bool
    outcome_age_seconds: float
    blockers: tuple[str, ...]
    realization: ScenarioRealizationReview
    simulation_only: bool = True
    execution_authority: str = "none"
    model_weight_mutation: bool = False
    capital_execution: bool = False
    campaign_execution: bool = False
    pricing_execution: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["realization"] = self.realization.as_dict()
        return data


def _parse(value: str, *, label: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"{label} required")
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include timezone")
    return parsed.astimezone(timezone.utc)



def assess_digital_twin_calibration(
    *,
    realization: ScenarioRealizationReview,
    baseline_observed_at: str,
    outcome_observed_at: str,
    now: datetime,
    max_age_seconds: int = 86400,
) -> DigitalTwinCalibrationReadiness:
    if now.tzinfo is None:
        raise ValueError("now must include timezone")
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")

    baseline_time = _parse(
        baseline_observed_at,
        label="baseline_observed_at",
    )
    outcome_time = _parse(
        outcome_observed_at,
        label="outcome_observed_at",
    )
    current = now.astimezone(timezone.utc)
    age = (current - outcome_time).total_seconds()
    blockers = list(realization.blockers)

    if outcome_time <= baseline_time:
        blockers.append("outcome_not_after_baseline")
    if age < -60:
        blockers.append("outcome_evidence_from_future")
    elif age > max_age_seconds:
        blockers.append("outcome_evidence_stale")
    if not realization.revenue_comparison_available:
        blockers.append("recognized_revenue_comparison_unavailable")

    ordered = tuple(sorted(set(blockers)))
    return DigitalTwinCalibrationReadiness(
        scenario_id=realization.scenario_id,
        ready_for_model_review=not ordered,
        outcome_age_seconds=round(age, 3),
        blockers=ordered,
        realization=realization,
    )
