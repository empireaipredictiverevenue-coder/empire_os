"""Canonical prospect-consent API contract."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Protocol

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


class ConsentRepository(Protocol):
    def current(
        self,
        *,
        prospect_id: str,
        channel: str,
    ) -> Mapping[str, Any] | None:
        ...

    def record(
        self,
        *,
        prospect_id: str,
        channel: str,
        decision: str,
        source: str,
        evidence: Mapping[str, Any],
        occurred_at: str,
    ) -> Mapping[str, Any]:
        ...


class ConsentDecisionRequest(BaseModel):
    channel: str = Field(default="email")
    source: str = Field(default="user_opt_in")
    evidence: dict[str, Any] = Field(default_factory=dict)


def create_consent_router(
    repository: ConsentRepository | None = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/consent",
        tags=["consent"],
    )

    def require_repository() -> ConsentRepository:
        if repository is None:
            raise HTTPException(
                status_code=503,
                detail="canonical_consent_repository_not_activated",
            )
        return repository

    def validate_channel(channel: str) -> str:
        value = str(channel or "").strip().lower()
        if value not in {"email", "sms", "voice", "a2a"}:
            raise HTTPException(
                status_code=422,
                detail="unsupported_consent_channel",
            )
        return value

    @router.get("/health")
    def health():
        return {
            "mode": "GOVERNED",
            "append_only": True,
            "outbound_execution": False,
            "repository_available": repository is not None,
        }

    @router.get("/prospects/{prospect_id}")
    def current(prospect_id: str, channel: str = "email"):
        repo = require_repository()
        normalized = validate_channel(channel)
        row = repo.current(
            prospect_id=prospect_id,
            channel=normalized,
        )
        if row is None:
            return {
                "known": False,
                "prospect_id": prospect_id,
                "channel": normalized,
                "decision": None,
            }
        return {
            "known": True,
            "prospect_id": prospect_id,
            "channel": normalized,
            "consent": dict(row),
        }

    @router.post("/prospects/{prospect_id}/opt-in")
    def opt_in(prospect_id: str, req: ConsentDecisionRequest):
        repo = require_repository()
        channel = validate_channel(req.channel)
        result = repo.record(
            prospect_id=prospect_id,
            channel=channel,
            decision="granted",
            source=str(req.source or "user_opt_in"),
            evidence=dict(req.evidence),
            occurred_at=datetime.now(timezone.utc).isoformat(),
        )
        return {
            "ok": True,
            "prospect_id": prospect_id,
            "channel": channel,
            "decision": "granted",
            "outbound_execution": False,
            "consent_event": dict(result),
        }

    @router.post("/prospects/{prospect_id}/revoke")
    def revoke(prospect_id: str, req: ConsentDecisionRequest):
        repo = require_repository()
        channel = validate_channel(req.channel)
        result = repo.record(
            prospect_id=prospect_id,
            channel=channel,
            decision="revoked",
            source=str(req.source or "user_revoke"),
            evidence=dict(req.evidence),
            occurred_at=datetime.now(timezone.utc).isoformat(),
        )
        return {
            "ok": True,
            "prospect_id": prospect_id,
            "channel": channel,
            "decision": "revoked",
            "outbound_execution": False,
            "consent_event": dict(result),
        }

    return router
