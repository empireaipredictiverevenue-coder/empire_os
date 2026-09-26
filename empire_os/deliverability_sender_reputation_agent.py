"""Deliverability & Sender Reputation Agent.

Evidence-first internal health analysis only. No external send, DNS mutation,
provider purchase, authority expansion, payment, or revenue recognition.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping


KNOWN_EVENT_TYPES = frozenset({
    "sent",
    "delivered",
    "deferred",
    "soft_bounce",
    "hard_bounce",
    "reply",
    "opt_out",
})


@dataclass(frozen=True)
class DeliverabilityState:
    sent: int
    delivered: int
    deferred: int
    soft_bounce: int
    hard_bounce: int
    replies: int
    opt_outs: int
    delivery_rate: float | None
    deferral_rate: float | None
    hard_bounce_rate: float | None
    reply_rate: float | None
    suppression_candidates: tuple[str, ...]
    recommended_action: str
    recommendation_reason: str
    composite_reputation_score: None = None
    action_performed: bool = False
    outbound_send_authority: bool = False
    dns_mutation_authority: bool = False
    payment_authority: bool = False
    revenue_recognition_authority: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(max(0, numerator) / denominator, 4)


def build_deliverability_state(
    events: Iterable[Mapping[str, Any]],
) -> DeliverabilityState:
    counts = {key: 0 for key in KNOWN_EVENT_TYPES}
    suppression: set[str] = set()

    for event in events:
        event_type = str(
            event.get("event_type")
            or event.get("type")
            or ""
        ).strip().lower()
        if event_type not in KNOWN_EVENT_TYPES:
            continue
        counts[event_type] += 1

        if event_type in {"hard_bounce", "opt_out"}:
            recipient = str(
                event.get("normalized_recipient")
                or event.get("recipient")
                or ""
            ).strip().lower()
            if recipient:
                suppression.add(recipient)

    sent = counts["sent"]
    hard_rate = _rate(counts["hard_bounce"], sent)
    deferral_rate = _rate(counts["deferred"], sent)

    action = "continue_observe"
    reason = "no_observed_threshold_trigger"

    if counts["hard_bounce"] > 0 and sent < 20:
        action = "suppress_proven_hard_failures"
        reason = "observed_hard_failure_requires_recipient_suppression"
    if (
        hard_rate is not None
        and sent >= 20
        and hard_rate >= 0.05
    ):
        action = "pause_sender_lane_review"
        reason = "observed_hard_bounce_rate_at_or_above_5_percent"
    elif (
        deferral_rate is not None
        and sent >= 20
        and deferral_rate >= 0.20
    ):
        action = "reduce_cap_review"
        reason = "observed_deferral_rate_at_or_above_20_percent"
    elif counts["opt_out"] > 0:
        action = "suppress_opt_outs"
        reason = "observed_opt_out_requires_suppression"

    return DeliverabilityState(
        sent=sent,
        delivered=counts["delivered"],
        deferred=counts["deferred"],
        soft_bounce=counts["soft_bounce"],
        hard_bounce=counts["hard_bounce"],
        replies=counts["reply"],
        opt_outs=counts["opt_out"],
        delivery_rate=_rate(counts["delivered"], sent),
        deferral_rate=deferral_rate,
        hard_bounce_rate=hard_rate,
        reply_rate=_rate(counts["reply"], sent),
        suppression_candidates=tuple(sorted(suppression)),
        recommended_action=action,
        recommendation_reason=reason,
    )


def deliverability_agent_status() -> dict[str, Any]:
    return {
        "schema_version": "empire.deliverability-agent.v1",
        "observed_inputs_only": True,
        "fabricated_reputation_score": False,
        "automatic_actions": "none",
        "outbound_send_authority": False,
        "dns_mutation_authority": False,
        "provider_purchase_authority": False,
        "payment_authority": False,
        "revenue_recognition_authority": False,
        "execution_authority": "none",
    }
