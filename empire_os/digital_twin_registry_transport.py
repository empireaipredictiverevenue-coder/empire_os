"""Dedicated Phase 14 Digital Twin scenario registry transport."""
from __future__ import annotations

import json
from typing import Any, Callable

from empire_os.digital_twin_registry import DigitalTwinRegistryRecord


class DigitalTwinRegistryTransportError(RuntimeError):
    pass


RPC_NAME = "record_digital_twin_scenario"
WRITER_ROLE = "empire_digital_twin_registry_writer"
READER_ROLE = "empire_digital_twin_registry_reader"
SQL = (
    "select public.record_digital_twin_scenario("
    "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)"
)
PARAM_KEYS = (
    "p_scenario_key",
    "p_niche",
    "p_metro",
    "p_baseline_evidence_ref",
    "p_baseline_observed_at",
    "p_observed_demand_units",
    "p_observed_capacity_units",
    "p_observed_price_per_unit_cents",
    "p_demand_multiplier",
    "p_capacity_multiplier",
    "p_price_multiplier",
    "p_projected_served_units",
    "p_projected_revenue_cents",
    "p_simulated_revenue_delta_cents",
    "p_evidence",
)


class PostgresDigitalTwinRegistryRpc:
    def __init__(
        self,
        dsn: str,
        *,
        connect_factory: Callable | None = None,
    ) -> None:
        self.dsn = str(dsn or "").strip()
        if not self.dsn:
            raise DigitalTwinRegistryTransportError(
                "dedicated digital twin registry DSN required"
            )
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise DigitalTwinRegistryTransportError(
                    "psycopg is required for digital twin registry"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def __call__(self, name: str, params: dict[str, Any]) -> Any:
        if name != RPC_NAME:
            raise DigitalTwinRegistryTransportError(
                "digital twin registry role cannot execute this RPC"
            )
        if not isinstance(params, dict) or set(params) != set(PARAM_KEYS):
            raise DigitalTwinRegistryTransportError(
                "unexpected digital twin registry RPC parameters"
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
            raise DigitalTwinRegistryTransportError(
                "digital twin registry RPC failed"
            ) from exc
        if not row or len(row) != 1:
            raise DigitalTwinRegistryTransportError(
                "digital twin registry RPC returned no result"
            )
        return row[0]


READ_SQL = """
SELECT
  s.id AS scenario_id,
  s.scenario_key,
  s.niche,
  s.metro,
  s.baseline_evidence_ref,
  s.baseline_observed_at,
  s.observed_demand_units,
  s.observed_capacity_units,
  s.observed_price_per_unit_cents,
  s.demand_multiplier,
  s.capacity_multiplier,
  s.price_multiplier,
  s.evidence,
  s.execution_authority,
  s.capital_execution,
  s.campaign_execution,
  s.pricing_execution,
  r.id AS result_id,
  r.projected_served_units,
  r.projected_revenue_cents,
  r.simulated_revenue_delta_cents,
  r.execution_authority AS result_execution_authority,
  s.created_at
FROM public.digital_twin_scenarios s
LEFT JOIN public.digital_twin_results r
  ON r.scenario_id=s.id
ORDER BY s.created_at DESC,s.id DESC
LIMIT %s
"""


class PostgresDigitalTwinRegistryReader:
    def __init__(
        self,
        dsn: str,
        *,
        connect_factory: Callable | None = None,
    ) -> None:
        self.dsn = str(dsn or "").strip()
        if not self.dsn:
            raise DigitalTwinRegistryTransportError(
                "dedicated digital twin registry read DSN required"
            )
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise DigitalTwinRegistryTransportError(
                    "psycopg is required for digital twin registry read"
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
            raise DigitalTwinRegistryTransportError(
                "digital twin registry read failed"
            ) from exc
        return [
            dict(zip(columns, row, strict=True))
            for row in rows
        ]


class RpcDigitalTwinRegistryRepository:
    def __init__(
        self,
        rpc: Callable[[str, dict[str, Any]], Any],
        *,
        reader: Callable[..., list[dict[str, Any]]] | None = None,
    ):
        self.rpc = rpc
        self.reader = reader

    def record(self, item: DigitalTwinRegistryRecord):
        item.validate()
        b = item.baseline
        s = item.scenario
        c = item.comparison
        result = self.rpc(
            RPC_NAME,
            {
                "p_scenario_key": item.scenario_key,
                "p_niche": b.niche,
                "p_metro": b.metro,
                "p_baseline_evidence_ref": b.evidence_ref,
                "p_baseline_observed_at": b.observed_at,
                "p_observed_demand_units": b.observed_demand_units,
                "p_observed_capacity_units": b.observed_capacity_units,
                "p_observed_price_per_unit_cents": (
                    b.observed_price_per_unit_cents
                ),
                "p_demand_multiplier": s.demand_multiplier,
                "p_capacity_multiplier": s.capacity_multiplier,
                "p_price_multiplier": s.price_multiplier,
                "p_projected_served_units": (
                    c.scenario.projected_served_units
                ),
                "p_projected_revenue_cents": (
                    c.scenario.projected_revenue_cents
                ),
                "p_simulated_revenue_delta_cents": (
                    c.simulated_revenue_delta_cents
                ),
                "p_evidence": dict(item.evidence),
            },
        )
        if not isinstance(result, dict):
            raise DigitalTwinRegistryTransportError(
                "digital twin registry RPC returned invalid payload"
            )
        return result

    def list_scenarios(self, *, limit: int):
        if self.reader is None:
            raise DigitalTwinRegistryTransportError(
                "digital twin registry reader not activated"
            )
        rows = self.reader(limit=limit)
        if not isinstance(rows, list):
            raise DigitalTwinRegistryTransportError(
                "digital twin registry reader returned invalid payload"
            )
        return rows
