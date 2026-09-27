"""Least-privilege PostgreSQL reader for canonical Revenue CRM views."""
from __future__ import annotations

from typing import Any, Callable
from uuid import UUID


class RevenueCrmTransportError(RuntimeError):
    """Dedicated Revenue CRM read transport is unavailable or unsafe."""


ROLE = "empire_revenue_crm_reader"

PROSPECT_COLUMNS = (
    "prospect_id,business_name,niche,metro,prospect_status,"
    "conversation_id,conversation_channel,conversation_state,"
    "conversation_updated_at,closer_case_id,closer_state,"
    "closer_updated_at,fulfilment_order_id,fulfilment_state,"
    "fulfilment_updated_at,price_cents,buyer_id,"
    "buyer_activation_state,buyer_available_capacity,"
    "buyer_capacity_verified_at,deal_probability"
)

BUYER_COLUMNS = (
    "buyer_id,buyer_name,niche,metro,buyer_status,is_active,"
    "commercial_activation_state,daily_cap,calls_today,"
    "available_capacity,per_lead_rate,capacity_verified_at,"
    "delivery_verified_at,commercial_terms_verified_at"
)

PROSPECT_LIST_SQL = (
    "SELECT " + PROSPECT_COLUMNS
    + " FROM public.revenue_crm_prospects "
    "ORDER BY prospect_id LIMIT %s"
)

PROSPECT_ONE_SQL = (
    "SELECT " + PROSPECT_COLUMNS
    + " FROM public.revenue_crm_prospects "
    "WHERE prospect_id=%s LIMIT 1"
)

BUYER_LIST_SQL = (
    "SELECT " + BUYER_COLUMNS
    + " FROM public.revenue_crm_buyers "
    "ORDER BY buyer_id LIMIT %s"
)


def _bounded_limit(value: int, *, maximum: int = 500) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise RevenueCrmTransportError("invalid Revenue CRM limit") from exc
    if not 1 <= parsed <= maximum:
        raise RevenueCrmTransportError("Revenue CRM limit out of range")
    return parsed


def _uuid(value: str, *, field: str) -> str:
    try:
        return str(UUID(str(value or "").strip()))
    except (TypeError, ValueError, AttributeError) as exc:
        raise RevenueCrmTransportError(
            f"invalid canonical {field} UUID"
        ) from exc


class PostgresRevenueCrmRepository:
    """Static, read-only repository over canonical Revenue CRM views."""

    def __init__(
        self,
        dsn: str,
        *,
        connect_factory: Callable | None = None,
    ) -> None:
        self.dsn = str(dsn or "").strip()
        if not self.dsn:
            raise RevenueCrmTransportError(
                "dedicated Revenue CRM database DSN required"
            )
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise RevenueCrmTransportError(
                    "psycopg is required for Revenue CRM transport"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def _fetch_all(
        self,
        sql: str,
        params: tuple[Any, ...],
    ) -> list[dict[str, Any]]:
        try:
            with self._connect(self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL ROLE " + ROLE)
                    cursor.execute(sql, params)
                    columns = [
                        description.name
                        for description in cursor.description
                    ]
                    rows = cursor.fetchall()
        except Exception as exc:
            raise RevenueCrmTransportError(
                "dedicated Revenue CRM database read failed"
            ) from exc
        return [
            dict(zip(columns, row, strict=True))
            for row in rows
        ]

    def prospects(self, *, limit: int):
        bounded = _bounded_limit(limit)
        return self._fetch_all(PROSPECT_LIST_SQL, (bounded,))

    def buyers(self, *, limit: int):
        bounded = _bounded_limit(limit)
        return self._fetch_all(BUYER_LIST_SQL, (bounded,))

    def prospect(self, prospect_id: str):
        canonical_id = _uuid(prospect_id, field="prospect_id")
        rows = self._fetch_all(
            PROSPECT_ONE_SQL,
            (canonical_id,),
        )
        return rows[0] if rows else None
