"""Phase 11 freshness gate for causal conclusion evidence."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from empire_os.experiment_conclusion import CausalConclusionPacket


@dataclass(frozen=True)
class ExperimentConclusionFreshness:
    conclusion_key: str
    fresh_for_operator_review: bool
    evidence_age_seconds: float
    blockers: tuple[str, ...]
    mode: str = "OBSERVE"
    execution_authority: str = "none"
    traffic_mutation: bool = False
    rollout_enabled: bool = False
    pricing_mutation: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


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


def assess_conclusion_freshness(
    *,
    conclusion: CausalConclusionPacket,
    experiment_observed_at: str,
    outcome_window_closed_at: str,
    now: datetime,
    max_age_seconds: int = 86400,
) -> ExperimentConclusionFreshness:
    conclusion.validate()
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")
    if now.tzinfo is None:
        raise ValueError("now must include timezone")

    current = now.astimezone(timezone.utc)
    experiment_time = _parse(
        experiment_observed_at,
        label="experiment_observed_at",
    )
    closed_time = _parse(
        outcome_window_closed_at,
        label="outcome_window_closed_at",
    )
    blockers: list[str] = []

    if closed_time < experiment_time:
        blockers.append("outcome_window_closed_before_experiment_observation")

    age = (current - closed_time).total_seconds()
    if age < -60:
        blockers.append("outcome_window_evidence_from_future")
    elif age > max_age_seconds:
        blockers.append("outcome_window_evidence_stale")

    ordered = tuple(sorted(set(blockers)))
    return ExperimentConclusionFreshness(
        conclusion_key=conclusion.conclusion_key,
        fresh_for_operator_review=not ordered,
        evidence_age_seconds=round(age, 3),
        blockers=ordered,
    )
