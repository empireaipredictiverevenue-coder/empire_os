"""Fail-closed authenticated A2A commercial-intent API."""
from __future__ import annotations

from typing import Any, Mapping, Protocol

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from empire_os.a2a_commerce_intent import (
    CommercialIntent,
    normalize_intent_record,
)
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
