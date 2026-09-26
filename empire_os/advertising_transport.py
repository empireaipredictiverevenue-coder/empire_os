"""Dedicated append-only transport for advertising observations."""
from __future__ import annotations

import json
from typing import Any, Callable

from empire_os.advertising_ingest import CanonicalAdObservation


class AdvertisingTransportError(RuntimeError):
    pass


RPC_NAME = "record_ad_performance_observation"
ROLE = "empire_ad_observation_ingest"
SQL = (
    "select public.record_ad_performance_observation("
    "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)"
)
PARAM_KEYS = (
    "p_campaign_id",
    "p_provider_observation_id",
    "p_observed_at",
    "p_spend_cents",
    "p_attributed_revenue_cents",
    "p_attributed_gross_profit_cents",
    "p_impressions",
    "p_clicks",
    "p_conversions",
    "p_source",
    "p_creative_id",
    "p_evidence",
)


class PostgresAdvertisingObservationRpc:
    def __init__(
        self,
        dsn: str,
        *,
        connect_factory: Callable | None = None,
    ) -> None:
        self.dsn = str(dsn or "").strip()
        if not self.dsn:
            raise AdvertisingTransportError(
                "dedicated advertising ingest DSN required"
            )
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise AdvertisingTransportError(
                    "psycopg is required for advertising ingest"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def __call__(self, name: str, params: dict[str, Any]) -> Any:
        if name != RPC_NAME:
            raise AdvertisingTransportError(
                "advertising ingest role cannot execute this RPC"
            )
        if not isinstance(params, dict) or set(params) != set(PARAM_KEYS):
            raise AdvertisingTransportError(
                "unexpected advertising ingest RPC parameters"
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
            raise AdvertisingTransportError(
                "advertising ingest RPC failed"
            ) from exc
        if not row or len(row) != 1:
            raise AdvertisingTransportError(
                "advertising ingest RPC returned no result"
            )
        return row[0]


class RpcAdvertisingObservationRepository:
    def __init__(self, rpc: Callable[[str, dict[str, Any]], Any]):
        self.rpc = rpc

    def append(self, item: CanonicalAdObservation):
        item.validate()
        obs = item.observation
        result = self.rpc(
            RPC_NAME,
            {
                "p_campaign_id": item.canonical_campaign_id,
                "p_provider_observation_id": item.provider_observation_id,
                "p_observed_at": obs.observed_at,
                "p_spend_cents": obs.spend_cents,
                "p_attributed_revenue_cents": obs.attributed_revenue_cents,
                "p_attributed_gross_profit_cents": (
                    obs.attributed_gross_profit_cents
                ),
                "p_impressions": obs.impressions,
                "p_clicks": obs.clicks,
                "p_conversions": obs.conversions,
                "p_source": obs.source,
                "p_creative_id": item.canonical_creative_id,
                "p_evidence": {
                    **dict(item.evidence),
                    "platform": obs.platform,
                    "external_campaign_id": obs.campaign_id,
                    "external_creative_id": obs.creative_id,
                    "payload_sha256": item.payload_sha256,
                },
            },
        )
        if not isinstance(result, dict):
            raise AdvertisingTransportError(
                "advertising ingest RPC returned invalid payload"
            )
        return result
