"""Fail-closed Recall.ai webhook ingress API.

This router verifies the raw request before any payload processing and hands the
verified envelope to an injected queue/dispatcher. It performs no business
mutation itself and is not mounted by default.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from fastapi import APIRouter, HTTPException, Request

from empire_os.recall_webhook_verification import (
    RecallVerificationEvidence,
    verify_recall_request,
)


@dataclass(frozen=True)
class VerifiedRecallEnvelope:
    raw_payload: bytes
    headers: Mapping[str, str]
    verification: RecallVerificationEvidence
    received_at: str | None = None

    def metadata(self) -> dict[str, Any]:
        return {
            "verification": self.verification.as_dict(),
            "payload_size_bytes": len(self.raw_payload),
            "received_at": self.received_at,
            "raw_payload_persisted_here": False,
            "execution_authority": "none",
        }


SecretProvider = Callable[[], str]
VerifiedEnvelopeSink = Callable[[VerifiedRecallEnvelope], Any]


def create_recall_webhook_router(
    *,
    secret_provider: SecretProvider,
    verified_envelope_sink: VerifiedEnvelopeSink,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/providers/recall",
        tags=["recall-webhook"],
    )

    @router.post("/realtime")
    async def realtime(request: Request):
        try:
            secret = str(secret_provider() or "").strip()
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="recall_verification_secret_unavailable",
            ) from exc
        if not secret:
            raise HTTPException(
                status_code=503,
                detail="recall_verification_secret_unavailable",
            )

        raw_payload = await request.body()
        headers = {
            str(key).lower(): str(value)
            for key, value in request.headers.items()
        }
        try:
            verification = verify_recall_request(
                secret=secret,
                headers=headers,
                raw_payload=raw_payload,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=401,
                detail="recall_webhook_verification_failed",
            ) from exc


        received_at = datetime.fromtimestamp(
            int(verification.webhook_timestamp),
            tz=timezone.utc,
        ).isoformat()
        envelope = VerifiedRecallEnvelope(
            raw_payload=raw_payload,
            headers=headers,
            verification=verification,
            received_at=received_at,
        )
        try:
            verified_envelope_sink(envelope)
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="recall_verified_event_queue_unavailable",
            ) from exc

        return {
            "accepted": True,
            "verified": True,
            "processed_inline": False,
            "execution_authority": "none",
        }

    return router
