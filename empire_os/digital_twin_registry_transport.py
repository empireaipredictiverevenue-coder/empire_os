"""Dedicated Phase 14 Digital Twin scenario registry transport."""
from __future__ import annotations

import json
from typing import Any, Callable

from empire_os.digital_twin_registry import DigitalTwinRegistryRecord


class DigitalTwinRegistryTransportError(RuntimeError):
    pass


RPC_NAME = "record_digital_twin_scenario"
ROLE = "empire_digital_twin_registry_writer"
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
                    cursor.execute("SET LOCAL ROLE " + ROLE)
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


class RpcDigitalTwinRegistryRepository:
    def __init__(self, rpc: Callable[[str, dict[str, Any]], Any]):
        self.rpc = rpc

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
