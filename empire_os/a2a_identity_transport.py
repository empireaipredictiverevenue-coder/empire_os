"""Dedicated PostgreSQL transport for A2A identity nonce consumption."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable


class A2AIdentityTransportError(RuntimeError):
    pass


RPC_NAME = "consume_a2a_identity_nonce"
ROLE = "empire_a2a_identity_nonce_writer"
SQL = (
    "select public.consume_a2a_identity_nonce("
    "%s,%s,%s,%s::timestamptz)"
)
PARAM_KEYS = (
    "p_agent_id",
    "p_key_id",
    "p_nonce",
    "p_issued_at",
)


class PostgresA2AIdentityNonceRpc:
    def __init__(
        self,
        dsn: str,
        *,
        connect_factory: Callable | None = None,
    ) -> None:
        self.dsn = str(dsn or "").strip()
        if not self.dsn:
            raise A2AIdentityTransportError(
                "dedicated A2A identity database DSN required"
            )
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise A2AIdentityTransportError(
                    "psycopg is required for A2A identity transport"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def __call__(self, name: str, params: dict[str, Any]) -> Any:
        if name != RPC_NAME:
            raise A2AIdentityTransportError(
                "A2A identity role cannot execute this RPC"
            )
        if not isinstance(params, dict) or set(params) != set(PARAM_KEYS):
            raise A2AIdentityTransportError(
                "unexpected A2A identity RPC parameters"
            )
        issued_at = str(params["p_issued_at"] or "").strip()
        if not issued_at:
            raise A2AIdentityTransportError("issued_at required")
        try:
            datetime.fromisoformat(issued_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise A2AIdentityTransportError(
                "issued_at must be ISO-8601"
            ) from exc

        values = tuple(params[key] for key in PARAM_KEYS)
        try:
            with self._connect(self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL ROLE " + ROLE)
                    cursor.execute(SQL, values)
                    row = cursor.fetchone()
        except Exception as exc:
            raise A2AIdentityTransportError(
                "dedicated A2A identity database RPC failed"
            ) from exc
        if not row or len(row) != 1 or not isinstance(row[0], bool):
            raise A2AIdentityTransportError(
                "dedicated A2A identity RPC returned invalid payload"
            )
        return row[0]


class RpcNonceRegistry:
    def __init__(self, rpc: Callable[[str, dict[str, Any]], Any]):
        self.rpc = rpc

    def consume(
        self,
        *,
        agent_id: str,
        key_id: str,
        nonce: str,
        issued_at: str,
    ) -> bool:
        result = self.rpc(
            RPC_NAME,
            {
                "p_agent_id": agent_id,
                "p_key_id": key_id,
                "p_nonce": nonce,
                "p_issued_at": issued_at,
            },
        )
        if not isinstance(result, bool):
            raise A2AIdentityTransportError(
                "A2A identity RPC returned non-boolean result"
            )
        return result
