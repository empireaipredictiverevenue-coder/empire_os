"""Phase 11 evidence-only experiment commercial-impact review."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.experiment_conclusion import CausalConclusionPacket
from empire_os.experiment_conclusion_freshness import (
    ExperimentConclusionFreshness,
)


@dataclass(frozen=True)
class ExperimentBusinessImpactEvidence:
    conclusion_key: str
    commercial_outcome_ref: str | None = None
    recognized_revenue_ref: str | None = None
    realized_gp_ref: str | None = None
    realized_gp_cents: int | None = None

    def validate(self) -> None:
        if not self.conclusion_key.strip():
            raise ValueError("conclusion_key required")


@dataclass(frozen=True)
class ExperimentBusinessImpactReview:
    conclusion_key: str
    experiment_key: str
    metric: str
    effect_direction: str
    outcome_link_ready: bool
    commercial_impact_ready: bool
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    realized_gp_cents: int | None
    statistical_significance_available: bool = False
    execution_authority: str = "none"
    traffic_mutation: bool = False
    rollout_enabled: bool = False
    pricing_mutation: bool = False
    revenue_mutation: bool = False
    accounting_mutation: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def review_experiment_business_impact(
    *,
    conclusion: CausalConclusionPacket,
    freshness: ExperimentConclusionFreshness,
    evidence: ExperimentBusinessImpactEvidence,
) -> ExperimentBusinessImpactReview:
    conclusion.validate()
    evidence.validate()
    if conclusion.conclusion_key != freshness.conclusion_key:
        raise ValueError("conclusion/freshness key mismatch")
    if conclusion.conclusion_key != evidence.conclusion_key:
        raise ValueError("conclusion/business-impact key mismatch")

    blockers = list(freshness.blockers)
    refs = list(conclusion.evidence_refs)
    outcome_ref = str(evidence.commercial_outcome_ref or "").strip()
    if outcome_ref:
        refs.append(outcome_ref)
    else:
        blockers.append("commercial_outcome_evidence_missing")
    if not freshness.fresh_for_operator_review:
        blockers.append("causal_conclusion_not_fresh_for_operator_review")

    outcome_ready = not blockers
    commercial_blockers = list(blockers)

    revenue_ref = str(evidence.recognized_revenue_ref or "").strip()
    if revenue_ref:
        refs.append(revenue_ref)
    else:
        commercial_blockers.append("recognized_revenue_evidence_missing")

    gp_ref = str(evidence.realized_gp_ref or "").strip()
    if gp_ref:
        refs.append(gp_ref)
    else:
        commercial_blockers.append("realized_gross_profit_evidence_missing")
    if evidence.realized_gp_cents is None:
        commercial_blockers.append("realized_gross_profit_value_unknown")

    ordered = tuple(sorted(set(commercial_blockers)))
    return ExperimentBusinessImpactReview(
        conclusion_key=conclusion.conclusion_key,
        experiment_key=conclusion.experiment_key,
        metric=conclusion.metric,
        effect_direction=conclusion.effect_direction,
        outcome_link_ready=outcome_ready,
        commercial_impact_ready=not ordered,
        blockers=ordered,
        evidence_refs=tuple(dict.fromkeys(refs)),
        realized_gp_cents=evidence.realized_gp_cents,
    )
