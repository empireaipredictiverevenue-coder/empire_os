"""Canonical read repository for conversion evidence."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable, Protocol

from empire_os.canonical_data_gateway import (
    CanonicalDataGateway,
    gateway_from_environment,
)
from empire_os.data_query import DataFilter
from empire_os.runtime_env import load_runtime_env


ENV_PATH = "/etc/empire_os.env"
Request = Callable[..., Any]


class ConversionRepository(Protocol):
    def approved_reviews(self) -> list[dict[str, Any]]: ...
    def delivered_or_replied_intents(self) -> list[dict[str, Any]]: ...
    def commercial_replies(self) -> list[dict[str, Any]]: ...
    def closer_cases(self) -> list[dict[str, Any]]: ...
    def commercial_terms(self) -> list[dict[str, Any]]: ...
    def accepted_orders(self) -> list[dict[str, Any]]: ...
    def payment_evidence(self) -> list[dict[str, Any]]: ...
    def commercial_outcomes(self) -> list[dict[str, Any]]: ...


def _rows(value: object, *, surface: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{surface} projection must be a list")
    return [dict(row) for row in value if isinstance(row, Mapping)]


class CanonicalConversionRepository:
    def __init__(self, gateway: CanonicalDataGateway) -> None:
        self._gateway = gateway

    @classmethod
    def from_environment(cls) -> "CanonicalConversionRepository":
        env = load_runtime_env(ENV_PATH)
        return cls(gateway_from_environment(env))

    def approved_reviews(self) -> list[dict[str, Any]]:
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

    def commercial_terms(self) -> list[dict[str, Any]]:
        return self._gateway.query(
            "commercial_terms_reviews",
            "id,status,fulfilment_order_id",
            limit=5000,
        )

    def accepted_orders(self) -> list[dict[str, Any]]:
        return self._gateway.query(
            "fulfilment_orders",
            "id,state",
            filters=(
                DataFilter.in_("state", ("accepted", "paid", "fulfilled")),
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
            "id,fulfilment_order_id,delivery_outcome,conversion_outcome,buyer_satisfaction",
            limit=5000,
        )


class RequestConversionRepository:
    """Compatibility adapter for existing injected request fakes."""

    def __init__(self, request: Request) -> None:
        self._request = request

    def _get(self, path: str, query: str, *, surface: str) -> list[dict[str, Any]]:
        return _rows(
            self._request("GET", f"{path}?{query}"),
            surface=surface,
        )

    def approved_reviews(self) -> list[dict[str, Any]]:
        return self._get(
            "/rest/v1/buyer_candidate_reviews",
            "select=id%2Cstatus&status=eq.approved&limit=5000",
            surface="buyer_candidate_reviews",
        )

    def delivered_or_replied_intents(self) -> list[dict[str, Any]]:
        return self._get(
            "/rest/v1/outbound_intents",
            "select=id%2Cstatus%2Cnormalized_recipient%2Cmetadata&status=in.%28delivered%2Creplied%29&limit=5000",
            surface="outbound_intents",
        )

    def commercial_replies(self) -> list[dict[str, Any]]:
        return self._get(
            "/rest/v1/outbound_replies",
            "select=id%2Cintent_id%2Cclassification%2Cnormalized_from_contact&classification=in.%28positive%2Cquestion%2Cobjection%29&limit=5000",
            surface="outbound_replies",
        )

    def closer_cases(self) -> list[dict[str, Any]]:
        return self._get(
            "/rest/v1/closer_cases",
            "select=id%2Cstate&limit=5000",
            surface="closer_cases",
        )

    def commercial_terms(self) -> list[dict[str, Any]]:
        return self._get(
            "/rest/v1/commercial_terms_reviews",
            "select=id%2Cstatus%2Cfulfilment_order_id&limit=5000",
            surface="commercial_terms_reviews",
        )

    def accepted_orders(self) -> list[dict[str, Any]]:
        return self._get(
            "/rest/v1/fulfilment_orders",
            "select=id%2Cstate&state=in.%28accepted%2Cpaid%2Cfulfilled%29&limit=5000",
            surface="fulfilment_orders",
        )

    def payment_evidence(self) -> list[dict[str, Any]]:
        return self._get(
            "/rest/v1/bsc_payment_evidence",
            "select=id%2Cfulfilment_order_id&limit=5000",
            surface="bsc_payment_evidence",
        )

    def commercial_outcomes(self) -> list[dict[str, Any]]:
        return self._get(
            "/rest/v1/commercial_outcomes",
            "select=id%2Cfulfilment_order_id%2Cdelivery_outcome%2Cconversion_outcome%2Cbuyer_satisfaction&limit=5000",
            surface="commercial_outcomes",
        )
