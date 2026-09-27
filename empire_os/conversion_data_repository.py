"""Canonical read repository for Conversion Intelligence."""
from __future__ import annotations

from typing import Any

from empire_os.canonical_data_gateway import CanonicalDataGateway
from empire_os.data_query import DataFilter


class ConversionDataRepository:
    def __init__(self, gateway: CanonicalDataGateway) -> None:
        self._gateway = gateway

    def approved_buyer_reviews(self) -> list[dict[str, Any]]:
        return self._gateway.query(
            "buyer_candidate_reviews",
            "id,status",
            filters=(DataFilter.eq("status", "approved"),),
            limit=5000,
        )

    def delivered_or_replied_intents(self) -> list[dict[str, Any]]:
        return self._gateway.query(
            "outbound_intents",
            "id,status,normalized_recipient,metadata",
            filters=(DataFilter.in_("status", ("delivered", "replied")),),
            limit=5000,
        )

    def commercial_replies(self) -> list[dict[str, Any]]:
        return self._gateway.query(
            "outbound_replies",
            "id,intent_id,classification,normalized_from_contact",
            filters=(
                DataFilter.in_(
                    "classification",
                    ("positive", "question", "objection"),
                ),
            ),
            limit=5000,
        )

    def closer_cases(self) -> list[dict[str, Any]]:
        return self._gateway.query(
            "closer_cases",
            "id,state",
            limit=5000,
        )

    def commercial_terms_reviews(self) -> list[dict[str, Any]]:
        return self._gateway.query(
            "commercial_terms_reviews",
            "id,status,fulfilment_order_id",
            limit=5000,
        )

    def accepted_paid_fulfilled_orders(self) -> list[dict[str, Any]]:
        return self._gateway.query(
            "fulfilment_orders",
            "id,state",
            filters=(
                DataFilter.in_(
                    "state",
                    ("accepted", "paid", "fulfilled"),
                ),
            ),
            limit=5000,
        )

    def payment_evidence(self) -> list[dict[str, Any]]:
        return self._gateway.query(
            "bsc_payment_evidence",
            "id,fulfilment_order_id",
            limit=5000,
        )

    def commercial_outcomes(self) -> list[dict[str, Any]]:
        return self._gateway.query(
            "commercial_outcomes",
            (
                "id,fulfilment_order_id,delivery_outcome,"
                "conversion_outcome,buyer_satisfaction"
            ),
            limit=5000,
        )

    def snapshot(self) -> dict[str, object]:
        backend = self._gateway.snapshot().as_dict()
        return {
            "backend": backend["primary_backend"],
            "configured": backend["configured"],
            "repository_authority": "read_only",
            "dual_write_enabled": backend["dual_write_enabled"],
            "write_fallback_enabled": backend["write_fallback_enabled"],
        }
