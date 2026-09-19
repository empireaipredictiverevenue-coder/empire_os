"""Dedicated Phase 12 demand-plan registry transport."""
from __future__ import annotations

import json
from typing import Any, Callable

from empire_os.demand_registry import DemandRegistryRecord


class DemandRegistryTransportError(RuntimeError):
    pass


RPC_NAME = "record_demand_plan_registry"
ROLE = "empire_demand_registry_writer"
SQL = (
    "select public.record_demand_plan_registry("
    "%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s::jsonb)"
)
PARAM_KEYS = (
    "p_plan_id",
    "p_channel",
    "p_objective",
    "p_audience",
    "p_evidence_refs",
    "p_success_metric",
    "p_evidence_score",
    "p_readiness_reason",
    "p_missing_evidence",
    "p_evidence",
)


class PostgresDemandRegistryRpc:
    def __init__(
        self,
        dsn: str,
        *,
        connect_factory: Callable | None = None,
    ) -> None:
        self.dsn = str(dsn or "").strip()
        if not self.dsn:
            raise DemandRegistryTransportError(
                "dedicated demand registry DSN required"
            )
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise DemandRegistryTransportError(
                    "psycopg is required for demand registry"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def __call__(self, name: str, params: dict[str, Any]) -> Any:
        if name != RPC_NAME:
            raise DemandRegistryTransportError(
                "demand registry role cannot execute this RPC"
            )
        if not isinstance(params, dict) or set(params) != set(PARAM_KEYS):
            raise DemandRegistryTransportError(
                "unexpected demand registry RPC parameters"
            )
        values = []
        for key in PARAM_KEYS:
            value = params[key]
            if key in {"p_evidence_refs", "p_missing_evidence", "p_evidence"}:
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
            raise DemandRegistryTransportError(
                "demand registry RPC failed"
            ) from exc
        if not row or len(row) != 1:
            raise DemandRegistryTransportError(
                "demand registry RPC returned no result"
            )
        return row[0]


class RpcDemandRegistryRepository:
    def __init__(self, rpc: Callable[[str, dict[str, Any]], Any]):
        self.rpc = rpc

    def record(self, item: DemandRegistryRecord):
        item.validate()
        plan = item.plan
        readiness = item.readiness
        result = self.rpc(
            RPC_NAME,
            {
                "p_plan_id": plan.plan_id,
                "p_channel": plan.channel,
                "p_objective": plan.objective,
                "p_audience": plan.audience,
                "p_evidence_refs": list(plan.evidence_refs),
                "p_success_metric": plan.success_metric,
                "p_evidence_score": readiness.evidence_score,
                "p_readiness_reason": readiness.readiness_reason,
                "p_missing_evidence": list(readiness.missing_evidence),
                "p_evidence": dict(item.evidence),
            },
        )
        if not isinstance(result, dict):
            raise DemandRegistryTransportError(
                "demand registry RPC returned invalid payload"
            )
        return result
