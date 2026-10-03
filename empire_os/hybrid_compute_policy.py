"""Evidence-backed policy for Empire Hybrid Compute.

This layer converts verified benchmark observations into routing
recommendations. It does not execute models, modify ModelRouter, mutate the
registry, grant commercial authority or promote models.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping


POLICY_VERSION = "empire-hybrid-compute-policy-v1"


@dataclass(frozen=True)
class LocalCandidateEvidence:
    candidate_id: str
    provider: str
    model: str

    quality: float
    reliability: float
    latency_ms: float

    sample_count: int
    benchmark_verified: bool


@dataclass(frozen=True)
class ProviderObservation:
    model_id: str
    provider: str

    status: str

    successful_calls: int
    failed_calls: int

    hard_block_observed: bool
    transient_failure_observed: bool

    reasons: tuple[str, ...]


@dataclass(frozen=True)
class RoutingRecommendation:
    quality_floor: float
    latency_ceiling_ms: float | None

    selected_candidate_id: str | None
    selected_provider: str | None
    selected_model: str | None

    measured_quality: float | None
    measured_reliability: float | None
    measured_latency_ms: float | None

    candidate_count: int

    economic_ready: bool

    route_applied: bool
    can_execute: bool
    production_authority: bool

    reason_codes: tuple[str, ...]


def _finite_float(
    value: Any,
) -> float | None:
    if isinstance(value, bool):
        return None

    if not isinstance(
        value,
        (int, float),
    ):
        return None

    value = float(value)

    if value < 0:
        return None

    return value


def load_local_evidence(
    path: str | Path,
) -> tuple[LocalCandidateEvidence, ...]:
    payload = json.loads(
        Path(path).read_text()
    )

    if payload.get("complete") is not True:
        raise ValueError(
            "local escalation evidence incomplete"
        )

    if (
        payload.get(
            "production_authority"
        )
        is not False
    ):
        raise ValueError(
            "unexpected production authority"
        )

    reports = payload.get(
        "reports"
    )

    if not isinstance(
        reports,
        Mapping,
    ):
        raise ValueError(
            "missing reports"
        )

    candidates = []

    for candidate_id, report in (
        reports.items()
    ):
        if not isinstance(
            report,
            Mapping,
        ):
            continue

        quality = _finite_float(
            report.get(
                "mean_coverage"
            )
        )

        reliability = _finite_float(
            report.get(
                "reliability"
            )
        )

        latency = _finite_float(
            report.get(
                "mean_latency_ms"
            )
        )

        sample_count = int(
            report.get(
                "sample_count"
            )
            or 0
        )

        if (
            quality is None
            or reliability is None
            or latency is None
        ):
            continue

        candidates.append(
            LocalCandidateEvidence(
                candidate_id=str(
                    candidate_id
                ),
                provider=str(
                    report.get(
                        "provider"
                    )
                    or "unknown"
                ),
                model=str(
                    report.get(
                        "model"
                    )
                    or "unknown"
                ),
                quality=quality,
                reliability=reliability,
                latency_ms=latency,
                sample_count=sample_count,
                benchmark_verified=(
                    report.get(
                        "benchmark_verified"
                    )
                    is True
                ),
            )
        )

    return tuple(candidates)


def derive_provider_observations(
    path: str | Path,
) -> tuple[ProviderObservation, ...]:
    """Interpret benchmark failures without creating canonical health state."""

    payload = json.loads(
        Path(path).read_text()
    )

    runs = payload.get(
        "runs"
    ) or []

    grouped: dict[
        tuple[str, str],
        list[Mapping[str, Any]],
    ] = {}

    for row in runs:
        if (
            row.get("lane")
            != "canonical_current"
        ):
            continue

        candidate = (
            row.get("candidate")
            or {}
        )

        model_id = str(
            candidate.get(
                "model_id"
            )
            or "unknown"
        )

        provider = str(
            candidate.get(
                "provider"
            )
            or "unknown"
        )

        grouped.setdefault(
            (
                model_id,
                provider,
            ),
            [],
        ).append(row)

    observations = []

    for (
        model_id,
        provider,
    ), rows in grouped.items():
        successes = sum(
            1
            for row in rows
            if row.get("ok") is True
        )

        failures = (
            len(rows)
            - successes
        )

        failure_text = " ".join(
            str(
                row.get(
                    "failure"
                )
                or ""
            ).lower()
            for row in rows
        )

        hard_block = any(
            marker in failure_text
            for marker in (
                "freetiererror",
                "zen_failed",
                "http 403",
                "permission denied",
                "unauthorized",
                "forbidden",
            )
        )

        transient = any(
            marker in failure_text
            for marker in (
                "503",
                "service unavailable",
                "timeout",
                "temporarily unavailable",
            )
        )

        reasons = []

        if hard_block:
            status = "blocked_observed"
            reasons.append(
                "hard_execution_failure_observed"
            )

        elif (
            successes
            and failures
        ):
            status = "degraded_observed"
            reasons.append(
                "mixed_execution_results"
            )

        elif transient:
            status = "degraded_observed"
            reasons.append(
                "transient_failure_observed"
            )

        elif (
            failures
            and not successes
        ):
            status = "unhealthy_observed"
            reasons.append(
                "all_observed_calls_failed"
            )

        elif successes:
            status = "healthy_observed"
            reasons.append(
                "successful_execution_observed"
            )

        else:
            status = "unknown"
            reasons.append(
                "no_execution_evidence"
            )

        if transient:
            reasons.append(
                "transient_provider_failure"
            )

        observations.append(
            ProviderObservation(
                model_id=model_id,
                provider=provider,
                status=status,
                successful_calls=successes,
                failed_calls=failures,
                hard_block_observed=hard_block,
                transient_failure_observed=transient,
                reasons=tuple(reasons),
            )
        )

    return tuple(observations)


def recommend_local(
    candidates: tuple[
        LocalCandidateEvidence,
        ...,
    ],
    *,
    quality_floor: float,
    latency_ceiling_ms: (
        float | None
    ) = None,
    minimum_samples: int = 5,
    minimum_reliability: float = 1.0,
) -> RoutingRecommendation:
    if not 0 <= quality_floor <= 1:
        raise ValueError(
            "quality_floor must be within [0, 1]"
        )

    reasons: list[str] = []

    verified = [
        candidate
        for candidate in candidates
        if (
            candidate.benchmark_verified
            and candidate.sample_count
            >= minimum_samples
            and candidate.reliability
            >= minimum_reliability
        )
    ]

    if not verified:
        return RoutingRecommendation(
            quality_floor=quality_floor,
            latency_ceiling_ms=(
                latency_ceiling_ms
            ),
            selected_candidate_id=None,
            selected_provider=None,
            selected_model=None,
            measured_quality=None,
            measured_reliability=None,
            measured_latency_ms=None,
            candidate_count=0,
            economic_ready=False,
            route_applied=False,
            can_execute=False,
            production_authority=False,
            reason_codes=(
                "no_verified_local_candidate",
            ),
        )

    eligible = [
        candidate
        for candidate in verified
        if candidate.quality
        >= quality_floor
    ]

    if latency_ceiling_ms is not None:
        eligible = [
            candidate
            for candidate in eligible
            if candidate.latency_ms
            <= latency_ceiling_ms
        ]

    if not eligible:
        reasons.append(
            "no_local_candidate_meets_constraints"
        )

        return RoutingRecommendation(
            quality_floor=quality_floor,
            latency_ceiling_ms=(
                latency_ceiling_ms
            ),
            selected_candidate_id=None,
            selected_provider=None,
            selected_model=None,
            measured_quality=None,
            measured_reliability=None,
            measured_latency_ms=None,
            candidate_count=len(
                verified
            ),
            economic_ready=False,
            route_applied=False,
            can_execute=False,
            production_authority=False,
            reason_codes=tuple(
                reasons
            ),
        )

    # Use observed performance rather than model size.
    #
    # First satisfy the requested quality/reliability constraints;
    # among models that satisfy them, prefer the lowest measured latency.
    #
    # Economic optimality remains UNKNOWN until resource/energy/concurrency
    # cost evidence exists.
    selected = min(
        eligible,
        key=lambda candidate: (
            candidate.latency_ms,
            -candidate.quality,
            candidate.candidate_id,
        ),
    )

    reasons.extend((
        "verified_local_candidate_available",
        "selected_by_quality_floor_then_latency",
        "economic_cost_evidence_pending",
        "shadow_recommendation_only",
    ))

    return RoutingRecommendation(
        quality_floor=quality_floor,
        latency_ceiling_ms=(
            latency_ceiling_ms
        ),
        selected_candidate_id=(
            selected.candidate_id
        ),
        selected_provider=(
            selected.provider
        ),
        selected_model=(
            selected.model
        ),
        measured_quality=(
            selected.quality
        ),
        measured_reliability=(
            selected.reliability
        ),
        measured_latency_ms=(
            selected.latency_ms
        ),
        candidate_count=len(
            verified
        ),

        # We do not yet have measured total local compute economics.
        economic_ready=False,

        # Critical authority invariant.
        route_applied=False,
        can_execute=False,
        production_authority=False,
        reason_codes=tuple(
            reasons
        ),
    )
