"""Dedicated Phase 16 SaaS readiness registry transport."""
from __future__ import annotations

import json
from typing import Any, Callable

from empire_os.saas_registry import SaasReadinessRecord


class SaasRegistryTransportError(RuntimeError):
    pass


RPC_NAME = "record_saas_readiness"
ROLE = "empire_saas_registry_writer"
SQL = (
    "select public.record_saas_readiness("
    "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)"
)
PARAM_KEYS = (
    "p_readiness_key",
    "p_tenant_id",
    "p_active_members",
    "p_observed_monthly_usage",
    "p_observed_usage_limit",
    "p_active_subscription",
    "p_tenant_isolation_verified",
    "p_white_label_requested",
    "p_white_label_configured",
    "p_evidence_refs",
    "p_evidence",
)


class PostgresSaasRegistryRpc:
    def __init__(
        self,
        dsn: str,
        *,
        connect_factory: Callable | None = None,
    ) -> None:
        self.dsn = str(dsn or "").strip()
        if not self.dsn:
            raise SaasRegistryTransportError(
                "dedicated SaaS registry DSN required"
            )
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise SaasRegistryTransportError(
                    "psycopg is required for SaaS registry"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def __call__(self, name: str, params: dict[str, Any]) -> Any:
        if name != RPC_NAME:
            raise SaasRegistryTransportError(
                "SaaS registry role cannot execute this RPC"
            )
        if not isinstance(params, dict) or set(params) != set(PARAM_KEYS):
            raise SaasRegistryTransportError(
                "unexpected SaaS registry RPC parameters"
            )
        values = []
        for key in PARAM_KEYS:
            value = params[key]
            if key in {"p_evidence_refs", "p_evidence"}:
                value = json.dumps(
                    value or ([] if key == "p_evidence_refs" else {}),
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
            raise SaasRegistryTransportError(
                "SaaS registry RPC failed"
            ) from exc
        if not row or len(row) != 1:
            raise SaasRegistryTransportError(
                "SaaS registry RPC returned no result"
            )
        return row[0]


class RpcSaasRegistryRepository:
    def __init__(self, rpc: Callable[[str, dict[str, Any]], Any]):
        self.rpc = rpc

    def record(self, item: SaasReadinessRecord):
        item.validate()
        snapshot = item.snapshot
        result = self.rpc(
            RPC_NAME,
            {
                "p_readiness_key": item.readiness_key,
                "p_tenant_id": snapshot.tenant_id,
                "p_active_members": snapshot.active_members,
                "p_observed_monthly_usage": snapshot.observed_monthly_usage,
                "p_observed_usage_limit": snapshot.observed_usage_limit,
                "p_active_subscription": snapshot.active_subscription,
                "p_tenant_isolation_verified": (
                    snapshot.tenant_isolation_verified
                ),
                "p_white_label_requested": snapshot.white_label_requested,
                "p_white_label_configured": snapshot.white_label_configured,
                "p_evidence_refs": list(snapshot.evidence_refs),
                "p_evidence": dict(item.evidence),
            },
        )
        if not isinstance(result, dict):
            raise SaasRegistryTransportError(
                "SaaS registry RPC returned invalid payload"
            )
        return result
