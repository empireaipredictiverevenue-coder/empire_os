"""Fail-closed authenticated A2A commercial-intent API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Protocol

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from empire_os.a2a_attribution import (
    A2ACommercialAttributionEvidence,
    review_a2a_commercial_attribution,
)
from empire_os.a2a_commerce_intent import (
    CommercialIntent,
    normalize_intent_record,
)
from empire_os.a2a_handoff import (
    A2AManualHandoffEvidence,
    review_manual_handoff,
)
from empire_os.a2a_handoff_readiness import (
    A2AHandoffTimingEvidence,
    review_manual_handoff_readiness,
)
from empire_os.a2a_negotiation import preview_negotiation_transition
from empire_os.a2a_identity import (
    AgentIdentityClaim,
    Clock,
    NonceRegistry,
    SignatureVerifier,
    verify_agent_identity,
)


class CommercialIntentRepository(Protocol):
    def record(
        self,
        *,
        intent: CommercialIntent,
    ) -> Mapping[str, Any]:
        ...


class IdentityClaimRequest(BaseModel):
    agent_id: str
    key_id: str
    nonce: str
    issued_at: str
    signature: str




class NegotiationTransitionRequest(BaseModel):
    current_state: str
    requested_state: str
    human_approval_present: bool = False


class ManualHandoffReviewRequest(BaseModel):
    negotiation_id: str
    agent_id: str
    negotiation_state: str
    signed_identity_evidence_ref: str | None = None
    negotiation_evidence_ref: str | None = None
    human_approval_present: bool = False
    human_approval_evidence_ref: str | None = None
    counterparty_acknowledged: bool = False
    counterparty_evidence_ref: str | None = None
    manual_handoff_ref: str | None = None


class CommercialAttributionRequest(BaseModel):
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


class ManualHandoffReadinessRequest(ManualHandoffReviewRequest):
    negotiation_observed_at: str
    human_approval_observed_at: str | None = None
    counterparty_observed_at: str | None = None
    handoff_observed_at: str | None = None
    now_utc: str
    max_age_seconds: int = Field(default=21600, gt=0)


class CommercialIntentRequest(BaseModel):
    identity: IdentityClaimRequest
    capability: str
    idempotency_key: str
    request: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)


def create_a2a_commerce_router(
    *,
    verifier: SignatureVerifier | None = None,
    trusted_key_ids: set[str] | frozenset[str] | None = None,
    repository: CommercialIntentRepository | None = None,
    nonce_registry: NonceRegistry | None = None,
    clock: Clock | None = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/a2a-commerce",
        tags=["a2a-commerce"],
    )
    trusted = frozenset(trusted_key_ids or ())

    @router.get("/health")
    def health():
        configured = (
            verifier is not None
            and bool(trusted)
            and repository is not None
            and nonce_registry is not None
        )
        return {
            "mode": "OBSERVE",
            "scope": "commerce.intent",
            "configured": configured,
            "human_approval_required": True,
            "execution_authority": "none",
            "payment_authority": False,
            "allocation_authority": False,
        }


    @router.post("/negotiation/transition/preview")
    def negotiation_transition_preview(req: NegotiationTransitionRequest):
        try:
            result = preview_negotiation_transition(
                current_state=req.current_state,
                requested_state=req.requested_state,
                human_approval_present=req.human_approval_present,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "human_approval_required": True,
            "execution_authority": "none",
            "payment_authority": False,
            "allocation_authority": False,
            "task_execution": False,
            "transition": result.as_dict(),
        }

    @router.post("/negotiation/handoff/preview")
    def negotiation_handoff_preview(req: ManualHandoffReviewRequest):
        try:
            review = review_manual_handoff(
                A2AManualHandoffEvidence(
                    negotiation_id=req.negotiation_id,
                    agent_id=req.agent_id,
                    negotiation_state=req.negotiation_state,
                    signed_identity_evidence_ref=(
                        req.signed_identity_evidence_ref
                    ),
                    negotiation_evidence_ref=req.negotiation_evidence_ref,
                    human_approval_present=req.human_approval_present,
                    human_approval_evidence_ref=(
                        req.human_approval_evidence_ref
                    ),
                    counterparty_acknowledged=(
                        req.counterparty_acknowledged
                    ),
                    counterparty_evidence_ref=(
                        req.counterparty_evidence_ref
                    ),
                    manual_handoff_ref=req.manual_handoff_ref,
                )
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "human_approval_required": True,
            "execution_authority": "none",
            "payment_authority": False,
            "allocation_authority": False,
            "task_execution": False,
            "autonomous_handoff_execution": False,
            "handoff": review.as_dict(),
        }

    @router.post("/negotiation/handoff/readiness/preview")
    def negotiation_handoff_readiness_preview(
        req: ManualHandoffReadinessRequest,
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
            readiness = review_manual_handoff_readiness(
                evidence=A2AManualHandoffEvidence(
                    negotiation_id=req.negotiation_id,
                    agent_id=req.agent_id,
                    negotiation_state=req.negotiation_state,
                    signed_identity_evidence_ref=(
                        req.signed_identity_evidence_ref
                    ),
                    negotiation_evidence_ref=req.negotiation_evidence_ref,
                    human_approval_present=req.human_approval_present,
                    human_approval_evidence_ref=(
                        req.human_approval_evidence_ref
                    ),
                    counterparty_acknowledged=(
                        req.counterparty_acknowledged
                    ),
                    counterparty_evidence_ref=(
                        req.counterparty_evidence_ref
                    ),
                    manual_handoff_ref=req.manual_handoff_ref,
                ),
                timing=A2AHandoffTimingEvidence(
                    negotiation_observed_at=req.negotiation_observed_at,
                    human_approval_observed_at=(
                        req.human_approval_observed_at
                    ),
                    counterparty_observed_at=req.counterparty_observed_at,
                    handoff_observed_at=req.handoff_observed_at,
                ),
                now=now,
                max_age_seconds=req.max_age_seconds,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "human_approval_required": True,
            "execution_authority": "none",
            "payment_authority": False,
            "allocation_authority": False,
            "task_execution": False,
            "autonomous_handoff_execution": False,
            "readiness": readiness.as_dict(),
        }

    @router.post("/attribution/preview")
    def commercial_attribution_preview(req: CommercialAttributionRequest):
        try:
            review = review_a2a_commercial_attribution(
                A2ACommercialAttributionEvidence(
                    intent_id=req.intent_id,
                    negotiation_id=req.negotiation_id,
                    agent_id=req.agent_id,
                    manual_handoff_ref=req.manual_handoff_ref,
                    fulfilment_order_ref=req.fulfilment_order_ref,
                    payment_request_ref=req.payment_request_ref,
                    verified_payment_ref=req.verified_payment_ref,
                    commercial_outcome_ref=req.commercial_outcome_ref,
                    recognized_revenue_ref=req.recognized_revenue_ref,
                    realized_gp_cents=req.realized_gp_cents,
                )
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "payment_authority": False,
            "allocation_authority": False,
            "revenue_mutation": False,
            "accounting_mutation": False,
            "attribution": review.as_dict(),
        }

    @router.post("/intents")
    def create_intent(req: CommercialIntentRequest):
        if (
            verifier is None
            or not trusted
            or repository is None
            or nonce_registry is None
        ):
            raise HTTPException(
                status_code=503,
                detail="a2a_commerce_intent_not_activated",
            )

        claim = AgentIdentityClaim(
            agent_id=req.identity.agent_id,
            key_id=req.identity.key_id,
            nonce=req.identity.nonce,
            issued_at=req.identity.issued_at,
            signature=req.identity.signature,
            requested_scope="commerce.intent",
        )
        try:
            identity = verify_agent_identity(
                claim,
                verifier=verifier,
                trusted_key_ids=trusted,
                nonce_registry=nonce_registry,
                now=clock,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        if not identity.authenticated:
            raise HTTPException(
                status_code=401,
                detail=identity.reason,
            )
        if identity.granted_scope != "commerce.intent":
            raise HTTPException(
                status_code=403,
                detail="commerce_intent_scope_required",
            )

        intent = CommercialIntent(
            agent_id=identity.agent_id or req.identity.agent_id,
            key_id=identity.key_id or req.identity.key_id,
            identity_nonce=req.identity.nonce,
            identity_issued_at=req.identity.issued_at,
            capability=req.capability,
            idempotency_key=req.idempotency_key,
            request=dict(req.request),
            evidence=dict(req.evidence),
        )
        try:
            intent.validate()
            row = repository.record(intent=intent)
            decision = normalize_intent_record(row)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return {
            "mode": "OBSERVE",
            "decision": decision.as_dict(),
            "human_approval_required": True,
            "execution_authority": "none",
            "payment_authority": False,
            "allocation_authority": False,
        }

    return router
