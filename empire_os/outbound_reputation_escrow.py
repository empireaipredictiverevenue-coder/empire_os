"""Reputation escrow: sender capacity is earned slowly and lost quickly."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ReputationEscrowPolicy:
    minimum_credit: int = 0
    maximum_credit: int = 100
    starting_credit: int = 10
    green_gain: int = 2
    positive_reply_gain: int = 1
    hard_bounce_loss: int = 8
    complaint_loss: int = 30
    auth_failure_loss: int = 50
    deferral_loss: int = 3


def update_reputation_credit(
    state: Mapping[str, Any],
    observation: Mapping[str, Any],
    *,
    policy: ReputationEscrowPolicy | None = None,
) -> dict[str, Any]:
    policy = policy or ReputationEscrowPolicy()
    credit = int(state.get("credit") if state.get("credit") is not None else policy.starting_credit)
    deltas: list[dict[str, Any]] = []

    if observation.get("green_window") is True:
        credit += policy.green_gain
        deltas.append({"reason": "green_window", "delta": policy.green_gain})

    positive_replies = max(0, int(observation.get("positive_replies") or 0))
    if positive_replies:
        gain = min(3, positive_replies) * policy.positive_reply_gain
        credit += gain
        deltas.append({"reason": "positive_replies", "delta": gain})

    hard_bounces = max(0, int(observation.get("hard_bounces") or 0))
    if hard_bounces:
        loss = hard_bounces * policy.hard_bounce_loss
        credit -= loss
        deltas.append({"reason": "hard_bounces", "delta": -loss})

    complaints = max(0, int(observation.get("complaints") or 0))
    if complaints:
        loss = complaints * policy.complaint_loss
        credit -= loss
        deltas.append({"reason": "complaints", "delta": -loss})

    auth_failures = max(0, int(observation.get("auth_failures") or 0))
    if auth_failures:
        loss = auth_failures * policy.auth_failure_loss
        credit -= loss
        deltas.append({"reason": "auth_failures", "delta": -loss})

    deferrals = max(0, int(observation.get("deferrals") or 0))
    if deferrals:
        loss = min(10, deferrals) * policy.deferral_loss
        credit -= loss
        deltas.append({"reason": "deferrals", "delta": -loss})

    credit = max(policy.minimum_credit, min(policy.maximum_credit, credit))

    if credit == 0:
        state_name = "QUARANTINED"
    elif credit < 15:
        state_name = "LIMITED"
    elif credit < 40:
        state_name = "RAMPING"
    else:
        state_name = "HEALTHY"

    # Credit is not a send count. It constrains policy-selected capacity elsewhere.
    return {
        "credit": credit,
        "state": state_name,
        "deltas": deltas,
        "meaning": "reputation_capital_not_send_authority",
    }
