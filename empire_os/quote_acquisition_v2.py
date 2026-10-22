"""Quote acquisition v2: deterministic evidence-based ranking and unit economics.

An OBSERVE-only adapter for canonical EmpireOS intake/matching owners.
Never treats forecasts, rankings or unverified prices as earned revenue.
"""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any
from empire_os.quote_acquisition_review import review_quote_request

SCHEMA = "empire.quote_acquisition.v2"
MAX_CANDIDATES = 50


def _amount(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, str, Decimal)):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return amount if amount.is_finite() and 0 <= amount <= 1_000_000 else None


def rank_quote_buyers(*, vertical: str, request: Mapping[str, Any],
                      candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not isinstance(candidates, (list, tuple)) or len(candidates) > MAX_CANDIDATES:
        raise ValueError("bounded buyer candidate list required")
    if not isinstance(request, Mapping):
        raise ValueError("request mapping required")
    output = []
    seen = set()
    for index, buyer in enumerate(candidates):
        if not isinstance(buyer, Mapping):
            raise ValueError("buyer mapping required")
        buyer_key = buyer.get("buyer_ref")
        if not isinstance(buyer_key, str) or not buyer_key.strip() or len(buyer_key) > 120:
            raise ValueError("opaque buyer_ref required")
        if buyer_key in seen:
            raise ValueError("duplicate buyer_ref")
        seen.add(buyer_key)
        review = review_quote_request(vertical=vertical, request=request, buyer=buyer)
        fully_eligible = review["match_review"] == "READY_FOR_HUMAN_REVIEW"
        verified = buyer.get("price_verified") is True
        price = _amount(buyer.get("accepted_lead_price")) if verified else None
        cost = _amount(buyer.get("verified_delivery_cost")) if buyer.get("cost_verified") is True else None
        margin = price - cost if price is not None and cost is not None else None
        # Rank by eligibility, verified margin (when known), then capacity; never contact automatically.
        capacity = buyer.get("remaining_capacity")
        capacity = capacity if isinstance(capacity, int) and not isinstance(capacity, bool) and 0 <= capacity <= 1_000_000 and buyer.get("capacity_verified") is True else None
        if capacity == 0:
            fully_eligible = False
        output.append({
            "buyer_ref": buyer_key,
            "status": "READY_FOR_HUMAN_REVIEW" if fully_eligible else "HOLD",
            "missing_evidence": review["missing_evidence"] + (["buyer.remaining_capacity"] if capacity == 0 else []),
            "verified_unit_margin": str(margin) if margin is not None else None,
            "margin_currency": buyer.get("currency") if margin is not None and buyer.get("currency") in ("GBP", "USD") else None,
            "remaining_capacity": capacity,
            "_sort": (int(fully_eligible), int(margin is not None), margin if margin is not None else Decimal("-1"), capacity if capacity is not None else -1, -index),
        })
    output.sort(key=lambda item: item["_sort"], reverse=True)
    for item in output:
        del item["_sort"]
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "vertical": vertical,
        "candidate_count": len(output),
        "ranked_candidates": output,
        "next_step": "Founder reviews evidence and selects one contracted buyer; no automatic distribution",
        "outbound_authorized": False,
        "customer_data_disclosed": False,
        "crm_writes": False,
        "payment_execution": False,
        "realised_revenue": None,
    }
