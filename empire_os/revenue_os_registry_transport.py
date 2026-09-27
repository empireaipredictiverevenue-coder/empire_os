"""Dedicated Phase 18 Revenue OS packet registry transport."""
from __future__ import annotations

import json
from typing import Any, Callable

from empire_os.revenue_os_registry import RevenueOsRegistryRecord


class RevenueOsRegistryTransportError(RuntimeError):
    pass


RPC_NAME = "record_revenue_os_packet"
WRITER_ROLE = "empire_revenue_os_registry_writer"
READER_ROLE = "empire_revenue_os_registry_reader"
SQL = (
    "select public.record_revenue_os_packet("
    "%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s::jsonb)"
)
PARAM_KEYS = (
    "p_packet_key",
    "p_recommended_workstream",
    "p_recommended_job_type",
    "p_forecast_direction",
    "p_capital_candidate_id",
    "p_demand_plan_ref",
    "p_enterprise_blockers",
    "p_evidence_refs",
    "p_ready_for_operator_review",
    "p_evidence",
)


class PostgresRevenueOsRegistryRpc:
    def __init__(self, dsn: str, *, connect_factory: Callable | None = None):
        self.dsn = str(dsn or "").strip()
        if not self.dsn:
            raise RevenueOsRegistryTransportError(
                "dedicated Revenue OS registry DSN required"
            )
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise RevenueOsRegistryTransportError(
                    "psycopg is required for Revenue OS registry"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def __call__(self, name: str, params: dict[str, Any]) -> Any:
        if name != RPC_NAME:
            raise RevenueOsRegistryTransportError(
                "Revenue OS registry role cannot execute this RPC"
            )
        if not isinstance(params, dict) or set(params) != set(PARAM_KEYS):
            raise RevenueOsRegistryTransportError(
                "unexpected Revenue OS registry RPC parameters"
            )
        values = []
        for key in PARAM_KEYS:
            value = params[key]
            if key in {
                "p_enterprise_blockers",
                "p_evidence_refs",
                "p_evidence",
            }:
                value = json.dumps(
                    value or ([] if key != "p_evidence" else {}),
                    separators=(",", ":"),
                    sort_keys=True,
                )
            values.append(value)
        try:
            with self._connect(self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL ROLE " + WRITER_ROLE)
                    cursor.execute(SQL, tuple(values))
                    row = cursor.fetchone()
        except Exception as exc:
            raise RevenueOsRegistryTransportError(
                "Revenue OS registry RPC failed"
            ) from exc
        if not row or len(row) != 1:
            raise RevenueOsRegistryTransportError(
                "Revenue OS registry RPC returned no result"
            )
        return row[0]


PACKET_COLUMNS = """
  id,
  packet_key,
  recommended_workstream,
  recommended_job_type,
  forecast_direction,
  capital_candidate_id,
  demand_plan_ref,
  enterprise_blockers,
  evidence_refs,
  ready_for_operator_review,
  readiness_blockers,
  evidence,
  execution_authority,
  spend_execution,
  outreach_execution,
  payment_execution,
  allocation_execution,
  deployment_execution,
  created_at
"""

PACKETS_SQL = (
    "SELECT " + PACKET_COLUMNS
    + " FROM public.revenue_os_decision_packets "
    "ORDER BY created_at DESC,id DESC LIMIT %s"
)

PACKET_SQL = (
    "SELECT " + PACKET_COLUMNS
    + " FROM public.revenue_os_decision_packets "
    "WHERE packet_key=%s LIMIT 1"
)


class PostgresRevenueOsRegistryReader:
    def __init__(
        self,
        dsn: str,
        *,
        connect_factory: Callable | None = None,
    ) -> None:
        self.dsn = str(dsn or "").strip()
        if not self.dsn:
            raise RevenueOsRegistryTransportError(
                "dedicated Revenue OS registry read DSN required"
            )
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise RevenueOsRegistryTransportError(
                    "psycopg is required for Revenue OS registry read"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def _fetch(
        self,
        sql: str,
        params: tuple[Any, ...],
    ) -> list[dict[str, Any]]:
        try:
            with self._connect(self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL ROLE " + READER_ROLE)
                    cursor.execute(sql, params)
                    columns = [
                        description.name
                        for description in cursor.description
                    ]
                    rows = cursor.fetchall()
        except Exception as exc:
            raise RevenueOsRegistryTransportError(
                "Revenue OS registry read failed"
            ) from exc
        return [
            dict(zip(columns, row, strict=True))
            for row in rows
        ]

    def packets(self, *, limit: int):
        bounded = max(1, min(int(limit), 200))
        return self._fetch(PACKETS_SQL, (bounded,))

    def packet(self, packet_key: str):
        key = str(packet_key or "").strip()
        if not key:
            raise RevenueOsRegistryTransportError(
                "packet_key required"
            )
        rows = self._fetch(PACKET_SQL, (key,))
        return rows[0] if rows else None


class RpcRevenueOsRegistryRepository:
    def __init__(
        self,
        rpc: Callable[[str, dict[str, Any]], Any],
        *,
        reader: PostgresRevenueOsRegistryReader | None = None,
    ):
        self.rpc = rpc
        self.reader = reader

    def record(self, item: RevenueOsRegistryRecord):
        item.validate()
        packet = item.packet
        readiness = item.readiness
        result = self.rpc(
            RPC_NAME,
            {
                "p_packet_key": packet.packet_key,
                "p_recommended_workstream": packet.recommended_workstream,
                "p_recommended_job_type": packet.recommended_job_type,
                "p_forecast_direction": packet.forecast_direction,
                "p_capital_candidate_id": packet.capital_candidate_id,
                "p_demand_plan_ref": packet.demand_plan_ref,
                "p_enterprise_blockers": list(packet.enterprise_blockers),
                "p_evidence_refs": list(packet.evidence_refs),
                "p_ready_for_operator_review": (
                    readiness.ready_for_operator_review
                ),
                "p_evidence": dict(item.evidence),
            },
        )
        if not isinstance(result, dict):
            raise RevenueOsRegistryTransportError(
                "Revenue OS registry RPC returned invalid payload"
            )
        return result

    def packets(self, *, limit: int):
        if self.reader is None:
            raise RevenueOsRegistryTransportError(
                "Revenue OS registry reader not activated"
            )
        return self.reader.packets(limit=limit)

    def packet(self, packet_key: str):
        if self.reader is None:
            raise RevenueOsRegistryTransportError(
                "Revenue OS registry reader not activated"
            )
        return self.reader.packet(packet_key)
