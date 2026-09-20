"""Dedicated PostgreSQL RPC transport for the governed closer roles."""
from __future__ import annotations

import json
from typing import Any, Callable

from empire_os.qualification_worker_v2 import request_json


class CloserTransportError(RuntimeError):
    pass


ROLE_FUNCTIONS = {
    "empire_closer_observer": {
        "list_closer_work": (
            "select public.list_closer_work(%s)",
            ("p_limit",),
        ),
    },
    "empire_closer_planner": {
        "list_closer_work": (
            "select public.list_closer_work(%s)",
            ("p_limit",),
        ),
        "open_closer_case": (
            "select public.open_closer_case(%s)",
            ("p_reply_id",),
        ),
        "provision_buyer_from_closer_case": (
            "select public.provision_buyer_from_closer_case(%s,%s)",
            ("p_case_id", "p_actor"),
        ),
        "get_closer_reply_context": (
            "select public.get_closer_reply_context(%s)",
            ("p_case_id",),
        ),
        "propose_closer_reply_intent": (
            "select public.propose_closer_reply_intent(%s,%s,%s,%s,%s,%s)",
            (
                "p_case_id",
                "p_subject",
                "p_body_text",
                "p_idempotency_key",
                "p_proposed_by",
                "p_expires_at",
            ),
        ),
        "record_closer_recommendation": (
            "select public.record_closer_recommendation(%s,%s,%s,%s::jsonb,%s,%s)",
            (
                "p_case_id",
                "p_type",
                "p_confidence",
                "p_rationale",
                "p_message",
                "p_model_key",
            ),
        ),
    },
    "empire_closer_approver": {
        "advance_closer_case": (
            "select public.advance_closer_case(%s,%s,%s,%s,%s)",
            (
                "p_case_id",
                "p_next_state",
                "p_actor",
                "p_fulfilment_order_id",
                "p_note",
            ),
        ),
    },
}


class PostgresCloserRpc:
    def __init__(
        self,
        dsn: str,
        role: str,
        *,
        connect_factory: Callable | None = None,
    ):
        self.dsn = str(dsn or "").strip()
        self.role = str(role or "").strip()
        if not self.dsn:
            raise CloserTransportError("dedicated closer database DSN required")
        if self.role not in ROLE_FUNCTIONS:
            raise CloserTransportError("unsupported closer database role")

        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise CloserTransportError(
                    "psycopg is required for closer role transport"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def __call__(self, name: str, params: dict[str, Any]) -> Any:
        allowed = ROLE_FUNCTIONS[self.role]
        if name not in allowed:
            raise CloserTransportError(
                f"{self.role} is not allowed to execute {name}"
            )

        sql, keys = allowed[name]
        if not isinstance(params, dict) or set(params) != set(keys):
            raise CloserTransportError("unexpected closer RPC parameters")

        values: list[Any] = []
        for key in keys:
            value = params[key]
            if key == "p_rationale":
                value = json.dumps(
                    value or {},
                    separators=(",", ":"),
                    sort_keys=True,
                )
            values.append(value)

        try:
            with self._connect(self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL ROLE " + self.role)
                    cursor.execute(sql, tuple(values))
                    row = cursor.fetchone()
        except Exception as exc:
            raise CloserTransportError(
                "dedicated closer database RPC failed"
            ) from exc

        if not row or len(row) != 1:
            raise CloserTransportError(
                "dedicated closer database RPC returned no result"
            )
        return row[0]


class SupabaseCloserRpc:
    """Narrow PostgREST bridge for closer roles already granted to service_role.

    This keeps the same per-role RPC allowlist and exposes no arbitrary SQL or
    table-write helper. Consequential closer state transitions remain excluded
    because service_role has no execute grant on advance_closer_case.
    """

    def __init__(
        self,
        role: str,
        *,
        request_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.role = str(role or "").strip()
        if self.role not in ROLE_FUNCTIONS:
            raise CloserTransportError("unsupported closer database role")
        if self.role == "empire_closer_approver":
            raise CloserTransportError(
                "closer approver requires dedicated governed transport"
            )
        self._request = request_factory or request_json

    def __call__(self, name: str, params: dict[str, Any]) -> Any:
        allowed = ROLE_FUNCTIONS[self.role]
        if name not in allowed:
            raise CloserTransportError(
                f"{self.role} is not allowed to execute {name}"
            )
        _, keys = allowed[name]
        if not isinstance(params, dict) or set(params) != set(keys):
            raise CloserTransportError("unexpected closer RPC parameters")
        return self._request(
            "POST",
            f"/rest/v1/rpc/{name}",
            payload=params,
        )
