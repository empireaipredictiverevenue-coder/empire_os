"""Phase 7 Conversation OS read-model foundation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping


class ConversationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    VOICE = "voice"
    A2A = "a2a"


class ConversationDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    INTERNAL = "internal"


@dataclass(frozen=True)
class ConversationRecord:
    id: str
    channel: ConversationChannel
    state: str
    prospect_id: str | None = None
    entity_id: str | None = None
    buyer_id: str | None = None
    opportunity_id: str | None = None
    closer_case_id: str | None = None
    external_conversation_id: str | None = None
    opened_at: str | None = None
    updated_at: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["channel"] = self.channel.value
        return data
@dataclass(frozen=True)
class ConversationEventRecord:
    conversation_id: str
    event_type: str
    direction: ConversationDirection
    occurred_at: str
    actor: str | None = None
    text: str | None = None
    provider_event_id: str | None = None
    evidence: Mapping[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["direction"] = self.direction.value
        data["evidence"] = dict(self.evidence or {})
        return data


def normalise_conversation_row(row: Mapping[str, Any]) -> ConversationRecord:
    channel = ConversationChannel(str(row.get("channel") or "").strip().lower())
    conversation_id = str(row.get("id") or "").strip()
    state = str(row.get("state") or "").strip()
    if not conversation_id or not state:
        raise ValueError("conversation id and state are required")
    if not any(
        row.get(name)
        for name in ("prospect_id", "entity_id", "buyer_id", "closer_case_id")
    ):
        raise ValueError("conversation requires a canonical participant or closer case")
    return ConversationRecord(
        id=conversation_id,
        channel=channel,
        state=state,
        prospect_id=row.get("prospect_id"),
        entity_id=row.get("entity_id"),
        buyer_id=row.get("buyer_id"),
        opportunity_id=row.get("opportunity_id"),
        closer_case_id=row.get("closer_case_id"),
        external_conversation_id=row.get("external_conversation_id"),
        opened_at=row.get("opened_at"),
        updated_at=row.get("updated_at"),
    )
