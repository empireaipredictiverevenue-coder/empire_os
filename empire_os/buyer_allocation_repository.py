"""Canonical data source for buyer allocation.

Read paths use the vendor-neutral Data Gateway. The atomic allocation mutation
remains an explicit RPC boundary and fails closed on EmpireDB until that
procedure is deliberately mapped.
"""
from __future__ import annotations

from typing import Any

from empire_os.canonical_data_gateway import CanonicalDataGateway
from empire_os.data_query import DataFilter, OrderSpec


QUALIFICATION_COLUMNS = (
    "id,prospect_id,entity_id,score,tier,status,scoring_engine,scoring_version,"
    "evidence_confidence,observed_dimensions,unknown_dimensions,scored_at"
)

IDENTITY_COLUMNS = (
    "prospect_id,entity_id,match_score,active,created_at"
)

BUYER_COLUMNS = (
    "id,buyer_name,niche,metro,is_active,status,"
    "daily_cap,calls_today,base_payout,per_lead_rate,priority,"
    "destination_phone,webhook_url,reviewed_at,"
    "commercial_activation_state,commercial_activated_at,"
    "commercial_terms_source,commercial_terms_reference,"
    "commercial_terms_verified_at,capacity_verified_at,"
    "delivery_verified_at"
)


class BuyerAllocationDataRepository:
    def __init__(self, gateway: CanonicalDataGateway) -> None:
        self._gateway = gateway

    def latest_qualifications(
        self,
        prospect_id: str,
    ) -> list[dict[str, Any]]:
        return self._gateway.query(
            "prospect_qualifications",
            QUALIFICATION_COLUMNS,
            filters=(
                DataFilter.eq("prospect_id", prospect_id),
                DataFilter.eq("scoring_engine", "empire_os.lead_scoring"),
                DataFilter.in_("scoring_version", ("v2", "v1")),
            ),
            order=(OrderSpec("scored_at", descending=True),),
            limit=2,
        )

    def active_identity_links(
        self,
        prospect_id: str,
    ) -> list[dict[str, Any]]:
        return self._gateway.query(
            "prospect_entity_links",
            IDENTITY_COLUMNS,
            filters=(
                DataFilter.eq("prospect_id", prospect_id),
                DataFilter.eq("active", True),
            ),
            order=(OrderSpec("created_at", descending=True),),
            limit=2,
        )

    def buyer_page(
        self,
        *,
        page_size: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        return self._gateway.query(
            "buyers",
            BUYER_COLUMNS,
            order=(
                OrderSpec("created_at", descending=True),
                OrderSpec("id", descending=True),
            ),
            limit=page_size,
            offset=offset,
        )

    def allocate_atomic(
        self,
        payload: dict[str, Any],
    ) -> Any:
        return self._gateway.rpc(
            "allocate_prospect_atomic",
            payload,
        )

    def snapshot(self) -> dict[str, object]:
        backend = self._gateway.snapshot().as_dict()
        return {
            "backend": backend["primary_backend"],
            "configured": backend["configured"],
            "dual_write_enabled": backend["dual_write_enabled"],
            "write_fallback_enabled": backend["write_fallback_enabled"],
            "atomic_allocator": "allocate_prospect_atomic",
        }
