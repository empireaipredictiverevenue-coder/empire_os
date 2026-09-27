"""Phase 6 approval-only A2A negotiation lifecycle."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


ALLOWED_NEGOTIATION_STATES = frozenset({
    "pending_approval",
    "reviewed",
    "counter_proposed",
    "approved_for_manual_execution",
    "rejected",
})

TRANSITIONS = {
    "pending_approval": frozenset({"reviewed", "rejected"}),
    "reviewed": frozenset({
        "counter_proposed",
        "approved_for_manual_execution",
        "rejected",
    }),
    "counter_proposed": frozenset({"reviewed", "rejected"}),
    "approved_for_manual_execution": frozenset(),
    "rejected": frozenset(),
}


@dataclass(frozen=True)
class NegotiationTransition:
    current_state: str
    requested_state: str
    transition_valid: bool
    human_approval_present: bool
    reason: str
    human_approval_required: bool = True
    execution_authority: str = "none"
    payment_authority: bool = False
    allocation_authority: bool = False
    task_execution: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def preview_negotiation_transition(
    *,
    current_state: str,
    requested_state: str,
    human_approval_present: bool,
) -> NegotiationTransition:
    current = str(current_state or "").strip()
    requested = str(requested_state or "").strip()

    if current not in ALLOWED_NEGOTIATION_STATES:
        raise ValueError("unsupported current negotiation state")
    if requested not in ALLOWED_NEGOTIATION_STATES:
        raise ValueError("unsupported requested negotiation state")

    allowed = requested in TRANSITIONS[current]
    if not allowed:
        return NegotiationTransition(
            current_state=current,
            requested_state=requested,
            transition_valid=False,
            human_approval_present=human_approval_present,
            reason="transition_not_allowed",
        )

    if not human_approval_present:
        return NegotiationTransition(
            current_state=current,
            requested_state=requested,
            transition_valid=False,
            human_approval_present=False,
            reason="human_approval_required",
        )

    return NegotiationTransition(
        current_state=current,
        requested_state=requested,
        transition_valid=True,
        human_approval_present=True,
        reason=(
            "approved_for_manual_execution_only"
            if requested == "approved_for_manual_execution"
            else "governed_transition_reviewable"
        ),
    )
