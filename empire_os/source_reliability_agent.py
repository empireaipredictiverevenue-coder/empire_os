"""Data Quality & Source Reliability Agent.

Observed-evidence source health and bounded scheduling recommendations. It does
not fabricate economics, delete canonical evidence, or permanently retire
sources.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.source_intelligence import classify_runtime_health


@dataclass(frozen=True)
class SourceReliabilityState:
    source_id: str
    runtime_health: str
    runs: int
    accepted: int
    errors: int
    prospects: int
    qualified: int
    conversations: int
    duplicates: int
    stale_records: int
    complete_records: int
    identity_resolved: int
    verified_revenue_cents: int | None
    cost_cents: int | None
    acceptance_rate: float | None
    qualification_rate: float | None
    conversation_rate: float | None
    duplicate_rate: float | None
    freshness_rate: float | None
    completeness_rate: float | None
    identity_resolution_rate: float | None
    scheduling_weight: float
    recommendation: str
    recommendation_reason: str
    permanent_retirement_allowed: bool = False
    canonical_delete_performed: bool = False
    external_action_performed: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(max(0, numerator) / denominator, 4)


def build_source_reliability_state(
    *,
    source_id: str,
    runs: int,
    accepted: int,
    errors: int,
    prospects: int = 0,
    qualified: int = 0,
    conversations: int = 0,
    duplicates: int = 0,
    stale_records: int = 0,
    complete_records: int = 0,
    identity_resolved: int = 0,
    consecutive_empty_runs: int = 0,
    verified_revenue_cents: int | None = None,
    cost_cents: int | None = None,
) -> SourceReliabilityState:
    sid = str(source_id or "").strip()
    if not sid:
        raise ValueError("source_id required")

    runs = max(0, int(runs))
    accepted = max(0, int(accepted))
    errors = max(0, int(errors))
    prospects = max(0, int(prospects))
    qualified = max(0, int(qualified))
    conversations = max(0, int(conversations))
    duplicates = max(0, int(duplicates))
    stale_records = max(0, int(stale_records))
    complete_records = max(0, int(complete_records))
    identity_resolved = max(0, int(identity_resolved))

    health = classify_runtime_health(
        runs=runs,
        accepted=accepted,
        errors=errors,
        consecutive_empty_runs=consecutive_empty_runs,
    )

    total_seen = accepted + duplicates
    fresh = max(0, accepted - stale_records)

    recommendation = "continue_exploration"
    reason = "insufficient_downstream_evidence_for_reweighting"
    weight = 1.0

    qualification_rate = _rate(qualified, prospects)
    conversation_rate = _rate(conversations, qualified)

    if health == "QUARANTINED":
        weight = 0.1
        recommendation = "recovery_only"
        reason = "runtime_health_quarantined"
    elif health == "DEGRADED":
        weight = 0.5
        recommendation = "reduce_sampling_and_open_recovery"
        reason = "runtime_health_degraded"
    elif (
        runs >= 3
        and prospects > 0
        and qualification_rate is not None
        and qualification_rate < 0.05
    ):
        weight = 0.75
        recommendation = "reduce_sampling_review"
        reason = "observed_low_qualification_yield"
    elif (
        runs >= 3
        and qualified >= 5
        and conversation_rate is not None
        and conversation_rate >= 0.20
    ):
        weight = 1.15
        recommendation = "increase_bounded_sampling"
        reason = "observed_downstream_conversation_yield"

    return SourceReliabilityState(
        source_id=sid,
        runtime_health=health,
        runs=runs,
        accepted=accepted,
        errors=errors,
        prospects=prospects,
        qualified=qualified,
        conversations=conversations,
        duplicates=duplicates,
        stale_records=stale_records,
        complete_records=complete_records,
        identity_resolved=identity_resolved,
        verified_revenue_cents=(
            None
            if verified_revenue_cents is None
            else max(0, int(verified_revenue_cents))
        ),
        cost_cents=(
            None if cost_cents is None else max(0, int(cost_cents))
        ),
        acceptance_rate=_rate(accepted, runs),
        qualification_rate=qualification_rate,
        conversation_rate=conversation_rate,
        duplicate_rate=_rate(duplicates, total_seen),
        freshness_rate=_rate(fresh, accepted),
        completeness_rate=_rate(complete_records, accepted),
        identity_resolution_rate=_rate(identity_resolved, accepted),
        scheduling_weight=weight,
        recommendation=recommendation,
        recommendation_reason=reason,
    )


def source_reliability_agent_status() -> dict[str, Any]:
    return {
        "schema_version": "empire.source-reliability-agent.v1",
        "observed_inputs_only": True,
        "unknown_economics_remain_unknown": True,
        "permanent_retirement_allowed": False,
        "canonical_delete_authority": False,
        "scheduler_recommendation_only": True,
        "execution_authority": "none",
    }
