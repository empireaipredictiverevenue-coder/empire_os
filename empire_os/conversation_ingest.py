"""Read-only provider event normalizers for Conversation OS."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from empire_os.conversation_os import ConversationDirection, ConversationEventRecord


SUPPORTED_PROVIDERS = frozenset({"vonage", "elevenlabs", "email", "a2a"})


@dataclass(frozen=True)
class ProviderConversationEvent:
    provider: str
    external_conversation_id: str
    provider_event_id: str
    event_type: str
    direction: ConversationDirection
    occurred_at: str
    actor: str | None = None
    text: str | None = None
    evidence: Mapping[str, Any] | None = None

    def validate(self) -> None:
        if self.provider not in SUPPORTED_PROVIDERS:
            raise ValueError("unsupported conversation provider")
        for name, value in (
            ("external_conversation_id", self.external_conversation_id),
            ("provider_event_id", self.provider_event_id),
            ("event_type", self.event_type),
            ("occurred_at", self.occurred_at),
        ):
            if not str(value or "").strip():
                raise ValueError(f"{name} required")

    def to_conversation_event(
        self,
        conversation_id: str,
    ) -> ConversationEventRecord:
        self.validate()
        cid = str(conversation_id or "").strip()
        if not cid:
            raise ValueError("canonical conversation_id required")
        evidence = dict(self.evidence or {})
        evidence.setdefault("provider", self.provider)
        evidence.setdefault(
            "external_conversation_id",
            self.external_conversation_id,
        )
        return ConversationEventRecord(
            conversation_id=cid,
            event_type=self.event_type,
            direction=self.direction,
            occurred_at=self.occurred_at,
            actor=self.actor,
            text=self.text,
            provider_event_id=self.provider_event_id,
            evidence=evidence,
        )
def _direction(value: Any) -> ConversationDirection:
    text = str(value or "").strip().lower()
    aliases = {
        "inbound": ConversationDirection.INBOUND,
        "incoming": ConversationDirection.INBOUND,
        "outbound": ConversationDirection.OUTBOUND,
        "outgoing": ConversationDirection.OUTBOUND,
        "internal": ConversationDirection.INTERNAL,
    }
    if text not in aliases:
        raise ValueError("unsupported conversation direction")
    return aliases[text]


def normalise_provider_event(
    provider: str,
    payload: Mapping[str, Any],
) -> ProviderConversationEvent:
    name = str(provider or "").strip().lower()
    if name not in SUPPORTED_PROVIDERS:
        raise ValueError("unsupported conversation provider")
    if not isinstance(payload, Mapping):
        raise ValueError("provider event payload must be a mapping")

    field_maps = {
        "vonage": {
            "conversation": "conversation_uuid",
            "event": "event_uuid",
            "type": "event_type",
            "time": "timestamp",
            "direction": "direction",
            "text": "text",
        },
        "elevenlabs": {
            "conversation": "conversation_id",
            "event": "event_id",
            "type": "event_type",
            "time": "occurred_at",
            "direction": "direction",
            "text": "transcript_text",
        },
        "email": {
            "conversation": "thread_id",
            "event": "message_id",
            "type": "event_type",
            "time": "occurred_at",
            "direction": "direction",
            "text": "body_text",
        },
        "a2a": {
            "conversation": "context_id",
            "event": "message_id",
            "type": "event_type",
            "time": "occurred_at",
            "direction": "direction",
            "text": "text",
        },
    }
    mapping = field_maps[name]
    event = ProviderConversationEvent(
        provider=name,
        external_conversation_id=str(
            payload.get(mapping["conversation"]) or ""
        ).strip(),
        provider_event_id=str(
            payload.get(mapping["event"]) or ""
        ).strip(),
        event_type=str(payload.get(mapping["type"]) or "").strip(),
        direction=_direction(payload.get(mapping["direction"])),
        occurred_at=str(payload.get(mapping["time"]) or "").strip(),
        actor=(
            str(payload.get("actor")).strip()
            if payload.get("actor") is not None
            else None
        ),
        text=(
            str(payload.get(mapping["text"])).strip()
            if payload.get(mapping["text"]) is not None
            else None
        ),
        evidence={"raw_kind": name},
    )
    event.validate()
    return event
