"""Phase 11 causal-review conclusion packets from verified experiment analysis."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from empire_os.experiment_analysis import ExperimentAnalysis


@dataclass(frozen=True)
class CausalConclusionPacket:
    conclusion_key: str
    experiment_key: str
    metric: str
    control_count: int
    treatment_count: int
    control_mean: float
    treatment_mean: float
    absolute_lift: float
    relative_lift: float | None
    effect_direction: str
    assignment_integrity_verified: bool
    exposure_integrity_verified: bool
    outcome_window_closed: bool
    evidence_refs: tuple[str, ...]
    causal_review_eligible: bool = True
    statistical_significance_available: bool = False
    interpretation: str = "eligible_for_causal_review_not_significance_claim"
    execution_authority: str = "none"
    traffic_mutation: bool = False
    rollout_enabled: bool = False
    pricing_mutation: bool = False

    def validate(self) -> None:
        if not self.conclusion_key.strip():
            raise ValueError("conclusion_key required")
        if not self.experiment_key.strip() or not self.metric.strip():
            raise ValueError("experiment_key and metric required")
        if self.control_count < 1 or self.treatment_count < 1:
            raise ValueError("conclusion requires observed arm samples")
        if self.control_mean < 0 or self.treatment_mean < 0:
            raise ValueError("conclusion means must be nonnegative")
        if not (
            self.assignment_integrity_verified
            and self.exposure_integrity_verified
            and self.outcome_window_closed
            and self.causal_review_eligible
        ):
            raise ValueError("experiment not eligible for causal conclusion")
        if self.statistical_significance_available:
            raise ValueError(
                "statistical significance is unavailable in this conclusion slice"
            )
        if self.effect_direction not in {
            "positive_observed_lift",
            "negative_observed_lift",
            "no_observed_lift",
        }:
            raise ValueError("unsupported conclusion effect direction")
        if not self.evidence_refs:
            raise ValueError("causal conclusion requires evidence")
        if self.execution_authority != "none":
            raise ValueError("causal conclusion cannot grant execution")
        if self.traffic_mutation or self.rollout_enabled or self.pricing_mutation:
            raise ValueError("causal conclusion cannot mutate experiment traffic")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        data = asdict(self)
        data["evidence_refs"] = list(self.evidence_refs)
        return data


@dataclass(frozen=True)
class ExperimentConclusionRecord:
    conclusion: CausalConclusionPacket
    evidence: Mapping[str, Any]

    def validate(self) -> None:
        self.conclusion.validate()
        if not isinstance(self.evidence, Mapping) or not self.evidence:
            raise ValueError("causal conclusion registry requires evidence")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "conclusion": self.conclusion.as_dict(),
            "evidence": dict(self.evidence),
            "mode": "OBSERVE",
            "execution_authority": "none",
            "traffic_mutation": False,
            "rollout_enabled": False,
            "pricing_mutation": False,
        }


def build_causal_conclusion(
    *,
    conclusion_key: str,
    analysis: ExperimentAnalysis,
) -> CausalConclusionPacket:
    estimate = analysis.estimate
    if not analysis.causal_claim_eligible or not estimate.available:
        raise ValueError("experiment not eligible for causal conclusion")
    if (
        estimate.control_mean is None
        or estimate.treatment_mean is None
        or estimate.absolute_lift is None
    ):
        raise ValueError("causal conclusion estimate is incomplete")

    if estimate.absolute_lift > 0:
        direction = "positive_observed_lift"
    elif estimate.absolute_lift < 0:
        direction = "negative_observed_lift"
    else:
        direction = "no_observed_lift"

    packet = CausalConclusionPacket(
        conclusion_key=str(conclusion_key or "").strip(),
        experiment_key=analysis.experiment_key,
        metric=analysis.metric,
        control_count=estimate.control_count,
        treatment_count=estimate.treatment_count,
        control_mean=estimate.control_mean,
        treatment_mean=estimate.treatment_mean,
        absolute_lift=estimate.absolute_lift,
        relative_lift=estimate.relative_lift,
        effect_direction=direction,
        assignment_integrity_verified=analysis.assignment_integrity_verified,
        exposure_integrity_verified=analysis.exposure_integrity_verified,
        outcome_window_closed=analysis.outcome_window_closed,
        evidence_refs=analysis.evidence_refs,
    )
    packet.validate()
    return packet
