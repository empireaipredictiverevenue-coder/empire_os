"""Evidence-first commercial opportunity assessment for EmpireOS."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class OpportunityCandidate:
    opportunity_key: str
    niche: str
    trigger: str
    offer_key: str
    distribution_path: str
    evidence_refs: tuple[str, ...]
    buyer_intent: float
    demand: float
    urgency: float
    margin_potential: float
    distribution_strength: float
    data_advantage: float
    fulfilment_readiness: float
    build_complexity: float

    def validate(self) -> None:
        if not self.opportunity_key.strip():
            raise ValueError("opportunity_key required")
        if not self.niche.strip() or not self.trigger.strip():
            raise ValueError("niche and trigger required")
        for name in (
            "buyer_intent", "demand", "urgency", "margin_potential",
            "distribution_strength", "data_advantage",
            "fulfilment_readiness", "build_complexity",
        ):
            value = float(getattr(self, name))
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")


@dataclass(frozen=True)
class OpportunityAssessment:
    opportunity_key: str
    score: float
    decision: str
    next_event: str
    evidence_count: int
    reasons: tuple[str, ...]
    revenue_verified: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_opportunity(candidate: OpportunityCandidate) -> OpportunityAssessment:
    candidate.validate()
    evidence_count = len(tuple(dict.fromkeys(candidate.evidence_refs)))
    score = (
        candidate.buyer_intent * 25
        + candidate.demand * 20
        + candidate.urgency * 15
        + candidate.margin_potential * 10
        + candidate.distribution_strength * 10
        + candidate.data_advantage * 10
        + candidate.fulfilment_readiness * 10
        - candidate.build_complexity * 10
    )
    score = round(max(0.0, min(100.0, score)), 2)

    reasons: list[str] = []
    if evidence_count < 2:
        reasons.append("insufficient_independent_evidence")
    if not candidate.offer_key.strip():
        reasons.append("offer_not_attached")
    if not candidate.distribution_path.strip():
        reasons.append("distribution_not_attached")
    if candidate.buyer_intent < 0.45:
        reasons.append("buyer_intent_not_proven")
    if candidate.demand < 0.35:
        reasons.append("demand_not_proven")
    if candidate.fulfilment_readiness < 0.35:
        reasons.append("fulfilment_not_ready")

    required_ready = not any(reason in reasons for reason in (
        "insufficient_independent_evidence",
        "offer_not_attached",
        "distribution_not_attached",
        "buyer_intent_not_proven",
        "demand_not_proven",
        "fulfilment_not_ready",
    ))

    if required_ready and score >= 65:
        decision = "build_smallest_useful_mvp"
        next_event = "mvp_build_requested"
    elif score < 35 and candidate.buyer_intent < 0.30:
        decision = "park"
        next_event = "opportunity_parked"
    else:
        decision = "research"
        next_event = "opportunity_research_requested"

    return OpportunityAssessment(
        opportunity_key=candidate.opportunity_key,
        score=score,
        decision=decision,
        next_event=next_event,
        evidence_count=evidence_count,
        reasons=tuple(reasons),
        revenue_verified=False,
    )
