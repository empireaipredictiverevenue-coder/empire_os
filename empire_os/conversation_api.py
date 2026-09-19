"""Conversation OS provider-event normalization and ingest API."""
from __future__ import annotations

from typing import Any, Protocol

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from empire_os.conversation_ingest import normalise_provider_event
from empire_os.conversation_os import ConversationEventRecord
from empire_os.conversation_qualification import (
    review_conversation_qualification,
)
from empire_os.conversation_timeline import summarise_conversation_timeline


class ConversationReadRepository(Protocol):
    def timeline(
        self,
        *,
        conversation_id: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        ...

    def conversation(
        self,
        *,
        conversation_id: str,
    ) -> dict[str, Any] | None:
        ...


class ConversationEventRepository(Protocol):
    def append(
        self,
        *,
        provider: str,
        external_conversation_id: str,
        event: ConversationEventRecord,
    ) -> dict[str, Any]:
        ...


class ConversationEventPreviewRequest(BaseModel):
    provider: str
    conversation_id: str
    payload: dict[str, Any]


def create_conversation_router(
    repository: ConversationEventRepository | None = None,
    read_repository: ConversationReadRepository | None = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/conversations",
        tags=["conversation-os"],
    )

    def normalize(req: ConversationEventPreviewRequest):
        try:
            provider_event = normalise_provider_event(
                req.provider,
                req.payload,
            )
            event = provider_event.to_conversation_event(
                req.conversation_id
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return provider_event, event

    @router.get("/health")
    def health():
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "provider_activation": False,
            "provider_ingest_configured": repository is not None,
            "reader_configured": read_repository is not None,
            "outbound_calls": False,
            "voice_streaming": False,
            "email_sends": False,
            "booking_execution": False,
        }

    @router.get("/{conversation_id}/timeline")
    def timeline(conversation_id: str, limit: int = 200):
        if read_repository is None:
            raise HTTPException(
                status_code=503,
                detail="conversation_reader_not_activated",
            )
        bounded = max(1, min(int(limit), 500))
        conversation = read_repository.conversation(
            conversation_id=conversation_id
        )
        if conversation is None:
            raise HTTPException(
                status_code=404,
                detail="conversation_not_found",
            )
        rows = list(read_repository.timeline(
            conversation_id=conversation_id,
            limit=bounded,
        ))
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "execution_authority": "none",
            "conversation": dict(conversation),
            "count": len(rows),
            "limit": bounded,
            "events": [dict(row) for row in rows],
        }

    @router.get("/{conversation_id}/summary")
    def summary(conversation_id: str, limit: int = 200):
        if read_repository is None:
            raise HTTPException(
                status_code=503,
                detail="conversation_reader_not_activated",
            )
        bounded = max(1, min(int(limit), 500))
        conversation = read_repository.conversation(
            conversation_id=conversation_id
        )
        if conversation is None:
            raise HTTPException(
                status_code=404,
                detail="conversation_not_found",
            )
        rows = list(read_repository.timeline(
            conversation_id=conversation_id,
            limit=bounded,
        ))
        result = summarise_conversation_timeline(
            rows,
            conversation_id=conversation_id,
        )
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "execution_authority": "none",
            "summary": result.as_dict(),
        }

    @router.get("/{conversation_id}/qualification")
    def qualification(conversation_id: str, limit: int = 200):
        if read_repository is None:
            raise HTTPException(
                status_code=503,
                detail="conversation_reader_not_activated",
            )
        bounded = max(1, min(int(limit), 500))
        conversation = read_repository.conversation(
            conversation_id=conversation_id
        )
        if conversation is None:
            raise HTTPException(
                status_code=404,
                detail="conversation_not_found",
            )
        rows = list(read_repository.timeline(
            conversation_id=conversation_id,
            limit=bounded,
        ))
        try:
            review = review_conversation_qualification(
                rows,
                conversation_id=conversation_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "execution_authority": "none",
            "outbound_calls": False,
            "voice_streaming": False,
            "email_sends": False,
            "booking_execution": False,
            "qualification": review.as_dict(),
        }

    @router.post("/events/preview")
    def event_preview(req: ConversationEventPreviewRequest):
        provider_event, event = normalize(req)
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "provider_activation": False,
            "write_authority": "none",
            "provider_event": {
                "provider": provider_event.provider,
                "external_conversation_id": (
                    provider_event.external_conversation_id
                ),
                "provider_event_id": provider_event.provider_event_id,
                "event_type": provider_event.event_type,
                "direction": provider_event.direction.value,
                "occurred_at": provider_event.occurred_at,
            },
            "canonical_event": event.as_dict(),
        }

    @router.post("/events/ingest")
    def event_ingest(req: ConversationEventPreviewRequest):
        if repository is None:
            raise HTTPException(
                status_code=503,
                detail="conversation_provider_ingest_not_activated",
            )
        provider_event, event = normalize(req)
        result = repository.append(
            provider=provider_event.provider,
            external_conversation_id=(
                provider_event.external_conversation_id
            ),
            event=event,
        )
        status = str(result.get("status") or "").strip()
        if status == "conflict":
            raise HTTPException(
                status_code=409,
                detail=str(
                    result.get("reason")
                    or "conversation_provider_event_conflict"
                ),
            )
        if status not in {"recorded", "existing"}:
            raise HTTPException(
                status_code=502,
                detail="conversation_ingest_invalid_repository_result",
            )
        return {
            "mode": "OBSERVE",
            "status": status,
            "event_id": result.get("event_id"),
            "conversation_id": event.conversation_id,
            "provider": provider_event.provider,
            "provider_event_id": provider_event.provider_event_id,
            "write_authority": "append_only_event",
            "provider_activation": False,
            "execution_authority": "none",
            "outbound_calls": False,
            "voice_streaming": False,
            "email_sends": False,
            "booking_execution": False,
        }

    return router
