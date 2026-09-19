"""Dedicated Phase 17 enterprise readiness registry transport."""
from __future__ import annotations

import json
from typing import Any, Callable

from empire_os.enterprise_registry import EnterpriseReadinessRecord


class EnterpriseRegistryTransportError(RuntimeError):
    pass


RPC_NAME = "record_enterprise_readiness"
ROLE = "empire_enterprise_registry_writer"
SQL = (
    "select public.record_enterprise_readiness("
    "%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s,%s::jsonb)"
)
PARAM_KEYS = (
    "p_readiness_key",
    "p_controls",
    "p_slos",
    "p_control_passes",
    "p_control_failures",
    "p_control_unknowns",
    "p_slo_passes",
    "p_slo_failures",
    "p_slo_unknowns",
    "p_evidence",
)


class PostgresEnterpriseRegistryRpc:
    def __init__(
        self,
        dsn: str,
        *,
        connect_factory: Callable | None = None,
    ) -> None:
        self.dsn = str(dsn or "").strip()
        if not self.dsn:
            raise EnterpriseRegistryTransportError(
                "dedicated enterprise registry DSN required"
            )
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise EnterpriseRegistryTransportError(
                    "psycopg is required for enterprise registry"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def __call__(self, name: str, params: dict[str, Any]) -> Any:
        if name != RPC_NAME:
            raise EnterpriseRegistryTransportError(
                "enterprise registry role cannot execute this RPC"
            )
        if not isinstance(params, dict) or set(params) != set(PARAM_KEYS):
            raise EnterpriseRegistryTransportError(
                "unexpected enterprise registry RPC parameters"
            )
        values = []
        for key in PARAM_KEYS:
            value = params[key]
            if key in {"p_controls", "p_slos", "p_evidence"}:
                value = json.dumps(
                    value or ([] if key != "p_evidence" else {}),
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
            raise EnterpriseRegistryTransportError(
                "enterprise registry RPC failed"
            ) from exc

        if not row or len(row) != 1:
            raise EnterpriseRegistryTransportError(
                "enterprise registry RPC returned no result"
            )
        return row[0]


class RpcEnterpriseRegistryRepository:
    def __init__(self, rpc: Callable[[str, dict[str, Any]], Any]):
        self.rpc = rpc

    def record(self, item: EnterpriseReadinessRecord):
        item.validate()
        result = self.rpc(
            RPC_NAME,
            {
                "p_readiness_key": item.readiness_key,
                "p_controls": [row.as_dict() for row in item.controls],
                "p_slos": [
                    {
                        "service_key": row.service_key,
                        "metric": row.metric,
                        "target": row.target,
                        "observed": row.observed,
                        "window": row.window,
                        "observed_at": row.observed_at,
                        "source": row.source,
                        "meets_target": row.meets_target,
                    }
                    for row in item.slos
                ],
                "p_control_passes": item.review.control_passes,
                "p_control_failures": item.review.control_failures,
                "p_control_unknowns": item.review.control_unknowns,
                "p_slo_passes": item.review.slo_passes,
                "p_slo_failures": item.review.slo_failures,
                "p_slo_unknowns": item.review.slo_unknowns,
                "p_evidence": dict(item.evidence),
            },
        )
        if not isinstance(result, dict):
            raise EnterpriseRegistryTransportError(
                "enterprise registry RPC returned invalid payload"
            )
        return result
