"""Phase 12 Demand Genesis outcome freshness and cost-efficiency review."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from empire_os.demand_outcome import DemandOutcomeEvidence, review_demand_outcome


@dataclass(frozen=True)
class DemandOutcomeEvidenceReview:
    plan_id: str
    success_metric: str
    outcome_age_seconds: float
    freshness: str
    outcome_after_plan: bool
    outcome_available: bool
    absolute_change: float | None
    observed_cost_cents: int | None
    cost_per_incremental_unit_cents: float | None
    cost_efficiency_available: bool
    review_ready: bool
    blockers: tuple[str, ...]
    execution_authority: str = "none"
    publishing_enabled: bool = False
    outbound_enabled: bool = False
    ad_spend_enabled: bool = False
    provider_activation_enabled: bool = False

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


def review_demand_outcome_evidence(
    evidence: DemandOutcomeEvidence,
    *,
    plan_registered_at: str,
    now: datetime,
    max_age_seconds: int = 604800,
) -> DemandOutcomeEvidenceReview:
    if now.tzinfo is None:
        raise ValueError("now must include timezone")
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")

    outcome = review_demand_outcome(evidence)
    plan_time = _parse_timestamp(
        plan_registered_at,
        name="plan_registered_at",
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

    after_plan = outcome_time > plan_time
    blockers: list[str] = []
    if freshness != "fresh":
        blockers.append(f"outcome_evidence_{freshness}")
    if not after_plan:
        blockers.append("outcome_not_after_registered_plan")
    if not outcome.outcome_available:
        blockers.extend(outcome.blockers)
    if evidence.observed_cost_cents is None:
        blockers.append("observed_cost_evidence_missing")


    cost_per_increment = None
    efficiency_available = False
    if (
        outcome.outcome_available
        and outcome.absolute_change is not None
        and outcome.absolute_change > 0
        and evidence.observed_cost_cents is not None
    ):
        cost_per_increment = round(
            evidence.observed_cost_cents / outcome.absolute_change,
            4,
        )
        efficiency_available = True
    elif (
        outcome.outcome_available
        and outcome.absolute_change is not None
        and outcome.absolute_change <= 0
    ):
        blockers.append("positive_incremental_outcome_not_observed")

    ordered = tuple(sorted(set(blockers)))
    return DemandOutcomeEvidenceReview(
        plan_id=evidence.plan_id,
        success_metric=evidence.success_metric,
        outcome_age_seconds=round(age, 3),
        freshness=freshness,
        outcome_after_plan=after_plan,
        outcome_available=outcome.outcome_available,
        absolute_change=outcome.absolute_change,
        observed_cost_cents=evidence.observed_cost_cents,
        cost_per_incremental_unit_cents=cost_per_increment,
        cost_efficiency_available=efficiency_available,
        review_ready=not ordered,
        blockers=ordered,
    )
