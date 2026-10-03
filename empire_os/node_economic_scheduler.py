"""Evidence-backed economic scheduling for Empire Node Fabric.

This module selects a preferred node only from verified observations.
It grants no execution authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping

from empire_os.hybrid_compute import Route
from empire_os.node_registry import (
    NodeRegistry,
)


SCHEDULER_VERSION = "empire-node-economic-scheduler-v1"


@dataclass(frozen=True)
class NodePerformance:
    node_id: str

    quality: float | None = None
    reliability: float | None = None
    latency_ms: float | None = None
    marginal_cost_gbp: float | None = None

    verified_outcome_score: float | None = None

    matched_sample_count: int = 0

    benchmark_verified: bool = False
    economic_memory_verified: bool = False

    def __post_init__(self) -> None:
        for name in (
            "quality",
            "reliability",
            "verified_outcome_score",
        ):
            value = getattr(self, name)

            if value is not None and not 0 <= value <= 1:
                raise ValueError(
                    f"{name} must be within [0, 1]"
                )

        if (
            self.latency_ms is not None
            and self.latency_ms < 0
        ):
            raise ValueError(
                "latency_ms must be nonnegative"
            )

        if (
            self.marginal_cost_gbp is not None
            and self.marginal_cost_gbp < 0
        ):
            raise ValueError(
                "marginal_cost_gbp must be nonnegative"
            )

        if self.matched_sample_count < 0:
            raise ValueError(
                "matched_sample_count must be nonnegative"
            )


@dataclass(frozen=True)
class SchedulerPolicy:
    shadow_min_samples: int = 3
    production_min_samples: int = 25

    production_min_quality: float = 0.85
    production_min_reliability: float = 0.98

    max_latency_ms: float = 60_000.0

    quality_weight: float = 0.45
    reliability_weight: float = 0.25
    latency_weight: float = 0.12
    cost_weight: float = 0.08
    outcome_weight: float = 0.10


@dataclass(frozen=True)
class CandidateScore:
    node_id: str
    score: float | None

    evidence_complete: bool
    shadow_eligible: bool
    production_eligible: bool

    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class ScheduleDecision:
    route: Route
    capability: str

    candidate_scores: tuple[CandidateScore, ...]

    selected_node_id: str | None

    shadow_selection_available: bool
    production_selection_available: bool

    production_authority: bool
    execution_performed: bool

    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict:
        payload = asdict(self)

        payload["route"] = self.route.value

        return payload


def _latency_score(
    latency_ms: float,
    policy: SchedulerPolicy,
) -> float:
    if latency_ms <= 0:
        return 1.0

    return max(
        0.0,
        min(
            1.0,
            1.0
            - (
                latency_ms
                / policy.max_latency_ms
            ),
        ),
    )


def _cost_score(cost: float) -> float:
    # Diminishing score. Zero observed marginal API cost scores 1.
    # This does not claim total infrastructure cost is zero.
    return 1.0 / (1.0 + cost)


def _score(
    perf: NodePerformance,
    policy: SchedulerPolicy,
) -> CandidateScore:
    reasons: list[str] = []

    required = {
        "quality": perf.quality,
        "reliability": perf.reliability,
        "latency_ms": perf.latency_ms,
        "marginal_cost_gbp": perf.marginal_cost_gbp,
    }

    missing = [
        key
        for key, value in required.items()
        if value is None
    ]

    if missing:
        reasons.extend(
            f"missing_{key}"
            for key in missing
        )

    if not perf.benchmark_verified:
        reasons.append(
            "benchmark_not_verified"
        )

    evidence_complete = (
        not missing
        and perf.benchmark_verified
    )

    shadow_eligible = (
        evidence_complete
        and perf.matched_sample_count
        >= policy.shadow_min_samples
    )

    if (
        perf.matched_sample_count
        < policy.shadow_min_samples
    ):
        reasons.append(
            "insufficient_shadow_samples"
        )

    production_eligible = (
        shadow_eligible
        and perf.matched_sample_count
        >= policy.production_min_samples
        and perf.quality is not None
        and perf.quality
        >= policy.production_min_quality
        and perf.reliability is not None
        and perf.reliability
        >= policy.production_min_reliability
        and perf.economic_memory_verified
    )

    if (
        perf.matched_sample_count
        < policy.production_min_samples
    ):
        reasons.append(
            "insufficient_production_samples"
        )

    if (
        perf.quality is not None
        and perf.quality
        < policy.production_min_quality
    ):
        reasons.append(
            "quality_below_production_floor"
        )

    if (
        perf.reliability is not None
        and perf.reliability
        < policy.production_min_reliability
    ):
        reasons.append(
            "reliability_below_production_floor"
        )

    if not perf.economic_memory_verified:
        reasons.append(
            "economic_memory_not_verified"
        )

    if not evidence_complete:
        return CandidateScore(
            node_id=perf.node_id,
            score=None,
            evidence_complete=False,
            shadow_eligible=False,
            production_eligible=False,
            reason_codes=tuple(reasons),
        )

    assert perf.quality is not None
    assert perf.reliability is not None
    assert perf.latency_ms is not None
    assert perf.marginal_cost_gbp is not None

    outcome = (
        perf.verified_outcome_score
        if perf.verified_outcome_score
        is not None
        else 0.0
    )

    score = (
        perf.quality
        * policy.quality_weight
        + perf.reliability
        * policy.reliability_weight
        + _latency_score(
            perf.latency_ms,
            policy,
        )
        * policy.latency_weight
        + _cost_score(
            perf.marginal_cost_gbp
        )
        * policy.cost_weight
        + outcome
        * policy.outcome_weight
    )

    return CandidateScore(
        node_id=perf.node_id,
        score=round(score, 8),
        evidence_complete=True,
        shadow_eligible=shadow_eligible,
        production_eligible=production_eligible,
        reason_codes=tuple(reasons),
    )


def schedule(
    *,
    registry: NodeRegistry,
    capability: str,
    route: Route,
    performance: Mapping[
        str,
        NodePerformance,
    ],
    policy: SchedulerPolicy | None = None,
    tenant_id: str | None = None,
) -> ScheduleDecision:
    scheduler_policy = (
        policy or SchedulerPolicy()
    )

    candidates = registry.candidates(
        capability=capability,
        route=route,
        tenant_id=tenant_id,
    )

    if not candidates:
        return ScheduleDecision(
            route=route,
            capability=capability,
            candidate_scores=(),
            selected_node_id=None,
            shadow_selection_available=False,
            production_selection_available=False,
            production_authority=False,
            execution_performed=False,
            reason_codes=(
                "no_healthy_capability_node",
            ),
        )

    scores: list[CandidateScore] = []

    for node in candidates:
        perf = performance.get(
            node.node_id
        )

        if perf is None:
            scores.append(
                CandidateScore(
                    node_id=node.node_id,
                    score=None,
                    evidence_complete=False,
                    shadow_eligible=False,
                    production_eligible=False,
                    reason_codes=(
                        "no_performance_receipt",
                    ),
                )
            )
            continue

        if perf.node_id != node.node_id:
            raise ValueError(
                "performance/node identity mismatch"
            )

        scores.append(
            _score(
                perf,
                scheduler_policy,
            )
        )

    eligible = [
        row
        for row in scores
        if (
            row.shadow_eligible
            and row.score is not None
        )
    ]

    eligible.sort(
        key=lambda row: (
            row.score,
            row.node_id,
        ),
        reverse=True,
    )

    selected = (
        eligible[0].node_id
        if eligible
        else None
    )

    production_available = bool(
        selected
        and next(
            row
            for row in scores
            if row.node_id == selected
        ).production_eligible
    )

    reasons = []

    if selected is None:
        reasons.append(
            "insufficient_verified_scheduler_evidence"
        )
    else:
        reasons.append(
            "shadow_node_selected"
        )

    if not production_available:
        reasons.append(
            "production_promotion_gate_closed"
        )

    return ScheduleDecision(
        route=route,
        capability=capability,
        candidate_scores=tuple(scores),
        selected_node_id=selected,
        shadow_selection_available=(
            selected is not None
        ),
        production_selection_available=(
            production_available
        ),
        production_authority=False,
        execution_performed=False,
        reason_codes=tuple(reasons),
    )
