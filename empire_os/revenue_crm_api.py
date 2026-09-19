"""Bounded read-only API contract for the canonical Revenue CRM."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Protocol, Sequence

from fastapi import APIRouter, HTTPException, Query


class RevenueCrmRepository(Protocol):
    def prospects(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        ...

    def buyers(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        ...

    def prospect(self, prospect_id: str) -> Mapping[str, Any] | None:
        ...


@dataclass(frozen=True)
class NextActionEvidence:
    available: bool
    action: str | None
    reason: str
    evidence: tuple[str, ...]
    execution_authority: str = "none"
    approval_required: bool = True

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
def derive_next_action(
    prospect: Mapping[str, Any],
) -> NextActionEvidence:
    closer_state = str(prospect.get("closer_state") or "").strip().lower()
    conversation_state = str(
        prospect.get("conversation_state") or ""
    ).strip().lower()
    fulfilment_state = str(
        prospect.get("fulfilment_state") or ""
    ).strip().lower()

    if closer_state == "awaiting_payment":
        return NextActionEvidence(
            available=True,
            action="review_payment_status",
            reason="closer_case_is_waiting_on_payment",
            evidence=("closer_state:awaiting_payment",),
        )

    if closer_state == "proposal_ready":
        return NextActionEvidence(
            available=True,
            action="review_proposal_readiness",
            reason="closer_case_has_observed_proposal_ready_state",
            evidence=("closer_state:proposal_ready",),
        )

    if conversation_state == "engaged":
        return NextActionEvidence(
            available=True,
            action="review_engaged_conversation",
            reason="canonical_conversation_is_engaged",
            evidence=("conversation_state:engaged",),
        )

    if fulfilment_state in {"accepted", "invoiced", "delivered", "confirmed"}:
        return NextActionEvidence(
            available=True,
            action="review_fulfilment_state",
            reason="canonical_fulfilment_requires_operator_review",
            evidence=(f"fulfilment_state:{fulfilment_state}",),
        )

    return NextActionEvidence(
        available=False,
        action=None,
        reason="insufficient_observed_evidence",
        evidence=(),
    )


def create_revenue_crm_router(
    repository: RevenueCrmRepository,
) -> APIRouter:
    router = APIRouter(prefix="/v1/revenue-crm")

    @router.get("/prospects")
    def prospects(limit: int = Query(default=100, ge=1, le=500)):
        rows = [dict(row) for row in repository.prospects(limit=limit)]
        return {
            "source": "canonical_revenue_crm_repository",
            "count": len(rows),
            "limit": limit,
            "items": rows,
            "read_only": True,
        }

    @router.get("/buyers")
    def buyers(limit: int = Query(default=100, ge=1, le=500)):
        rows = [dict(row) for row in repository.buyers(limit=limit)]
        return {
            "source": "canonical_revenue_crm_repository",
            "count": len(rows),
            "limit": limit,
            "items": rows,
            "read_only": True,
        }

    @router.get("/prospects/{prospect_id}/next-action")
    def next_action(prospect_id: str):
        row = repository.prospect(prospect_id)
        if row is None:
            raise HTTPException(status_code=404, detail="prospect_not_found")
        return derive_next_action(row).as_dict()

    return router
