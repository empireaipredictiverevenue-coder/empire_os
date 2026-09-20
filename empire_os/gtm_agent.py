"""Empire GTM Agent decision layer.

This agent chooses the next commercial action from the canonical commercial
loop blocker. It delegates execution to existing governed modules; it never
executes side effects directly.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from empire_os.gtm_agent_policy import (
    GTMActionReview,
    GTMStandingAuthority,
    review_gtm_action,
)


GTM_AGENT_ID = "empire_gtm_agent_v1"

BLOCKER_ACTIONS = {
    "real_acquisition": "acquisition.run",
    "qualification_v2": "qualification.run",
    "omega_projection": "omega.score",
    "buyer_candidate_approved": "buyer.discovery",
    "outbound_authorized": "outreach.prepare",
    "outbound_sent": "outreach.send",
    "buyer_conversation": "conversation.monitor",
    "commercial_terms": "commercial_terms.draft",
    "verified_buyer_capacity": "buyer.activate",
    "inventory_allocation": "inventory.allocate",
    "bsc_payment_request": "payment_request.issue",
    "bsc_usdt_payment": "payment.monitor",
    "fulfilment": "fulfilment.execute",
    "commercial_outcome": "outcome.observe",
    "recognized_revenue": "revenue.recognize",
    "realized_gross_profit": "outcome.observe",
    "learning_feedback": "learning.run",
}


@dataclass(frozen=True)
class GTMAgentDecision:
    agent_id: str
    blocker: str | None
    next_action: str | None
    action_review: GTMActionReview | None
    rationale: str
    execution_performed: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["action_review"] = (
            self.action_review.as_dict()
            if self.action_review is not None
            else None
        )
        return data


def decide_next_gtm_action(
    loop_status: Mapping[str, Any],
    *,
    now,
    standing_authority: GTMStandingAuthority | None = None,
    action_context: Mapping[str, Any] | None = None,
    external_actions_used_today: int = 0,
) -> GTMAgentDecision:
    blocker = str(
        loop_status.get("highest_priority_blocker") or ""
    ).strip() or None

    if loop_status.get("loop_complete") is True and blocker is None:
        return GTMAgentDecision(
            agent_id=GTM_AGENT_ID,
            blocker=None,
            next_action=None,
            action_review=None,
            rationale="commercial loop is complete; no next GTM action required",
        )

    if blocker is None:
        return GTMAgentDecision(
            agent_id=GTM_AGENT_ID,
            blocker=None,
            next_action=None,
            action_review=None,
            rationale="commercial loop blocker is unavailable",
        )

    action = BLOCKER_ACTIONS.get(blocker)
    if action is None:
        return GTMAgentDecision(
            agent_id=GTM_AGENT_ID,
            blocker=blocker,
            next_action=None,
            action_review=None,
            rationale=f"no GTM action mapping exists for blocker {blocker}",
        )

    review = review_gtm_action(
        action,
        now=now,
        standing_authority=standing_authority,
        context=action_context,
        external_actions_used_today=external_actions_used_today,
    )

    if review.permitted:
        rationale = (
            f"{blocker} is the first incomplete commercial stage; "
            f"{action} is authorized in {review.lane.value}"
        )
    else:
        rationale = (
            f"{blocker} is the first incomplete commercial stage; "
            f"{action} is blocked by {', '.join(review.blockers)}"
        )

    return GTMAgentDecision(
        agent_id=GTM_AGENT_ID,
        blocker=blocker,
        next_action=action,
        action_review=review,
        rationale=rationale,
    )
