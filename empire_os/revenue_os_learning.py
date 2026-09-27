"""Phase 18 learning-readiness gate for observed Revenue OS outcomes."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from empire_os.revenue_os_feedback import (
    RevenueOsLearningFeedback,
    RevenueOsOutcomeEvidence,
    review_revenue_os_outcome,
)


@dataclass(frozen=True)
class RevenueOsLearningReadiness:
    packet_key: str
    learning_ready: bool
    outcome_age_seconds: float | None
    feedback: RevenueOsLearningFeedback
    blockers: tuple[str, ...]
    mode: str = "OBSERVE"
    side_effects: str = "none"
    execution_authority: str = "none"
    model_weight_mutation: bool = False
    capital_reallocation: bool = False
    spend_execution: bool = False
    outreach_execution: bool = False
    payment_execution: bool = False
    allocation_execution: bool = False
    deployment_execution: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["feedback"] = self.feedback.as_dict()
        return data


def _parse_timestamp(value: str, *, label: str) -> datetime:
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


def assess_revenue_os_learning(
    *,
    evidence: RevenueOsOutcomeEvidence,
    packet_created_at: str,
    now: datetime,
    max_age_seconds: int = 86400,
) -> RevenueOsLearningReadiness:
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")
    if now.tzinfo is None:
        raise ValueError("now must include timezone")

    feedback = review_revenue_os_outcome(evidence)
    current = now.astimezone(timezone.utc)
    packet_time = _parse_timestamp(
        packet_created_at,
        label="packet_created_at",
    )
    outcome_time = _parse_timestamp(
        evidence.observed_at,
        label="observed_at",
    )

    blockers = list(feedback.blockers)
    age = (current - outcome_time).total_seconds()
    if outcome_time <= packet_time:
        blockers.append("outcome_not_after_decision_packet")
    if age < -60:
        blockers.append("outcome_evidence_from_future")
    elif age > max_age_seconds:
        blockers.append("outcome_evidence_stale")

    ordered = tuple(sorted(set(blockers)))
    return RevenueOsLearningReadiness(
        packet_key=evidence.packet_key,
        learning_ready=not ordered,
        outcome_age_seconds=round(age, 3),
        feedback=feedback,
        blockers=ordered,
    )
