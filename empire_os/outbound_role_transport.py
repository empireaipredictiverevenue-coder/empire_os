"""Direct PostgreSQL transport for separated Phase 3E outbound roles.

No credentials are stored here. A login DSN is supplied at runtime and the
connection SET LOCAL ROLEs into one NOLOGIN permission role per transaction.
"""
from __future__ import annotations

from typing import Any, Callable

from empire_os.outbound_provider import OutboundProviderError
from empire_os.qualification_worker_v2 import request_json

ROLE_FUNCTIONS = {
    "empire_outbound_approver": {
        "approve_outbound_intent": (
            "select public.approve_outbound_intent(%s,%s,%s)",
            ("p_intent_id", "p_approved_by", "p_note"),
        ),
        "cancel_outbound_intent": (
            "select public.cancel_outbound_intent(%s,%s,%s)",
            ("p_intent_id", "p_cancelled_by", "p_reason"),
        ),
    },
    "empire_outbound_sender": {
        "get_outbound_intent_review": (
            "select public.get_outbound_intent_review(%s)",
            ("p_intent_id",),
        ),
        "get_outbound_governor_context": (
            "select public.get_outbound_governor_context(%s)",
            ("p_intent_id",),
        ),
        "list_outbound_governor_work": (
            "select public.list_outbound_governor_work(%s)",
            ("p_limit",),
        ),
        "claim_outbound_send": (
            "select public.claim_outbound_send(%s,%s)",
            ("p_intent_id", "p_actor"),
        ),
        "record_outbound_delivery": (
            "select public.record_outbound_delivery(%s,%s,%s,%s,%s::jsonb)",
            ("p_intent_id", "p_event_type", "p_actor", "p_provider_message_id", "p_payload"),
        ),
    },
    "empire_reply_ingest": {
        "ingest_outbound_reply": (
            "select public.ingest_outbound_reply(%s,%s,%s,%s,%s,%s,%s::jsonb)",
            ("p_intent_id", "p_provider_message_id", "p_from_contact", "p_subject", "p_body_text", "p_received_at", "p_metadata"),
        ),
        "classify_outbound_reply": (
            "select public.classify_outbound_reply(%s,%s,%s,%s)",
            ("p_reply_id", "p_classification", "p_confidence", "p_actor"),
        ),
        "record_outbound_provider_event": (
            "select public.record_outbound_provider_event(%s,%s,%s,%s,%s,%s::jsonb)",
            (
                "p_intent_id", "p_event_type", "p_provider_message_id",
                "p_recipient", "p_suppress", "p_payload",
            ),
        ),
    },
}


class PostgresOutboundRpc:
    def __init__(self, dsn: str, role: str, *, connect_factory: Callable | None = None):
        self.dsn = str(dsn or "").strip()
        self.role = role
        if not self.dsn:
            raise OutboundProviderError("dedicated outbound database DSN required")
        if role not in ROLE_FUNCTIONS:
            raise OutboundProviderError("unsupported outbound database role")
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise OutboundProviderError("psycopg is required for outbound role transport") from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def __call__(self, name: str, params: dict[str, Any]) -> Any:
        allowed = ROLE_FUNCTIONS[self.role]
        if name not in allowed:
            raise OutboundProviderError(f"{self.role} is not allowed to execute {name}")
        sql, keys = allowed[name]
        if not isinstance(params, dict) or set(params) != set(keys):
            raise OutboundProviderError("unexpected outbound RPC parameters")
        values = []
        for key in keys:
            value = params[key]
            if key in {"p_payload", "p_metadata"}:
                import json
                value = json.dumps(value or {}, separators=(",", ":"), sort_keys=True)
            values.append(value)
        try:
            with self._connect(self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL ROLE " + self.role)
                    cursor.execute(sql, tuple(values))
                    row = cursor.fetchone()
        except Exception as exc:
            raise OutboundProviderError("dedicated outbound database RPC failed") from exc
        if not row or len(row) != 1:
            raise OutboundProviderError("dedicated outbound database RPC returned no result")
        return row[0]


class SupabaseOutboundRpc:
    """Narrow PostgREST transport using the existing protected service key.

    The local role name remains an allowlist boundary: only RPC names already
    assigned to that Phase 3E role may be called. This is a runtime bridge for
    environments where dedicated Postgres LOGIN credentials are not yet
    provisioned; it does not add table-write helpers or arbitrary SQL.
    """

    def __init__(
        self,
        role: str,
        *,
        request_factory: Callable[..., Any] | None = None,
    ):
        if role not in ROLE_FUNCTIONS:
            raise OutboundProviderError("unsupported outbound database role")
        self.role = role
        self._request = request_factory or request_json

    def __call__(self, name: str, params: dict[str, Any]) -> Any:
        allowed = ROLE_FUNCTIONS[self.role]
        if name not in allowed:
            raise OutboundProviderError(
                f"{self.role} is not allowed to execute {name}"
            )
        _, keys = allowed[name]
        if not isinstance(params, dict) or set(params) != set(keys):
            raise OutboundProviderError(
                "unexpected outbound RPC parameters"
            )
        return self._request(
            "POST",
            f"/rest/v1/rpc/{name}",
            payload=params,
        )


class SupabaseStandingAuthorityApproverRpc:
    """Service-role bridge to the database-enforced standing-authority gate.

    It intentionally exposes only automatic intent approval. The database RPC
    rechecks evidence, suppression, content compliance, offer scope, freshness,
    and the daily cap before delegating to approve_outbound_intent.
    """

    def __init__(
        self,
        *,
        daily_cap: int = 10,
        request_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.daily_cap = max(1, min(int(daily_cap), 50))
        self._request = request_factory or request_json

    def __call__(self, name: str, params: dict[str, Any]) -> Any:
        if name != "approve_outbound_intent":
            raise OutboundProviderError(
                "standing-authority bridge only supports outbound approval"
            )
        expected = {"p_intent_id", "p_approved_by", "p_note"}
        if not isinstance(params, dict) or set(params) != expected:
            raise OutboundProviderError(
                "unexpected standing-authority approval parameters"
            )
        intent_id = params["p_intent_id"]
        rows = self._request(
            "GET",
            "/rest/v1/outbound_intents"
            f"?select=metadata&id=eq.{intent_id}&limit=1",
        ) or []
        metadata = (rows[0].get("metadata") or {}) if rows else {}
        rpc_name = (
            "auto_approve_outbound_followup"
            if isinstance(metadata, dict)
            and metadata.get("sequence_kind") == "followup"
            else "auto_approve_outbound_intent"
        )
        return self._request(
            "POST",
            f"/rest/v1/rpc/{rpc_name}",
            payload={
                "p_intent_id": intent_id,
                "p_daily_cap": self.daily_cap,
            },
        )
