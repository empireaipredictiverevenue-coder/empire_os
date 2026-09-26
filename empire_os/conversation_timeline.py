"""Phase 7 read-only conversation timeline and summary."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from empire_os.conversation_os import (
    ConversationDirection,
    ConversationEventRecord,
)


@dataclass(frozen=True)
class ConversationTimelineSummary:
    conversation_id: str
    event_count: int
    inbound_events: int
    outbound_events: int
    internal_events: int
    first_observed_at: str | None
    last_observed_at: str | None
    latest_event_type: str | None
    latest_direction: str | None
    latest_text: str | None
    qualification_signal: str
    blockers: tuple[str, ...]
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _event_from_row(row: Mapping[str, Any]) -> ConversationEventRecord:
    direction = ConversationDirection(
        str(row.get("direction") or "").strip().lower()
    )
    conversation_id = str(row.get("conversation_id") or "").strip()
    event_type = str(row.get("event_type") or "").strip()
    occurred_at = str(row.get("occurred_at") or "").strip()
    if not conversation_id or not event_type or not occurred_at:
        raise ValueError(
            "conversation_id, event_type and occurred_at are required"
        )
    return ConversationEventRecord(
        conversation_id=conversation_id,
        event_type=event_type,
        direction=direction,
        occurred_at=occurred_at,
        actor=row.get("actor"),
        text=row.get("body_text", row.get("text")),
        provider_event_id=row.get("provider_event_id"),
        evidence=dict(row.get("evidence") or {}),
    )

def summarise_conversation_timeline(
    rows: Sequence[Mapping[str, Any]],
    *,
    conversation_id: str,
) -> ConversationTimelineSummary:
    cid = str(conversation_id or "").strip()
    if not cid:
        raise ValueError("conversation_id required")

    events = tuple(_event_from_row(row) for row in rows)
    if any(event.conversation_id != cid for event in events):
        raise ValueError("conversation timeline contains mixed identities")

    ordered = tuple(sorted(events, key=lambda item: item.occurred_at))
    inbound = sum(
        event.direction is ConversationDirection.INBOUND
        for event in ordered
    )
    outbound = sum(
        event.direction is ConversationDirection.OUTBOUND
        for event in ordered
    )
    internal = sum(
        event.direction is ConversationDirection.INTERNAL
        for event in ordered
    )

    blockers: list[str] = []
    if not ordered:
        signal = "no_observed_events"
        blockers.append("conversation_event_evidence_missing")
    elif inbound > 0:
        signal = "observed_inbound_response"
    elif outbound > 0:
        signal = "outbound_only_no_observed_response"
        blockers.append("inbound_response_not_observed")
    else:
        signal = "internal_only"
        blockers.append("external_conversation_evidence_missing")

    latest = ordered[-1] if ordered else None
    return ConversationTimelineSummary(
        conversation_id=cid,
        event_count=len(ordered),
        inbound_events=inbound,
        outbound_events=outbound,
        internal_events=internal,
        first_observed_at=ordered[0].occurred_at if ordered else None,
        last_observed_at=latest.occurred_at if latest else None,
        latest_event_type=latest.event_type if latest else None,
        latest_direction=latest.direction.value if latest else None,
        latest_text=latest.text if latest else None,
        qualification_signal=signal,
        blockers=tuple(blockers),
    )
