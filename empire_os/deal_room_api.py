"""Read-only/governed Deal Room API surface."""
from __future__ import annotations

import os

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from empire_os.deal_room import (
    AgreementDraft,
    AgreementRecipient,
    agreement_evidence_is_verified,
    build_documenso_envelope_plan,
    normalize_documenso_webhook,
    verify_documenso_webhook_secret,
)


class RecipientRequest(BaseModel):
    email: str
    name: str
    role: str = "SIGNER"
    signing_order: int | None = Field(default=None, ge=1)


class AgreementPreviewRequest(BaseModel):
    external_id: str
    title: str
    document_sha256: str
    recipients: list[RecipientRequest] = Field(min_length=1)
    source_evidence_refs: list[str] = Field(min_length=1)
    commercial_terms_ref: str
    redirect_url: str | None = None


def create_deal_room_router() -> APIRouter:
    router = APIRouter(prefix="/v1/deal-room", tags=["deal-room"])

    @router.get("/health")
    def health():
        return {
            "mode": "OBSERVE",
            "provider": "documenso",
            "provider_configured": bool(
                os.getenv("DOCUMENSO_API_KEY", "").strip()
            ),
            "webhook_verification_configured": bool(
                os.getenv("DOCUMENSO_WEBHOOK_SECRET", "").strip()
            ),
            "provider_execution": False,
            "binding_acceptance": False,
            "payment_authority": False,
            "revenue_authority": False,
            "execution_authority": "none",
        }

    @router.post("/agreement/preview")
    def preview(req: AgreementPreviewRequest):
        try:
            draft = AgreementDraft(
                external_id=req.external_id,
                title=req.title,
                document_sha256=req.document_sha256,
                recipients=tuple(
                    AgreementRecipient(
                        email=row.email,
                        name=row.name,
                        role=row.role,
                        signing_order=row.signing_order,
                    )
                    for row in req.recipients
                ),
                source_evidence_refs=tuple(req.source_evidence_refs),
                commercial_terms_ref=req.commercial_terms_ref,
                redirect_url=req.redirect_url,
            )
            return build_documenso_envelope_plan(draft)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.post("/webhooks/documenso/preview")
    def webhook_preview(
        payload: dict,
        x_documenso_secret: str | None = Header(default=None),
    ):
        expected = os.getenv("DOCUMENSO_WEBHOOK_SECRET", "").strip()
        if not expected:
            raise HTTPException(503, "documenso_webhook_not_activated")
        if not verify_documenso_webhook_secret(
            x_documenso_secret,
            expected,
        ):
            raise HTTPException(401, "unauthorized")
        try:
            evidence = normalize_documenso_webhook(payload)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "verified_webhook": True,
            "agreement_evidence_verified": (
                agreement_evidence_is_verified(evidence)
            ),
            "evidence": evidence.as_dict(),
            "canonical_commercial_mutation": False,
            "payment_request_created": False,
            "funds_movement": False,
            "revenue_recognition": False,
            "execution_authority": "none",
        }

    return router
