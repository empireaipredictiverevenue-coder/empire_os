"""Dedicated append-only provider-event transport for Conversation OS."""
from __future__ import annotations

import json
from typing import Any, Callable

from empire_os.conversation_os import ConversationEventRecord


class ConversationTransportError(RuntimeError):
    pass


RPC_NAME = "ingest_conversation_provider_event"
ROLE = "empire_conversation_ingest"
SQL = (
    "select public.ingest_conversation_provider_event("
    "%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)"
)
PARAM_KEYS = (
    "p_conversation_id",
    "p_provider",
    "p_external_conversation_id",
    "p_provider_event_id",
    "p_event_type",
    "p_direction",
    "p_actor",
    "p_body_text",
    "p_evidence",
    "p_occurred_at",
)


class PostgresConversationIngestRpc:
    def __init__(
        self,
        dsn: str,
        *,
        connect_factory: Callable | None = None,
    ) -> None:
        self.dsn = str(dsn or "").strip()
        if not self.dsn:
            raise ConversationTransportError(
                "dedicated conversation ingest DSN required"
            )
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise ConversationTransportError(
                    "psycopg is required for conversation ingest"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def __call__(self, name: str, params: dict[str, Any]) -> Any:
        if name != RPC_NAME:
            raise ConversationTransportError(
                "conversation ingest role cannot execute this RPC"
            )
        if not isinstance(params, dict) or set(params) != set(PARAM_KEYS):
            raise ConversationTransportError(
                "unexpected conversation ingest RPC parameters"
            )
        values = []
        for key in PARAM_KEYS:
            value = params[key]
            if key == "p_evidence":
                value = json.dumps(
                    value or {},
                    separators=(",", ":"),
                    sort_keys=True,
                )
            values.append(value)
        try:
            with self._connect(self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL ROLE " + ROLE)
                    cursor.execute(SQL, tuple(values))
                    row = cursor.fetchone()
        except Exception as exc:
            raise ConversationTransportError(
                "conversation ingest RPC failed"
            ) from exc
        if not row or len(row) != 1:
            raise ConversationTransportError(
                "conversation ingest RPC returned no result"
            )
        return row[0]


class RpcConversationEventRepository:
    def __init__(self, rpc: Callable[[str, dict[str, Any]], Any]):
        self.rpc = rpc

    def append(
        self,
        *,
        provider: str,
        external_conversation_id: str,
        event: ConversationEventRecord,
    ):
        payload = self.rpc(
            RPC_NAME,
            {
                "p_conversation_id": event.conversation_id,
                "p_provider": provider,
                "p_external_conversation_id": external_conversation_id,
                "p_provider_event_id": event.provider_event_id,
                "p_event_type": event.event_type,
                "p_direction": event.direction.value,
                "p_actor": event.actor,
                "p_body_text": event.text,
                "p_evidence": dict(event.evidence or {}),
                "p_occurred_at": event.occurred_at,
            },
        )
        if not isinstance(payload, dict):
            raise ConversationTransportError(
                "conversation ingest RPC returned invalid payload"
            )
        return payload
