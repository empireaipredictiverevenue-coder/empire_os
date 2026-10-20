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
from empire_os.sb import request_json


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
                    "select": "id,state,buyer_id,prospect_id,product_id",
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
            if (
                str(order.get("buyer_id") or "") != buyer_id
                or str(order.get("prospect_id") or "") != prospect_id
            ):
                blocked += 1
                blockers["fulfilment_order_binding_mismatch"] += 1
                continue

            product_id = str(order.get("product_id") or "").strip()
            if not product_id:
                blocked += 1
                blockers["fulfilment_order_product_missing"] += 1
                continue

            products = _rows(
                request,
                "/rest/v1/commercial_products",
                {
                    "select": "id,product_code,active",
                    "id": f"eq.{product_id}",
                    "limit": 1,
                },
            )
            if len(products) != 1:
                blocked += 1
                blockers["commercial_product_identity_missing"] += 1
                continue

            product = products[0]
            product_code = str(product.get("product_code") or "").strip()
            if not product_code or product.get("active") is not True:
                blocked += 1
                blockers["commercial_product_inactive_or_invalid"] += 1
                continue

            capacity = capacities[0] if capacities else {}
            catalog = _rpc(
                request,
                "get_commercial_product_readiness",
                {"p_product_code": product_code},
            )
            if catalog.get("binding_terms_ready") is not True:
                blocked += 1
                catalog_blockers = catalog.get("blockers")
                if isinstance(catalog_blockers, list) and catalog_blockers:
                    blockers.update(
                        f"catalog_{str(value)}"
                        for value in catalog_blockers
                    )
                else:
                    blockers["commercial_product_catalog_not_ready"] += 1
                continue

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
                    product_id=product_id,
                    product_code=product_code,
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
                        f"terms:{order_id}:{product_code}:{evidence_key}"
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


