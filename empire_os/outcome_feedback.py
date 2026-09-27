"""Phase 3F feedback normalization for revenue intelligence and Astra."""
from __future__ import annotations

from statistics import mean
from typing import Any, Iterable, Mapping


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def feedback_to_revenue_features(row: Mapping[str, Any]) -> dict[str, Any]:
    conversion = str(row.get("conversion_outcome") or "unknown").lower()
    actual_revenue = bool(row.get("actual_revenue"))
    satisfaction = row.get("buyer_satisfaction")
    replied = conversion not in {"unknown", "no_response"}

    return {
        "replied": replied,
        "engaged": conversion in {"qualified", "booked", "won"},
        "previous_purchase": actual_revenue,
        "conversion_probability_target": (
            1.0 if conversion == "won"
            else 0.0 if conversion in {"lost", "no_response"}
            else None
        ),
        "buyer_satisfaction": (
            round(_num(satisfaction), 2) if satisfaction is not None else None
        ),
        "actual_revenue_cents": int(_num(row.get("actual_revenue_cents"))),
        "actual_cost_cents": int(_num(row.get("actual_cost_cents"))),
        "gross_profit_cents": int(_num(row.get("gross_profit_cents"))),
        "fulfilment_order_id": row.get("fulfilment_order_id"),
        "prospect_id": row.get("prospect_id"),
        "buyer_id": row.get("buyer_id"),
        "opportunity_id": row.get("opportunity_id"),
    }


def summarize_outcomes(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    items = list(rows)
    converted = [
        row for row in items
        if str(row.get("conversion_outcome") or "").lower() == "won"
    ]
    satisfaction = [
        _num(row.get("buyer_satisfaction"))
        for row in items
        if row.get("buyer_satisfaction") is not None
    ]
    revenue = sum(int(_num(row.get("actual_revenue_cents"))) for row in items)
    cost = sum(int(_num(row.get("actual_cost_cents"))) for row in items)
    profit = sum(int(_num(row.get("gross_profit_cents"))) for row in items)

    return {
        "orders": len(items),
        "converted": len(converted),
        "conversion_rate": round(len(converted) / len(items), 4) if items else 0.0,
        "actual_revenue_cents": revenue,
        "actual_cost_cents": cost,
        "gross_profit_cents": profit,
        "gross_margin_rate": round(profit / revenue, 4) if revenue > 0 else 0.0,
        "average_buyer_satisfaction": (
            round(mean(satisfaction), 2) if satisfaction else None
        ),
    }
