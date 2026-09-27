"""Dedicated PostgreSQL transport for Phase 6 A2A intent capture."""
from __future__ import annotations

import json
from typing import Any, Callable

from empire_os.a2a_commerce_intent import CommercialIntent


class A2ACommerceTransportError(RuntimeError):
    pass


RPC_NAME = "record_a2a_commercial_intent"
ROLE = "empire_a2a_intent_writer"
SQL = (
    "select public.record_a2a_commercial_intent("
    "%s,%s,%s,%s::timestamptz,%s,%s,%s::jsonb,%s::jsonb)"
)
PARAM_KEYS = (
    "p_agent_id",
    "p_key_id",
    "p_identity_nonce",
    "p_identity_issued_at",
    "p_capability",
    "p_idempotency_key",
    "p_request",
    "p_evidence",
)


class PostgresA2AIntentRpc:
    def __init__(
        self,
        dsn: str,
        *,
        connect_factory: Callable | None = None,
    ) -> None:
        self.dsn = str(dsn or "").strip()
        if not self.dsn:
            raise A2ACommerceTransportError(
                "dedicated A2A intent database DSN required"
            )
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise A2ACommerceTransportError(
                    "psycopg is required for A2A intent transport"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def __call__(self, name: str, params: dict[str, Any]) -> Any:
        if name != RPC_NAME:
            raise A2ACommerceTransportError(
                "A2A intent role cannot execute this RPC"
            )
        if not isinstance(params, dict) or set(params) != set(PARAM_KEYS):
            raise A2ACommerceTransportError(
                "unexpected A2A intent RPC parameters"
            )
        values = []
        for key in PARAM_KEYS:
            value = params[key]
            if key in {"p_request", "p_evidence"}:
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
            raise A2ACommerceTransportError(
                "dedicated A2A intent database RPC failed"
            ) from exc
        if not row or len(row) != 1:
            raise A2ACommerceTransportError(
                "dedicated A2A intent database RPC returned no result"
            )
        return row[0]


class RpcCommercialIntentRepository:
    def __init__(self, rpc: Callable[[str, dict[str, Any]], Any]):
        self.rpc = rpc

    def record(self, *, intent: CommercialIntent):
        intent.validate()
        result = self.rpc(
            RPC_NAME,
            {
                "p_agent_id": intent.agent_id,
                "p_key_id": intent.key_id,
                "p_identity_nonce": intent.identity_nonce,
                "p_identity_issued_at": intent.identity_issued_at,
                "p_capability": intent.capability,
                "p_idempotency_key": intent.idempotency_key,
                "p_request": dict(intent.request),
                "p_evidence": dict(intent.evidence),
            },
        )
        if not isinstance(result, dict):
            raise A2ACommerceTransportError(
                "A2A intent RPC returned invalid payload"
            )
        return result
