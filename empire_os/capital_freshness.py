"""Phase 15 capital outcome freshness and recommendation calibration."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from empire_os.capital_outcome import CapitalOutcomeEvidence, review_capital_outcome


@dataclass(frozen=True)
class CapitalOutcomeCalibration:
    candidate_id: str
    outcome_age_seconds: float
    freshness: str
    outcome_after_recommendation: bool
    outcome_available: bool
    expected_return_multiple: float
    realized_return_multiple: float | None
    return_multiple_error: float | None
    realized_gross_profit_cents: int | None
    calibration_available: bool
    blockers: tuple[str, ...]
    recommendation_only: bool = True
    execution_authority: str = "none"
    funds_movement: bool = False
    budget_mutation: bool = False
    recommendation_mutation: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_timestamp(value: str, *, name: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"{name} required")
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{name} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include timezone")
    return parsed.astimezone(timezone.utc)


def review_capital_outcome_calibration(
    evidence: CapitalOutcomeEvidence,
    *,
    recommendation_recorded_at: str,
    now: datetime,
    max_age_seconds: int = 604800,
) -> CapitalOutcomeCalibration:
    if now.tzinfo is None:
        raise ValueError("now must include timezone")
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")

    outcome = review_capital_outcome(evidence)
    recommendation_time = _parse_timestamp(
        recommendation_recorded_at,
        name="recommendation_recorded_at",
    )
    outcome_time = _parse_timestamp(
        evidence.observed_at,
        name="outcome_observed_at",
    )
    clock = now.astimezone(timezone.utc)
    age = (clock - outcome_time).total_seconds()
    if age < -60:
        freshness = "future"
    elif age > max_age_seconds:
        freshness = "stale"
    else:
        freshness = "fresh"

    after_recommendation = outcome_time > recommendation_time
    blockers: list[str] = []
    if freshness != "fresh":
        blockers.append(f"outcome_evidence_{freshness}")
    if not after_recommendation:
        blockers.append("outcome_not_after_recommendation")
    if not outcome.outcome_available:
        blockers.extend(outcome.blockers)

    expected_multiple = (
        evidence.expected_return_cents / evidence.required_capital_cents
    )
    realized_multiple = outcome.realized_return_multiple
    error = None
    if realized_multiple is not None:
        error = round(realized_multiple - expected_multiple, 4)

    ordered = tuple(sorted(set(blockers)))
    calibration_available = (
        not ordered and realized_multiple is not None
    )
    return CapitalOutcomeCalibration(
        candidate_id=evidence.candidate_id,
        outcome_age_seconds=round(age, 3),
        freshness=freshness,
        outcome_after_recommendation=after_recommendation,
        outcome_available=outcome.outcome_available,
        expected_return_multiple=round(expected_multiple, 4),
        realized_return_multiple=realized_multiple,
        return_multiple_error=error,
        realized_gross_profit_cents=outcome.realized_gross_profit_cents,
        calibration_available=calibration_available,
        blockers=ordered,
    )
