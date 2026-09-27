"""Canonical data repository for the autonomous execution bus.

This repository owns data access semantics only. It does not decide whether a
job should execute, widen approval authority, or change execution mode.
"""
from __future__ import annotations

from typing import Any, Iterable

from empire_os.buyer_allocation_repository import BuyerAllocationDataRepository
from empire_os.canonical_data_gateway import CanonicalDataGateway
from empire_os.commercial_event_repository import CommercialEventRepository
from empire_os.data_query import DataFilter, OrderSpec


PROSPECT_COLUMNS = (
    "id,business_name,niche,metro,status,buy_signal_score,phone,website,address,"
    "rating,review_count,contact_name,contact_title,contact_source,contacted_status"
)

ALLOCATION_PROSPECT_COLUMNS = (
    "id,business_name,niche,metro,status,buy_signal_score,"
    "phone,website,address,contact_source,contacted_status"
)

BUYER_CAPACITY_COLUMNS = (
    "id,buyer_name,niche,metro,is_active,status,"
    "daily_cap,calls_today,destination_phone,webhook_url,"
    "reviewed_at,commercial_activation_state,"
    "commercial_activated_at,commercial_terms_source,"
    "commercial_terms_reference,commercial_terms_verified_at,"
    "capacity_verified_at,delivery_verified_at"
)


class ExecutionBusDataRepository:
    def __init__(self, gateway: CanonicalDataGateway) -> None:
        self._gateway = gateway
        self.events = CommercialEventRepository(gateway)
        self.buyer_allocation = BuyerAllocationDataRepository(gateway)

    def rpc(
        self,
        name: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._gateway.rpc(name, payload)

    def append_commercial_event(
        self,
        event: dict[str, Any],
    ) -> bool:
        return self.events.append_idempotent(event)

    def ingest_prospect_atomic(
        self,
        *,
        prospect: dict[str, Any],
        evidence: dict[str, Any],
        ingest_key: str,
        identity_keys: list[str],
    ) -> Any:
        return self.rpc(
            "ingest_prospect_atomic",
            {
                "p_prospect": prospect,
                "p_evidence": evidence,
                "p_ingest_key": ingest_key,
                "p_identity_keys": identity_keys,
            },
        )

    def qualification_candidates(
        self,
        *,
        aliases: Iterable[str],
        metro: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        values = tuple(str(alias) for alias in aliases if str(alias))
        if not values:
            return []
        return self._gateway.query(
            "prospects",
            PROSPECT_COLUMNS,
            filters=(
                DataFilter.in_("niche", values),
                DataFilter.ilike("metro", metro),
                DataFilter.ne("status", "archived"),
            ),
            order=(
                OrderSpec(
                    "buy_signal_score",
                    descending=True,
                    nulls_last=True,
                ),
                OrderSpec("created_at"),
            ),
            limit=limit,
        )

    def existing_qualification_ids(
        self,
        prospect_ids: Iterable[str],
        *,
        scoring_engine: str,
        scoring_version: str,
    ) -> set[str]:
        ids = tuple(str(value) for value in prospect_ids if str(value))
        if not ids:
            return set()
        rows = self._gateway.query(
            "prospect_qualifications",
            "prospect_id",
            filters=(
                DataFilter.in_("prospect_id", ids),
                DataFilter.eq("scoring_engine", scoring_engine),
                DataFilter.eq("scoring_version", scoring_version),
            ),
            limit=max(1, len(ids)),
        )
        return {
            str(row.get("prospect_id"))
            for row in rows
            if row.get("prospect_id")
        }

    def allocation_qualifications(
        self,
        prospect_ids: Iterable[str],
    ) -> list[dict[str, Any]]:
        ids = tuple(str(value) for value in prospect_ids if str(value))
        if not ids:
            return []
        return self._gateway.query(
            "prospect_qualifications",
            "prospect_id,score,tier,status,scored_at",
            filters=(
                DataFilter.in_("prospect_id", ids),
                DataFilter.eq("status", "scored"),
                DataFilter.in_("tier", ("hot", "warm")),
                DataFilter.gte("score", 50),
                DataFilter.eq("scoring_engine", "empire_os.lead_scoring"),
                DataFilter.eq("scoring_version", "v1"),
            ),
            order=(
                OrderSpec("score", descending=True),
                OrderSpec("scored_at"),
            ),
            limit=max(1, len(ids)),
        )

    def active_fulfilment_prospect_ids(
        self,
        prospect_ids: Iterable[str],
    ) -> set[str]:
        ids = tuple(str(value) for value in prospect_ids if str(value))
        if not ids:
            return set()
        rows = self._gateway.query(
            "fulfilment_orders",
            "prospect_id",
            filters=(
                DataFilter.in_("prospect_id", ids),
                DataFilter.not_in("state", ("rejected", "cancelled")),
            ),
            limit=max(1, len(ids)),
        )
        return {
            str(row.get("prospect_id"))
            for row in rows
            if row.get("prospect_id")
        }

    def find_gtm_job(
        self,
        idempotency_key: str,
    ) -> dict[str, Any] | None:
        rows = self._gateway.query(
            "gtm_jobs",
            "id",
            filters=(DataFilter.eq("idempotency_key", idempotency_key),),
            limit=1,
        )
        return dict(rows[0]) if rows else None

    def insert_gtm_job(
        self,
        row: dict[str, Any],
    ) -> dict[str, Any]:
        rows = self._gateway.insert(
            "gtm_jobs",
            row,
            return_repr=True,
        )
        if not rows:
            raise RuntimeError("gtm job insert returned no row")
        return dict(rows[0])

    def prospect_by_id(
        self,
        prospect_id: str,
    ) -> dict[str, Any] | None:
        rows = self._gateway.query(
            "prospects",
            ALLOCATION_PROSPECT_COLUMNS,
            filters=(DataFilter.eq("id", prospect_id),),
            limit=1,
        )
        if not rows:
            return None
        if len(rows) != 1:
            raise RuntimeError("prospect query returned multiple rows")
        return dict(rows[0])

    def allocation_market_prospects(
        self,
        *,
        aliases: Iterable[str],
        metro: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        values = tuple(str(alias) for alias in aliases if str(alias))
        if not values:
            return []
        return self._gateway.query(
            "prospects",
            ALLOCATION_PROSPECT_COLUMNS,
            filters=(
                DataFilter.in_("niche", values),
                DataFilter.ilike("metro", metro),
                DataFilter.ne("status", "archived"),
            ),
            order=(
                OrderSpec(
                    "buy_signal_score",
                    descending=True,
                    nulls_last=True,
                ),
                OrderSpec("created_at"),
            ),
            limit=limit,
        )

    def capacity_buyer_page(
        self,
        *,
        page_size: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        return self._gateway.query(
            "buyers",
            BUYER_CAPACITY_COLUMNS,
            limit=page_size,
            offset=offset,
        )

    def snapshot(self) -> dict[str, object]:
        backend = self._gateway.snapshot().as_dict()
        return {
            "backend": backend["primary_backend"],
            "configured": backend["configured"],
            "dual_write_enabled": backend["dual_write_enabled"],
            "write_fallback_enabled": backend["write_fallback_enabled"],
            "repository_authority": "execution_bus_bounded",
        }
