"""Dedicated Phase 14 Digital Twin realization registry transport."""
from __future__ import annotations

import json
from typing import Any, Callable

from empire_os.digital_twin_registry import DigitalTwinRealizationRecord


class DigitalTwinRealizationTransportError(RuntimeError):
    pass


RPC_NAME = "record_digital_twin_realization"
WRITER_ROLE = "empire_digital_twin_realization_writer"
READER_ROLE = "empire_digital_twin_realization_reader"
SQL = (
    "select public.record_digital_twin_realization("
    "%s,%s,%s,%s,%s,%s,%s,%s::jsonb)"
)
PARAM_KEYS = (
    "p_realization_key",
    "p_scenario_key",
    "p_observed_served_units",
    "p_observed_revenue_cents",
    "p_revenue_recognized",
    "p_observed_at",
    "p_evidence_refs",
    "p_evidence",
)


class PostgresDigitalTwinRealizationRpc:
    def __init__(
        self,
        dsn: str,
        *,
        connect_factory: Callable | None = None,
    ) -> None:
        self.dsn = str(dsn or "").strip()
        if not self.dsn:
            raise DigitalTwinRealizationTransportError(
                "dedicated digital twin realization DSN required"
            )
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise DigitalTwinRealizationTransportError(
                    "psycopg is required for digital twin realization registry"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def __call__(self, name: str, params: dict[str, Any]) -> Any:
        if name != RPC_NAME:
            raise DigitalTwinRealizationTransportError(
                "digital twin realization role cannot execute this RPC"
            )
        if not isinstance(params, dict) or set(params) != set(PARAM_KEYS):
            raise DigitalTwinRealizationTransportError(
                "unexpected digital twin realization RPC parameters"
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
                    cursor.execute("SET LOCAL ROLE " + WRITER_ROLE)
                    cursor.execute(SQL, tuple(values))
                    row = cursor.fetchone()
        except Exception as exc:
            raise DigitalTwinRealizationTransportError(
                "digital twin realization RPC failed"
            ) from exc
        if not row or len(row) != 1:
            raise DigitalTwinRealizationTransportError(
                "digital twin realization RPC returned no result"
            )
        return row[0]


READ_SQL = """
SELECT
  z.id AS realization_id,
  z.realization_key,
  s.scenario_key,
  z.observed_served_units,
  z.observed_revenue_cents,
  z.revenue_recognized,
  z.observed_at,
  z.evidence_refs,
  z.served_unit_error,
  z.revenue_error_cents,
  z.revenue_error_ratio,
  z.revenue_comparison_available,
  z.blockers,
  z.simulation_only,
  z.creates_actual_revenue,
  z.execution_authority,
  z.evidence,
  z.created_at
FROM public.digital_twin_realizations z
JOIN public.digital_twin_scenarios s ON s.id=z.scenario_id
ORDER BY z.created_at DESC,z.id DESC
LIMIT %s
"""


class PostgresDigitalTwinRealizationReader:
    def __init__(
        self,
        dsn: str,
        *,
        connect_factory: Callable | None = None,
    ) -> None:
        self.dsn = str(dsn or "").strip()
        if not self.dsn:
            raise DigitalTwinRealizationTransportError(
                "dedicated digital twin realization read DSN required"
            )
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise DigitalTwinRealizationTransportError(
                    "psycopg is required for digital twin realization read"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory


    def __call__(self, *, limit: int) -> list[dict[str, Any]]:
        bounded = max(1, min(int(limit), 500))
        try:
            with self._connect(self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL ROLE " + READER_ROLE)
                    cursor.execute(READ_SQL, (bounded,))
                    columns = [
                        description.name
                        for description in cursor.description
                    ]
                    rows = cursor.fetchall()
        except Exception as exc:
            raise DigitalTwinRealizationTransportError(
                "digital twin realization read failed"
            ) from exc
        return [
            dict(zip(columns, row, strict=True))
            for row in rows
        ]


class RpcDigitalTwinRealizationRepository:
    def __init__(
        self,
        rpc: Callable[[str, dict[str, Any]], Any],
        *,
        reader: Callable[..., list[dict[str, Any]]] | None = None,
    ) -> None:
        self.rpc = rpc
        self.reader = reader

    def record_realization(self, item: DigitalTwinRealizationRecord):
        item.validate()
        result = self.rpc(
            RPC_NAME,
            {
                "p_realization_key": item.realization_key,
                "p_scenario_key": item.scenario_key,
                "p_observed_served_units": item.observed.observed_served_units,
                "p_observed_revenue_cents": (
                    item.observed.observed_revenue_cents
                    if item.observed.revenue_recognized
                    else None
                ),
                "p_revenue_recognized": item.observed.revenue_recognized,
                "p_observed_at": item.observed.observed_at,
                "p_evidence_refs": list(item.observed.evidence_refs),
                "p_evidence": dict(item.evidence),
            },
        )
        if not isinstance(result, dict):
            raise DigitalTwinRealizationTransportError(
                "digital twin realization RPC returned invalid payload"
            )
        return result

    def list_realizations(self, *, limit: int):
        if self.reader is None:
            raise DigitalTwinRealizationTransportError(
                "digital twin realization reader not activated"
            )
        rows = self.reader(limit=limit)
        if not isinstance(rows, list):
            raise DigitalTwinRealizationTransportError(
                "digital twin realization reader returned invalid payload"
            )
        return rows
