"""Evidence-backed outcome calibration for Astra.

Consumes only the bounded Phase 3F commercial outcome projection.
No model weights, commercial state, or external systems are mutated here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from empire_os.outcome_feedback import summarize_outcomes


@dataclass(frozen=True)
class OutcomeCalibration:
    sample_size: int
    converted: int
    actual_revenue_cents: int
    actual_cost_cents: int
    gross_profit_cents: int
    conversion_rate: float
    gross_margin_rate: float
    average_buyer_satisfaction: float | None
    negative_margin_orders: int
    repeat_purchase_orders: int
    calibration_ready: bool
    calibration_reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_outcome_calibration(
    rows: Iterable[Mapping[str, Any]],
    *,
    min_samples: int = 20,
    min_conversions: int = 5,
) -> OutcomeCalibration:
    """Summarize real Phase 3F outcomes into a deterministic calibration view."""
    items = list(rows)
    summary = summarize_outcomes(items)

    negative_margin_orders = sum(
        int(row.get("gross_profit_cents") or 0) < 0
        for row in items
    )
    repeat_purchase_orders = sum(
        bool(row.get("previous_purchase"))
        for row in items
    )

    sample_floor = max(int(min_samples), 1)
    conversion_floor = max(int(min_conversions), 1)
    enough_samples = len(items) >= sample_floor
    enough_conversions = int(summary["converted"]) >= conversion_floor
    calibration_ready = enough_samples and enough_conversions

    if calibration_ready:
        reason = "real_outcome_threshold_met"
    elif not enough_samples:
        reason = "insufficient_real_outcome_samples"
    else:
        reason = "insufficient_real_conversions"


    return OutcomeCalibration(
        sample_size=len(items),
        converted=int(summary["converted"]),
        actual_revenue_cents=int(summary["actual_revenue_cents"]),
        actual_cost_cents=int(summary["actual_cost_cents"]),
        gross_profit_cents=int(summary["gross_profit_cents"]),
        conversion_rate=float(summary["conversion_rate"]),
        gross_margin_rate=float(summary["gross_margin_rate"]),
        average_buyer_satisfaction=summary["average_buyer_satisfaction"],
        negative_margin_orders=negative_margin_orders,
        repeat_purchase_orders=repeat_purchase_orders,
        calibration_ready=calibration_ready,
        calibration_reason=reason,
    )


def _optional_int(row: Mapping[str, Any], key: str) -> int | None:
    value = row.get(key)
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def buyer_history_features(row: Mapping[str, Any]) -> dict[str, Any]:
    """Expose observed buyer-history features without filling missing evidence."""
    raw_conversion = row.get("conversion_outcome")
    conversion = (
        str(raw_conversion).strip().lower()
        if raw_conversion is not None
        else None
    )

    replied = (
        conversion not in {"unknown", "no_response", ""}
        if conversion is not None
        else None
    )
    engaged = (
        conversion in {"qualified", "booked", "won"}
        if conversion is not None
        else None
    )

    return {
        "replied": replied,
        "engaged": engaged,
        "previous_purchase": (
            bool(row["previous_purchase"])
            if "previous_purchase" in row and row["previous_purchase"] is not None
            else None
        ),
        "historical_buyer_satisfaction": row.get("buyer_satisfaction"),
        "historical_gross_profit_cents": _optional_int(
            row, "gross_profit_cents"
        ),
        "fulfilment_order_id": row.get("fulfilment_order_id"),
        "prospect_id": row.get("prospect_id"),
        "buyer_id": row.get("buyer_id"),
        "opportunity_id": row.get("opportunity_id"),
    }
