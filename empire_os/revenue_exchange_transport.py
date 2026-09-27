"""Dedicated append-only transport for Revenue Exchange observations."""
from __future__ import annotations

import json
from typing import Any, Callable

from empire_os.revenue_exchange_ingest import CanonicalExchangeObservation


class RevenueExchangeTransportError(RuntimeError):
    pass


RPC_NAME = "record_revenue_exchange_observation"
WRITER_ROLE = "empire_revenue_exchange_ingest"
READER_ROLE = "empire_revenue_exchange_reader"
SQL = (
    "select public.record_revenue_exchange_observation("
    "%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)"
)
PARAM_KEYS = (
    "p_observation_key",
    "p_niche",
    "p_metro",
    "p_qualified_inventory_count",
    "p_active_buyer_capacity",
    "p_verified_price_per_lead_cents",
    "p_observed_at",
    "p_source",
    "p_evidence",
)


class PostgresRevenueExchangeRpc:
    def __init__(
        self,
        dsn: str,
        *,
        connect_factory: Callable | None = None,
    ) -> None:
        self.dsn = str(dsn or "").strip()
        if not self.dsn:
            raise RevenueExchangeTransportError(
                "dedicated revenue exchange ingest DSN required"
            )
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise RevenueExchangeTransportError(
                    "psycopg is required for revenue exchange ingest"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def __call__(self, name: str, params: dict[str, Any]) -> Any:
        if name != RPC_NAME:
            raise RevenueExchangeTransportError(
                "revenue exchange ingest role cannot execute this RPC"
            )
        if not isinstance(params, dict) or set(params) != set(PARAM_KEYS):
            raise RevenueExchangeTransportError(
                "unexpected revenue exchange RPC parameters"
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
            raise RevenueExchangeTransportError(
                "revenue exchange ingest RPC failed"
            ) from exc
        if not row or len(row) != 1:
            raise RevenueExchangeTransportError(
                "revenue exchange ingest RPC returned no result"
            )
        return row[0]


READ_SQL = """
SELECT
  niche,
  metro,
  qualified_inventory_count,
  active_buyer_capacity,
  verified_price_per_lead_cents,
  observed_at,
  source
FROM public.revenue_exchange_observations
ORDER BY observed_at DESC,id DESC
LIMIT %s
"""


class PostgresRevenueExchangeReader:
    def __init__(
        self,
        dsn: str,
        *,
        connect_factory: Callable | None = None,
    ) -> None:
        self.dsn = str(dsn or "").strip()
        if not self.dsn:
            raise RevenueExchangeTransportError(
                "dedicated revenue exchange read DSN required"
            )
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise RevenueExchangeTransportError(
                    "psycopg is required for revenue exchange read"
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
            raise RevenueExchangeTransportError(
                "revenue exchange read failed"
            ) from exc
        return [
            dict(zip(columns, row, strict=True))
            for row in rows
        ]


class RpcRevenueExchangeRepository:
    def __init__(
        self,
        rpc: Callable[[str, dict[str, Any]], Any] | None = None,
        *,
        reader: Callable[..., list[dict[str, Any]]] | None = None,
    ):
        self.rpc = rpc
        self.reader = reader

    def append(self, item: CanonicalExchangeObservation):
        if self.rpc is None:
            raise RevenueExchangeTransportError(
                "revenue exchange ingest writer not activated"
            )
        item.validate()
        snap = item.snapshot
        result = self.rpc(
            RPC_NAME,
            {
                "p_observation_key": item.observation_key,
                "p_niche": snap.niche,
                "p_metro": snap.metro,
                "p_qualified_inventory_count": (
                    snap.qualified_inventory_count
                ),
                "p_active_buyer_capacity": snap.active_buyer_capacity,
                "p_verified_price_per_lead_cents": list(
                    snap.verified_price_per_lead_cents
                ),
                "p_observed_at": snap.observed_at,
                "p_source": snap.source,
                "p_evidence": dict(item.evidence),
            },
        )
        if not isinstance(result, dict):
            raise RevenueExchangeTransportError(
                "revenue exchange ingest RPC returned invalid payload"
            )
        return result

    def observations(self, *, limit: int):
        if self.reader is None:
            raise RevenueExchangeTransportError(
                "revenue exchange reader not activated"
            )
        rows = self.reader(limit=limit)
        if not isinstance(rows, list):
            raise RevenueExchangeTransportError(
                "revenue exchange reader returned invalid payload"
            )
        return rows
