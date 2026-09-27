"""Phase 6 evidence-only A2A commercial attribution review."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class A2ACommercialAttributionEvidence:
    intent_id: str
    negotiation_id: str
    agent_id: str
    manual_handoff_ref: str | None = None
    fulfilment_order_ref: str | None = None
    payment_request_ref: str | None = None
    verified_payment_ref: str | None = None
    commercial_outcome_ref: str | None = None
    recognized_revenue_ref: str | None = None
    realized_gp_cents: int | None = None

    def validate(self) -> None:
        for label, value in (
            ("intent_id", self.intent_id),
            ("negotiation_id", self.negotiation_id),
            ("agent_id", self.agent_id),
        ):
            if not str(value or "").strip():
                raise ValueError(f"{label} required")


@dataclass(frozen=True)
class A2ACommercialAttributionReview:
    intent_id: str
    negotiation_id: str
    agent_id: str
    revenue_attribution_ready: bool
    gross_profit_attribution_ready: bool
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    realized_gp_cents: int | None
    mode: str = "OBSERVE"
    execution_authority: str = "none"
    payment_authority: bool = False
    allocation_authority: bool = False
    revenue_mutation: bool = False
    accounting_mutation: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def review_a2a_commercial_attribution(
    evidence: A2ACommercialAttributionEvidence,
) -> A2ACommercialAttributionReview:
    """Require the full observed commercial chain before A2A revenue attribution."""
    evidence.validate()
    blockers: list[str] = []
    refs: list[str] = []

    required = (
        ("manual_handoff", evidence.manual_handoff_ref),
        ("fulfilment_order", evidence.fulfilment_order_ref),
        ("payment_request", evidence.payment_request_ref),
        ("verified_payment", evidence.verified_payment_ref),
        ("commercial_outcome", evidence.commercial_outcome_ref),
        ("recognized_revenue", evidence.recognized_revenue_ref),
    )
    for label, value in required:
        ref = str(value or "").strip()
        if ref:
            refs.append(ref)
        else:
            blockers.append(f"{label}_evidence_missing")

    revenue_ready = not blockers
    gp_ready = revenue_ready and evidence.realized_gp_cents is not None
    if revenue_ready and evidence.realized_gp_cents is None:
        blockers.append("realized_gross_profit_evidence_missing")

    return A2ACommercialAttributionReview(
        intent_id=evidence.intent_id,
        negotiation_id=evidence.negotiation_id,
        agent_id=evidence.agent_id,
        revenue_attribution_ready=revenue_ready,
        gross_profit_attribution_ready=gp_ready,
        blockers=tuple(sorted(set(blockers))),
        evidence_refs=tuple(dict.fromkeys(refs)),
        realized_gp_cents=evidence.realized_gp_cents,
    )
