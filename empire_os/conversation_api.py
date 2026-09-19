"""Conversation OS provider-event normalization preview API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from empire_os.conversation_ingest import normalise_provider_event


class ConversationEventPreviewRequest(BaseModel):
    provider: str
    conversation_id: str
    payload: dict[str, Any]


def create_conversation_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/conversations",
        tags=["conversation-os"],
    )

    @router.get("/health")
    def health():
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "provider_activation": False,
            "outbound_calls": False,
            "voice_streaming": False,
            "email_sends": False,
            "booking_execution": False,
        }

    @router.post("/events/preview")
    def event_preview(req: ConversationEventPreviewRequest):
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

    return router
