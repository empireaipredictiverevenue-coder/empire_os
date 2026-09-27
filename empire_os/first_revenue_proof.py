"""Phase 3 first-revenue proof readiness."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class FirstRevenueEvidence:
    buyer_identity_verified: bool
    commercial_terms_verified: bool
    human_approval_recorded: bool
    outbound_intent_approved: bool
    send_evidence_verified: bool
    delivery_evidence_verified: bool
    agreement_evidence_verified: bool
    usdt_bsc_payment_verified: bool
    fulfilment_delivery_verified: bool
    outcome_evidence_verified: bool
    revenue_recognized: bool
    evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        if not self.evidence_refs:
            raise ValueError("first revenue proof requires evidence refs")


@dataclass(frozen=True)
class FirstRevenueReadiness:
    ready_for_outbound: bool
    ready_for_payment_acceptance: bool
    ready_for_fulfilment: bool
    ready_for_outcome_recognition: bool
    first_revenue_proven: bool
    blockers: tuple[str, ...]
    execution_authority: str = "none"
    side_effects: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_first_revenue_readiness(
    evidence: FirstRevenueEvidence,
) -> FirstRevenueReadiness:
    evidence.validate()

    blockers: list[str] = []
    checks = (
        ("buyer_identity_not_verified", evidence.buyer_identity_verified),
        ("commercial_terms_not_verified", evidence.commercial_terms_verified),
        ("human_approval_missing", evidence.human_approval_recorded),
        ("outbound_intent_not_approved", evidence.outbound_intent_approved),
        ("send_evidence_missing", evidence.send_evidence_verified),
        ("delivery_evidence_missing", evidence.delivery_evidence_verified),
        ("agreement_evidence_missing", evidence.agreement_evidence_verified),
        ("usdt_bsc_payment_not_verified", evidence.usdt_bsc_payment_verified),
        (
            "fulfilment_delivery_not_verified",
            evidence.fulfilment_delivery_verified,
        ),
        ("outcome_evidence_not_verified", evidence.outcome_evidence_verified),
        ("revenue_not_recognized", evidence.revenue_recognized),
    )
    for name, ok in checks:
        if not ok:
            blockers.append(name)

    outbound_ready = all((
        evidence.buyer_identity_verified,
        evidence.commercial_terms_verified,
        evidence.human_approval_recorded,
        evidence.outbound_intent_approved,
    ))
    payment_ready = all((
        outbound_ready,
        evidence.send_evidence_verified,
        evidence.delivery_evidence_verified,
        evidence.agreement_evidence_verified,
    ))
    fulfilment_ready = payment_ready and evidence.usdt_bsc_payment_verified
    outcome_ready = fulfilment_ready and evidence.fulfilment_delivery_verified
    first_revenue = all(ok for _, ok in checks)

    return FirstRevenueReadiness(
        ready_for_outbound=outbound_ready,
        ready_for_payment_acceptance=payment_ready,
        ready_for_fulfilment=fulfilment_ready,
        ready_for_outcome_recognition=outcome_ready,
        first_revenue_proven=first_revenue,
        blockers=tuple(blockers),
    )
