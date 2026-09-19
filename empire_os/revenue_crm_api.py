"""Bounded read-only API contract for the canonical Revenue CRM."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Mapping, Protocol, Sequence

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from empire_os.revenue_crm_readiness import assess_close_readiness
from empire_os.revenue_crm_retention import (
    RevenueCrmRetentionEvidence,
    assess_retention_expansion_readiness,
)
from empire_os.revenue_crm_retention_freshness import (
    RevenueCrmRetentionTiming,
    assess_retention_expansion_freshness,
)


class RevenueCrmRepository(Protocol):
    def prospects(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        ...

    def buyers(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        ...

    def prospect(self, prospect_id: str) -> Mapping[str, Any] | None:
        ...


class RevenueCrmRetentionRequest(BaseModel):
    buyer_id: str
    buyer_activated: bool
    buyer_evidence_ref: str | None = None
    payment_verified: bool
    payment_evidence_ref: str | None = None
    fulfilment_delivered: bool
    fulfilment_evidence_ref: str | None = None
    outcome_observed: bool
    outcome_success_verified: bool | None = None
    outcome_evidence_ref: str | None = None
    buyer_available_capacity: int | None = Field(default=None, ge=0)
    capacity_evidence_ref: str | None = None


class RevenueCrmRetentionFreshnessRequest(RevenueCrmRetentionRequest):
    buyer_observed_at: str
    payment_observed_at: str | None = None
    fulfilment_observed_at: str | None = None
    outcome_observed_at: str | None = None
    capacity_observed_at: str | None = None
    now_utc: str
    max_age_seconds: int = Field(default=86400, gt=0)


@dataclass(frozen=True)
class EvidenceRef:
    kind: str
    record_id: str
    state: str | None
    observed_at: str | None
    detail: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NextActionEvidence:
    available: bool
    action: str | None
    reason: str
    evidence: tuple[EvidenceRef, ...]
    execution_authority: str = "none"
    approval_required: bool = True

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence"] = [item.as_dict() for item in self.evidence]
        return data


def _canonical_ref(
    *,
    kind: str,
    record_id: Any,
    state: Any,
    observed_at: Any,
    detail: str | None = None,
) -> EvidenceRef | None:
    rid = str(record_id or "").strip()
    if not rid:
        return None
    state_text = str(state or "").strip() or None
    observed_text = str(observed_at or "").strip() or None
    return EvidenceRef(
        kind=kind,
        record_id=rid,
        state=state_text,
        observed_at=observed_text,
        detail=detail,
    )


def derive_next_action(
    prospect: Mapping[str, Any],
) -> NextActionEvidence:
    closer_state = str(
        prospect.get("closer_state") or ""
    ).strip().lower()
    conversation_state = str(
        prospect.get("conversation_state") or ""
    ).strip().lower()
    fulfilment_state = str(
        prospect.get("fulfilment_state") or ""
    ).strip().lower()

    closer_ref = _canonical_ref(
        kind="closer_case",
        record_id=prospect.get("closer_case_id"),
        state=prospect.get("closer_state"),
        observed_at=prospect.get("closer_updated_at"),
    )
    conversation_ref = _canonical_ref(
        kind="conversation",
        record_id=prospect.get("conversation_id"),
        state=prospect.get("conversation_state"),
        observed_at=prospect.get("conversation_updated_at"),
    )
    fulfilment_ref = _canonical_ref(
        kind="fulfilment_order",
        record_id=prospect.get("fulfilment_order_id"),
        state=prospect.get("fulfilment_state"),
        observed_at=prospect.get("fulfilment_updated_at"),
    )

    if closer_state == "awaiting_payment" and closer_ref is not None:
        return NextActionEvidence(
            available=True,
            action="review_payment_status",
            reason="closer_case_is_waiting_on_payment",
            evidence=(closer_ref,),
        )

    if closer_state == "proposal_ready" and closer_ref is not None:
        return NextActionEvidence(
            available=True,
            action="review_proposal_readiness",
            reason="closer_case_has_observed_proposal_ready_state",
            evidence=(closer_ref,),
        )

    if conversation_state == "engaged" and conversation_ref is not None:
        return NextActionEvidence(
            available=True,
            action="review_engaged_conversation",
            reason="canonical_conversation_is_engaged",
            evidence=(conversation_ref,),
        )

    if (
        fulfilment_state
        in {"accepted", "invoiced", "delivered", "confirmed"}
        and fulfilment_ref is not None
    ):
        return NextActionEvidence(
            available=True,
            action="review_fulfilment_state",
            reason="canonical_fulfilment_requires_operator_review",
            evidence=(fulfilment_ref,),
        )

    buyer_id = str(prospect.get("buyer_id") or "").strip()
    buyer_activation = str(
        prospect.get("buyer_activation_state") or ""
    ).strip().lower()
    capacity = prospect.get("buyer_available_capacity")
    capacity_verified_at = str(
        prospect.get("buyer_capacity_verified_at") or ""
    ).strip()
    if (
        buyer_id
        and buyer_activation == "activated"
        and capacity is not None
        and capacity_verified_at
    ):
        capacity_value = int(capacity)
        if capacity_value > 0:
            buyer_ref = EvidenceRef(
                kind="buyer_capacity",
                record_id=buyer_id,
                state=buyer_activation,
                observed_at=capacity_verified_at,
                detail=f"available_capacity:{capacity_value}",
            )
            return NextActionEvidence(
                available=True,
                action="review_buyer_capacity",
                reason="allocated_buyer_has_verified_available_capacity",
                evidence=(buyer_ref,),
            )

    return NextActionEvidence(
        available=False,
        action=None,
        reason="insufficient_observed_evidence",
        evidence=(),
    )


def create_revenue_crm_router(
    repository: RevenueCrmRepository | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/v1/revenue-crm")

    @router.get("/health")
    def health():
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "execution_authority": "none",
            "follow_up_execution": False,
            "payment_execution": False,
            "repository_available": repository is not None,
        }

    def require_repository() -> RevenueCrmRepository:
        if repository is None:
            raise HTTPException(
                status_code=503,
                detail="revenue_crm_repository_not_activated",
            )
        return repository

    @router.post("/retention-expansion/preview")
    def retention_expansion_preview(req: RevenueCrmRetentionRequest):
        try:
            evidence = RevenueCrmRetentionEvidence(
                buyer_id=req.buyer_id,
                buyer_activated=req.buyer_activated,
                buyer_evidence_ref=req.buyer_evidence_ref,
                payment_verified=req.payment_verified,
                payment_evidence_ref=req.payment_evidence_ref,
                fulfilment_delivered=req.fulfilment_delivered,
                fulfilment_evidence_ref=req.fulfilment_evidence_ref,
                outcome_observed=req.outcome_observed,
                outcome_success_verified=req.outcome_success_verified,
                outcome_evidence_ref=req.outcome_evidence_ref,
                buyer_available_capacity=req.buyer_available_capacity,
                capacity_evidence_ref=req.capacity_evidence_ref,
            )
            readiness = assess_retention_expansion_readiness(evidence)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "execution_authority": "none",
            "follow_up_execution": False,
            "payment_execution": False,
            "crm_mutation": False,
            "offer_mutation": False,
            "readiness": readiness.as_dict(),
        }

    @router.post("/retention-expansion/freshness/preview")
    def retention_expansion_freshness_preview(
        req: RevenueCrmRetentionFreshnessRequest,
    ):
        try:
            normalized = (
                req.now_utc[:-1] + "+00:00"
                if req.now_utc.endswith("Z")
                else req.now_utc
            )
            now = datetime.fromisoformat(normalized)
            if now.tzinfo is None:
                raise ValueError("now_utc must include timezone")
            evidence = RevenueCrmRetentionEvidence(
                buyer_id=req.buyer_id,
                buyer_activated=req.buyer_activated,
                buyer_evidence_ref=req.buyer_evidence_ref,
                payment_verified=req.payment_verified,
                payment_evidence_ref=req.payment_evidence_ref,
                fulfilment_delivered=req.fulfilment_delivered,
                fulfilment_evidence_ref=req.fulfilment_evidence_ref,
                outcome_observed=req.outcome_observed,
                outcome_success_verified=req.outcome_success_verified,
                outcome_evidence_ref=req.outcome_evidence_ref,
                buyer_available_capacity=req.buyer_available_capacity,
                capacity_evidence_ref=req.capacity_evidence_ref,
            )
            freshness = assess_retention_expansion_freshness(
                evidence=evidence,
                timing=RevenueCrmRetentionTiming(
                    buyer_observed_at=req.buyer_observed_at,
                    payment_observed_at=req.payment_observed_at,
                    fulfilment_observed_at=req.fulfilment_observed_at,
                    outcome_observed_at=req.outcome_observed_at,
                    capacity_observed_at=req.capacity_observed_at,
                ),
                now=now,
                max_age_seconds=req.max_age_seconds,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "execution_authority": "none",
            "follow_up_execution": False,
            "payment_execution": False,
            "crm_mutation": False,
            "offer_mutation": False,
            "freshness": freshness.as_dict(),
        }

    @router.get("/prospects")
    def prospects(limit: int = Query(default=100, ge=1, le=500)):
        repo = require_repository()
        rows = [dict(row) for row in repo.prospects(limit=limit)]
        return {
            "source": "canonical_revenue_crm_repository",
            "count": len(rows),
            "limit": limit,
            "items": rows,
            "read_only": True,
        }

    @router.get("/buyers")
    def buyers(limit: int = Query(default=100, ge=1, le=500)):
        repo = require_repository()
        rows = [dict(row) for row in repo.buyers(limit=limit)]
        return {
            "source": "canonical_revenue_crm_repository",
            "count": len(rows),
            "limit": limit,
            "items": rows,
            "read_only": True,
        }

    @router.get("/prospects/{prospect_id}/next-action")
    def next_action(prospect_id: str):
        repo = require_repository()
        row = repo.prospect(prospect_id)
        if row is None:
            raise HTTPException(status_code=404, detail="prospect_not_found")
        return derive_next_action(row).as_dict()

    @router.get("/prospects/{prospect_id}/close-readiness")
    def close_readiness(prospect_id: str):
        repo = require_repository()
        row = repo.prospect(prospect_id)
        if row is None:
            raise HTTPException(status_code=404, detail="prospect_not_found")
        try:
            readiness = assess_close_readiness(row)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "execution_authority": "none",
            "follow_up_execution": False,
            "payment_execution": False,
            "crm_mutation": False,
            "readiness": readiness.as_dict(),
        }

    return router