def build_persisted_terms_stage(order, review, events, *, context, as_of):
    """Observe approved installed terms from existing reviews/events, without RPCs."""
    import re
    from empire_os.conversation_qualification import _observed_stage_row, _stage_time
    for row in (order, review, *events):
        _observed_stage_row(row, as_of=as_of)
        for key in ("tenant_id", "buyer_id", "prospect_id", "opportunity_id", "closer_case_id", "outbound_intent_id"):
            if row.get(key) is not None and row[key] != context.get(key):
                raise ValueError(f"commercial terms {key} mismatch")
    payload = order.get("commercial_payload") or {}
    terms = review.get("terms") or {}
    for row in (terms, payload, *((event.get("payload") or {}) for event in events)):
        for key in ("tenant_id", "buyer_id", "prospect_id", "opportunity_id", "closer_case_id", "outbound_intent_id", "fulfilment_order_id"):
            if row.get(key) is not None and row[key] != context.get(key):
                raise ValueError(f"terms evidence {key} mismatch")
    if order.get("id") != context.get("fulfilment_order_id") or review.get("fulfilment_order_id") != order.get("id"):
        raise ValueError("terms canonical order mismatch")
    if order.get("state") not in ("offered", "accepted", "delivered", "confirmed", "invoiced", "paid", "settled", "outcome_captured"):
        raise ValueError("approved terms contradict canonical order progression")
    if review.get("status") != "approved":
        raise ValueError("approved commercial terms review required")
    for row in (review, terms, payload):
        if row.get("expires_at") and _stage_time(row["expires_at"]) <= as_of:
            raise ValueError("expired commercial terms")
    if (not review.get("id") or not review.get("decided_by")
            or type(review.get("price_cents")) is not int or review["price_cents"] <= 0
            or str(terms.get("currency") or "").upper() != "USD"
            or str(terms.get("settlement_asset") or "").upper() != "USDT"
            or str(terms.get("settlement_chain") or "").upper() != "BSC"
            or terms.get("price_cents", review.get("price_cents")) != review.get("price_cents")
            or not re.fullmatch(r"[0-9a-f]{64}", str(review.get("commercial_terms_sha256") or ""))):
        raise ValueError("approved terms identity price currency and provenance required")
    decided_at = _stage_time(review.get("decided_at"))
    if _stage_time(review.get("proposed_at")) > decided_at or decided_at > as_of:
        raise ValueError("invalid commercial terms decision time")
    if (payload.get("commercial_terms_review_id") != review["id"]
            or payload.get("commercial_terms_sha256") != review["commercial_terms_sha256"]
            or payload.get("commercial_terms") != terms or order.get("price_cents") != review["price_cents"]
            or payload.get("terms_approved_by") != review["decided_by"]
            or _stage_time(payload.get("terms_approved_at")) != decided_at):
        raise ValueError("approved review not coherently installed on canonical order")
    for event in events:
        if event.get("review_id") != review["id"] or event.get("fulfilment_order_id") != order["id"]:
            raise ValueError("commercial terms event identity mismatch")
    approvals = [e for e in events if e.get("event_type") == "approved"]
    if len(approvals) != 1:
        raise ValueError("unique canonical terms approval event required")
    approval = approvals[0]
    if (not approval.get("id") or approval.get("actor") != review["decided_by"]
            or (approval.get("payload") or {}).get("commercial_terms_sha256") != review["commercial_terms_sha256"]
            or _stage_time(approval.get("occurred_at")) < decided_at):
        raise ValueError("terms approval evidence mismatch")
    state, accepted_at = "APPROVED", None
    acceptance_keys = ("buyer_accepted_at", "buyer_acceptance_kind", "buyer_acceptance_reference", "buyer_acceptance_recorded_by")
    accepted_events = [e for e in events if e.get("event_type") == "accepted"]
    if any(payload.get(key) for key in acceptance_keys) or accepted_events:
        if order.get("state") == "offered":
            raise ValueError("buyer acceptance contradicts canonical order progression")
        if len(accepted_events) != 1 or not all(payload.get(key) for key in acceptance_keys):
            raise ValueError("incomplete canonical buyer acceptance")
        accepted = accepted_events[0]
        evidence = accepted.get("payload") or {}
        accepted_clock = _stage_time(payload["buyer_accepted_at"])
        if (not accepted.get("id") or payload["buyer_acceptance_kind"] not in ("outbound_reply", "signed_agreement", "manual_verified")
                or evidence.get("evidence_kind") != payload["buyer_acceptance_kind"]
                or evidence.get("evidence_reference") != payload["buyer_acceptance_reference"]
                or accepted.get("actor") != payload["buyer_acceptance_recorded_by"]
                or evidence.get("commercial_terms_sha256") != review["commercial_terms_sha256"]
                or _stage_time(evidence.get("accepted_at")) != accepted_clock
                or accepted_clock < decided_at or _stage_time(accepted.get("occurred_at")) < accepted_clock):
            raise ValueError("canonical buyer acceptance evidence mismatch")
        state, accepted_at = "ACCEPTED", accepted_clock.isoformat()
    if any(e.get("event_type") == "rejected" for e in events):
        raise ValueError("contradictory rejected terms evidence")
    return {**context, "schema_version": "empire.outreach-commercial-terms.v1", "state": state,
            "stage_ref": "canonical:commercial_terms_reviews:" + review["id"],
            "terms_ref": "canonical:commercial_terms_reviews:" + review["id"],
            "review_ref": "canonical:commercial_terms_reviews:" + review["id"],
            "price_cents": review["price_cents"], "currency": "USD",
            "created_at": review["proposed_at"], "approved_at": decided_at.isoformat(), "accepted_at": accepted_at,
            "evidence_refs": ["canonical:commercial_terms_events:" + approval["id"]]
                + (["canonical:commercial_terms_events:" + accepted_events[0]["id"]] if state == "ACCEPTED" else []),
            "source": "persisted_approved_installed_terms", "canonical_order": dict(order),
            "terms_review": dict(review), "terms_events": list(events), "execution_authority": "none"}


def validate_commercial_terms_stage(stage, record, *, as_of):
    from empire_os.conversation_qualification import _validate_stage_binding
    _validate_stage_binding(stage, record, as_of=as_of)
    if stage.get("schema_version") != "empire.outreach-commercial-terms.v1":
        raise ValueError("canonical commercial terms contract required")
    expected = build_persisted_terms_stage(stage.get("canonical_order"), stage.get("terms_review"),
        stage.get("terms_events"), context=stage, as_of=as_of)
    for key in ("state", "stage_ref", "terms_ref", "review_ref", "price_cents", "currency", "approved_at", "accepted_at", "evidence_refs", "source"):
        if stage.get(key) != expected[key]:
            raise ValueError("commercial terms evidence projection mismatch")
