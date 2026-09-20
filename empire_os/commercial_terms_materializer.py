"""Materialize evidence-backed commercial terms proposals.

This worker may create a pending commercial-terms review only when canonical
capacity, verified price evidence, observed acquisition cost, observed
fulfilment cost and positive margin are all present. It never approves terms,
records buyer acceptance, creates a payment request, moves funds, fulfils an
order or recognizes revenue.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Mapping
import urllib.parse

from empire_os.commercial_terms_readiness import (
    CommercialTermsReadinessEvidence,
    review_commercial_terms_readiness,
)
from empire_os.qualification_worker_v2 import request_json


Request = Callable[..., Any]


@dataclass(frozen=True)
class CommercialTermsMaterializerResult:
    scanned: int
    ready: int
    proposed: int
    blocked: int
    blocker_counts: tuple[tuple[str, int], ...]
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "scanned": self.scanned,
            "ready": self.ready,
            "proposed": self.proposed,
            "blocked": self.blocked,
            "blocker_counts": dict(self.blocker_counts),
            "errors": list(self.errors),
            "terms_approved": False,
            "buyer_acceptance_recorded": False,
            "payment_request_created": False,
            "funds_movement": False,
            "actual_revenue": False,
        }


def _rows(
    request: Request,
    path: str,
    params: Mapping[str, Any],
) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            key: str(value)
            for key, value in params.items()
            if value is not None
        }
    )
    value = request("GET", f"{path}?{query}") or []
    if not isinstance(value, list):
        raise ValueError(f"{path} projection must be a list")
    return [row for row in value if isinstance(row, dict)]


def _rpc(
    request: Request,
    name: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    result = request(
        "POST",
        f"/rest/v1/rpc/{name}",
        payload=dict(payload),
    ) or {}
    if isinstance(result, list) and len(result) == 1:
        result = result[0]
    if not isinstance(result, dict):
        raise ValueError(f"{name} returned invalid payload")
    return result


def _item(
    value: Any,
) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def run_commercial_terms_materializer(
    request: Request = request_json,
    *,
    scan_limit: int = 25,
    proposal_limit: int = 5,
) -> CommercialTermsMaterializerResult:
    bounded = max(1, min(int(scan_limit), 100))
    cap = max(1, min(int(proposal_limit), 20))
    cases = _rows(
        request,
        "/rest/v1/closer_cases",
        {
            "select": (
                "id,state,buyer_id,prospect_id,fulfilment_order_id,updated_at"
            ),
            "fulfilment_order_id": "not.is.null",
            "state": "in.(engaged,qualified,proposal_ready)",
            "order": "updated_at.desc",
            "limit": bounded,
        },
    )

    ready = proposed = blocked = 0
    blockers: Counter[str] = Counter()
    errors: list[str] = []

    for case in cases:
        if proposed >= cap:
            break
        case_id = str(case.get("id") or "").strip()
        order_id = str(case.get("fulfilment_order_id") or "").strip()
        buyer_id = str(case.get("buyer_id") or "").strip()
        prospect_id = str(case.get("prospect_id") or "").strip()
        if not all((case_id, order_id, buyer_id, prospect_id)):
            blocked += 1
            blockers["case_binding_incomplete"] += 1
            continue

        try:
            orders = _rows(
                request,
                "/rest/v1/fulfilment_orders",
                {
                    "select": "id,state,buyer_id,prospect_id",
                    "id": f"eq.{order_id}",
                    "limit": 1,
                },
            )
            capacities = _rows(
                request,
                "/rest/v1/buyer_capacity_intakes",
                {
                    "select": (
                        "id,state,territory,daily_cap,delivery_route,"
                        "delivery_reference"
                    ),
                    "closer_case_id": f"eq.{case_id}",
                    "limit": 1,
                },
            )
            if not orders:
                raise ValueError("fulfilment order not found")
            order = orders[0]
            capacity = capacities[0] if capacities else {}
            evidence = _rpc(
                request,
                "get_verified_terms_evidence",
                {"p_fulfilment_order_id": order_id},
            )

            price = _item(evidence.get("price"))
            acquisition = _item(evidence.get("acquisition_cost"))
            fulfilment = _item(evidence.get("fulfilment_cost"))

            review = review_commercial_terms_readiness(
                CommercialTermsReadinessEvidence(
                    closer_case_id=case_id,
                    fulfilment_order_id=order_id,
                    buyer_id=buyer_id,
                    prospect_id=prospect_id,
                    order_state=str(order.get("state") or ""),
                    buyer_conversation_observed=True,
                    capacity_intake_state=str(capacity.get("state") or ""),
                    capacity_evidence_ref=(
                        f"buyer_capacity_intake:{capacity.get('id')}"
                        if capacity.get("id")
                        else None
                    ),
                    territory=capacity.get("territory"),
                    daily_cap=capacity.get("daily_cap"),
                    delivery_route=capacity.get("delivery_route"),
                    proposed_price_cents=(
                        int(price["amount_cents"])
                        if price and price.get("amount_cents") is not None
                        else None
                    ),
                    verified_price_evidence_ref=(
                        f"commercial_evidence:{price.get('evidence_id')}"
                        if price and price.get("evidence_id")
                        else None
                    ),
                    acquisition_cost_cents=(
                        int(acquisition["amount_cents"])
                        if acquisition
                        and acquisition.get("amount_cents") is not None
                        else None
                    ),
                    acquisition_cost_evidence_ref=(
                        f"commercial_evidence:{acquisition.get('evidence_id')}"
                        if acquisition and acquisition.get("evidence_id")
                        else None
                    ),
                    fulfilment_cost_cents=(
                        int(fulfilment["amount_cents"])
                        if fulfilment
                        and fulfilment.get("amount_cents") is not None
                        else None
                    ),
                    fulfilment_cost_evidence_ref=(
                        f"commercial_evidence:{fulfilment.get('evidence_id')}"
                        if fulfilment and fulfilment.get("evidence_id")
                        else None
                    ),
                )
            )

            if not review.ready_for_terms_proposal:
                blocked += 1
                blockers.update(review.blockers)
                continue

            ready += 1
            packet = dict(review.terms_packet or {})
            price_cents = int(packet["price_cents"])
            acquisition_cents = int(packet["acquisition_cost_cents"])
            fulfilment_cents = int(packet["fulfilment_cost_cents"])
            evidence_key = ":".join(review.evidence_refs)
            result = _rpc(
                request,
                "propose_commercial_terms",
                {
                    "p_fulfilment_order_id": order_id,
                    "p_price_cents": price_cents,
                    "p_acquisition_cost_cents": acquisition_cents,
                    "p_fulfilment_cost_cents": fulfilment_cents,
                    "p_terms": packet,
                    "p_idempotency_key": (
                        f"terms:{order_id}:{evidence_key}"
                    )[:240],
                    "p_actor": "astra-commercial-terms-planner",
                },
            )
            if str(result.get("decision") or "") in {"proposed", "existing"}:
                proposed += 1
            else:
                errors.append(
                    f"{case_id}:terms_proposal_returned_no_decision"
                )
        except Exception as exc:
            errors.append(
                f"{case_id}:{type(exc).__name__}:{str(exc)[:180]}"
            )

    return CommercialTermsMaterializerResult(
        scanned=len(cases),
        ready=ready,
        proposed=proposed,
        blocked=blocked,
        blocker_counts=tuple(sorted(blockers.items())),
        errors=tuple(errors),
    )
