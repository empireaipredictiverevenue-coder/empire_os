"""Fail-closed admission of original conversation/reply evidence sources.

A data row from outbound telemetry is not, by itself, an inbound reply.
The admission filter only controls which raw rows the existing immutable
identity/quarantine adjudicator examines. It does not authenticate replies,
resolve tenant identity, classify buyer intent or approve commercial action.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

CONVERSATION_DB_TABLES = frozenset({
    "public.outbound_replies",
    "public.inbound_replies",
    "public.empire_conversation_events",
})
# A conversation container identifies a thread, not an inbound message.
CONTEXT_DB_TABLES = frozenset({
    "public.empire_conversations",
    "public.outbound_intents",
})
DIRECT_REPLIES = frozenset({
    "inbound", "incoming", "reply_received", "received_reply",
    "inbound_reply", "inbound_message", "message_received",
})
EVENT_FIELDS = ("direction", "message_direction", "event_type", "type")
RUNTIME_SOURCE_TERMS = (
    "inbound", "reply", "conversation", "mailbox",
)


def _explicit_inbound(row: Mapping[str, Any]) -> bool:
    # Generic value "reply" or a sentiment label is not provider
    # message-direction proof. Only explicit received message events qualify.
    lower = {str(k).casefold(): v for k, v in row.items()}
    return any(
        isinstance(lower.get(k), str)
        and lower[k].strip().casefold() in DIRECT_REPLIES
        for k in EVENT_FIELDS
    )


def source_admission(source_name: str, row: Any) -> str:
    """Return an auditable disposition, never a trust/identity verdict."""
    if not isinstance(row, Mapping):
        return "NOT_AN_EVENT_MAPPING"
    source = source_name.strip().casefold()
    if source.startswith("public."):
        if source in CONTEXT_DB_TABLES:
            return "EXCLUDED_CONTEXT_ONLY_TABLE"
        if source == "public.empire_conversation_events":
            # A conversation event may be outgoing. Only incoming events
            # with original provider event ID qualify for message review.
            fields = {str(k).casefold(): v for k, v in row.items()}
            if (
                not _explicit_inbound(row)
                or not isinstance(fields.get("provider_event_id"), str)
                or not fields["provider_event_id"].strip()
            ):
                return "EXCLUDED_CONVERSATION_EVENT_NOT_ORIGINAL_INBOUND"
            return "CANDIDATE_FROM_ORIGINAL_INBOUND_EVENT"
        if source in CONVERSATION_DB_TABLES:
            return "CANDIDATE_FROM_CONVERSATION_TABLE"
        if source == "public.outbound_events":
            # Outbound telemetry is never inbound-message source authority.
            return "EXCLUDED_OUTBOUND_EVENT_TELEMETRY"
        return "EXCLUDED_UNRELATED_DATABASE_TABLE"
    if source.startswith("runtime/"):
        if not any(term in source for term in RUNTIME_SOURCE_TERMS):
            return "EXCLUDED_UNRELATED_RUNTIME_SNAPSHOT"
        if not _explicit_inbound(row):
            return "EXCLUDED_RUNTIME_NON_INBOUND"
        return "CANDIDATE_FROM_EXPLICIT_INBOUND_RUNTIME_EVENT"
    return "EXCLUDED_UNKNOWN_SOURCE"


def admit_candidate_rows(
    records: list[tuple[str, dict[str, Any]]],
) -> tuple[list[tuple[str, dict[str, Any]]], dict[str, Any]]:
    accepted = []
    reasons: Counter[str] = Counter()
    for source, row in records:
        disposition = source_admission(source, row)
        reasons[disposition] += 1
        if disposition.startswith("CANDIDATE_FROM_"):
            accepted.append((source, row))
    report = {
        "schema": "empire.conversation_source_admission.v1",
        "total_source_rows_examined": len(records),
        "admitted_conversation_candidate_rows": len(accepted),
        "excluded_nonmessage_rows": len(records) - len(accepted),
        "reason_counts": dict(sorted(reasons.items())),
        "admission_does_not_authenticate_buyer_intent": True,
        "missing_identity_records_remain_quarantined": True,
        "tenant_binding_established": False,
        "outbound_authorized": False,
        "execution_authority": "none",
    }
    return accepted, report
