"""Phase 6 evidence-only A2A manual handoff review."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class A2AManualHandoffEvidence:
    negotiation_id: str
    agent_id: str
    negotiation_state: str
    signed_identity_evidence_ref: str | None
    negotiation_evidence_ref: str | None
    human_approval_present: bool
    human_approval_evidence_ref: str | None
    counterparty_acknowledged: bool
    counterparty_evidence_ref: str | None
    manual_handoff_ref: str | None

    def validate(self) -> None:
        if not self.negotiation_id.strip():
            raise ValueError("negotiation_id required")
        if not self.agent_id.strip():
            raise ValueError("agent_id required")


@dataclass(frozen=True)
class A2AManualHandoffReview:
    negotiation_id: str
    agent_id: str
    handoff_ready_for_operator_review: bool
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    human_approval_required: bool = True
    execution_authority: str = "none"
    payment_authority: bool = False
    allocation_authority: bool = False
    task_execution: bool = False
    autonomous_handoff_execution: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def review_manual_handoff(
    evidence: A2AManualHandoffEvidence,
) -> A2AManualHandoffReview:
    evidence.validate()
    blockers: list[str] = []
    refs: list[str] = []

    if evidence.negotiation_state != "approved_for_manual_execution":
        blockers.append("negotiation_not_approved_for_manual_execution")

    signed_ref = str(evidence.signed_identity_evidence_ref or "").strip()
    if signed_ref:
        refs.append(signed_ref)
    else:
        blockers.append("signed_agent_identity_evidence_missing")

    negotiation_ref = str(evidence.negotiation_evidence_ref or "").strip()
    if negotiation_ref:
        refs.append(negotiation_ref)
    else:
        blockers.append("negotiation_evidence_missing")

    approval_ref = str(evidence.human_approval_evidence_ref or "").strip()
    if evidence.human_approval_present and approval_ref:
        refs.append(approval_ref)
    else:
        blockers.append("human_approval_evidence_missing")

    counterparty_ref = str(evidence.counterparty_evidence_ref or "").strip()
    if evidence.counterparty_acknowledged and counterparty_ref:
        refs.append(counterparty_ref)
    else:
        blockers.append("counterparty_acknowledgement_evidence_missing")

    handoff_ref = str(evidence.manual_handoff_ref or "").strip()
    if handoff_ref:
        refs.append(handoff_ref)
    else:
        blockers.append("manual_handoff_reference_missing")

    ordered = tuple(sorted(set(blockers)))
    return A2AManualHandoffReview(
        negotiation_id=evidence.negotiation_id,
        agent_id=evidence.agent_id,
        handoff_ready_for_operator_review=not ordered,
        blockers=ordered,
        evidence_refs=tuple(dict.fromkeys(refs)),
    )
