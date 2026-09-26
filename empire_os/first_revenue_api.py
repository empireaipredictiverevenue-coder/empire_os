"""Preview-only Phase 3 first-revenue proof readiness API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from empire_os.first_revenue_evidence import (
    compile_first_revenue_evidence,
)
from empire_os.first_revenue_proof import (
    FirstRevenueEvidence,
    assess_first_revenue_readiness,
)


class FirstRevenueReadinessRequest(BaseModel):
    buyer_identity_verified: bool = False
    commercial_terms_verified: bool = False
    human_approval_recorded: bool = False
    outbound_intent_approved: bool = False
    send_evidence_verified: bool = False
    delivery_evidence_verified: bool = False
    agreement_evidence_verified: bool = False
    usdt_bsc_payment_verified: bool = False
    fulfilment_delivery_verified: bool = False
    outcome_evidence_verified: bool = False
    revenue_recognized: bool = False
    evidence_refs: list[str] = Field(min_length=1)


class FirstRevenueCanonicalEvidenceRequest(BaseModel):
    buyer: dict[str, Any] = Field(default_factory=dict)
    outbound_intent: dict[str, Any] = Field(default_factory=dict)
    provider_events: list[dict[str, Any]] = Field(default_factory=list)
    agreement: dict[str, Any] = Field(default_factory=dict)
    payment: dict[str, Any] = Field(default_factory=dict)
    fulfilment: dict[str, Any] = Field(default_factory=dict)
    outcome: dict[str, Any] = Field(default_factory=dict)
    revenue_event: dict[str, Any] = Field(default_factory=dict)


def create_first_revenue_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/first-revenue",
        tags=["first-revenue-proof"],
    )

    @router.get("/health")
    def health():
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "side_effects": "none",
            "outbound_execution": False,
            "payment_execution": False,
            "fulfilment_execution": False,
            "revenue_mutation": False,
        }

    @router.post("/readiness/preview")
    def readiness(req: FirstRevenueReadinessRequest):
        try:
            result = assess_first_revenue_readiness(
                FirstRevenueEvidence(
                    buyer_identity_verified=req.buyer_identity_verified,
                    commercial_terms_verified=req.commercial_terms_verified,
                    human_approval_recorded=req.human_approval_recorded,
                    outbound_intent_approved=req.outbound_intent_approved,
                    send_evidence_verified=req.send_evidence_verified,
                    delivery_evidence_verified=req.delivery_evidence_verified,
                    agreement_evidence_verified=req.agreement_evidence_verified,
                    usdt_bsc_payment_verified=req.usdt_bsc_payment_verified,
                    fulfilment_delivery_verified=req.fulfilment_delivery_verified,
                    outcome_evidence_verified=req.outcome_evidence_verified,
                    revenue_recognized=req.revenue_recognized,
                    evidence_refs=tuple(req.evidence_refs),
                )
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "side_effects": "none",
            "outbound_execution": False,
            "payment_execution": False,
            "fulfilment_execution": False,
            "revenue_mutation": False,
            "readiness": result.as_dict(),
        }

    @router.post("/readiness/from-canonical-evidence")
    def readiness_from_canonical_evidence(
        req: FirstRevenueCanonicalEvidenceRequest,
    ):
        try:
            evidence = compile_first_revenue_evidence(
                buyer=req.buyer,
                outbound_intent=req.outbound_intent,
                provider_events=req.provider_events,
                agreement=req.agreement,
                payment=req.payment,
                fulfilment=req.fulfilment,
                outcome=req.outcome,
                revenue_event=req.revenue_event,
            )
            result = assess_first_revenue_readiness(evidence)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "side_effects": "none",
            "outbound_execution": False,
            "payment_execution": False,
            "fulfilment_execution": False,
            "revenue_mutation": False,
            "compiled_evidence": {
                "buyer_identity_verified": evidence.buyer_identity_verified,
                "commercial_terms_verified": evidence.commercial_terms_verified,
                "human_approval_recorded": evidence.human_approval_recorded,
                "outbound_intent_approved": evidence.outbound_intent_approved,
                "send_evidence_verified": evidence.send_evidence_verified,
                "delivery_evidence_verified": evidence.delivery_evidence_verified,
                "agreement_evidence_verified": evidence.agreement_evidence_verified,
                "usdt_bsc_payment_verified": evidence.usdt_bsc_payment_verified,
                "fulfilment_delivery_verified": (
                    evidence.fulfilment_delivery_verified
                ),
                "outcome_evidence_verified": evidence.outcome_evidence_verified,
                "revenue_recognized": evidence.revenue_recognized,
                "evidence_refs": list(evidence.evidence_refs),
            },
            "readiness": result.as_dict(),
        }

    return router
