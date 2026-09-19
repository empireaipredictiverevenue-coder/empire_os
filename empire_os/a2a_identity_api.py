"""Discovery-only A2A identity verification API."""
from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from empire_os.a2a_identity import (
    AgentIdentityClaim,
    SignatureVerifier,
    verify_agent_identity,
)


class AgentIdentityClaimRequest(BaseModel):
    agent_id: str
    key_id: str
    nonce: str
    issued_at: str
    signature: str
    requested_scope: str = "discovery"


def create_a2a_identity_router(
    *,
    verifier: SignatureVerifier | None = None,
    trusted_key_ids: set[str] | frozenset[str] | None = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/a2a-identity",
        tags=["a2a-identity"],
    )
    trusted = frozenset(trusted_key_ids or ())

    @router.get("/health")
    def health():
        configured = verifier is not None and bool(trusted)
        return {
            "mode": "OBSERVE",
            "scopes": ["discovery", "commerce.intent"],
            "execution_authority": "none",
            "commerce_execution": False,
            "payment_execution": False,
            "allocation_execution": False,
            "configured": configured,
        }

    @router.post("/verify")
    def verify(req: AgentIdentityClaimRequest):
        if verifier is None or not trusted:
            raise HTTPException(
                status_code=503,
                detail="a2a_identity_verifier_not_activated",
            )

        claim = AgentIdentityClaim(
            agent_id=req.agent_id,
            key_id=req.key_id,
            nonce=req.nonce,
            issued_at=req.issued_at,
            signature=req.signature,
            requested_scope=req.requested_scope,
        )
        try:
            decision = verify_agent_identity(
                claim,
                verifier=verifier,
                trusted_key_ids=trusted,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return {
            "mode": "OBSERVE",
            "scope": decision.granted_scope,
            "execution_authority": "none",
            "commerce_execution": False,
            "payment_execution": False,
            "allocation_execution": False,
            "decision": decision.as_dict(),
        }

    return router
