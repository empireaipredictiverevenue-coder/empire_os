"""Hypothetical B2B economics, deliberately disconnected from real revenue."""
from __future__ import annotations
from decimal import Decimal, InvalidOperation

CURRENCY = "USD"
SCHEMA = "empire.claims_exchange.scenario_v2"


def _amount(value: object) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("invalid_amount")
    try:
        num = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("invalid_amount") from None
    if not num.is_finite() or num < 0 or num > Decimal("100000000"):
        raise ValueError("invalid_amount")
    return num


def b2b_scenario(*, contractor_subscribers: int = 0, contractor_mrr: object = "2500",
                 network_subscribers: int = 0, network_mrr: object = "5000",
                 pilots_sold: int = 0, pilot_price: object = "1500") -> dict:
    """Planning math only. Never encode a regulated claim percentage here."""
    counts = (contractor_subscribers, network_subscribers, pilots_sold)
    if any(isinstance(n, bool) or not isinstance(n, int) or n < 0 or n > 100000 for n in counts):
        raise ValueError("invalid_customer_counts")
    c, n, p = map(_amount, (contractor_mrr, network_mrr, pilot_price))
    monthly = c * contractor_subscribers + n * network_subscribers
    once = p * pilots_sold
    return {
        "schema": SCHEMA, "currency": CURRENCY,
        "monthly_recurring_scenario": str(monthly.quantize(Decimal("0.01"))),
        "one_time_pilot_scenario": str(once.quantize(Decimal("0.01"))),
        "combined_first_month_scenario": str((monthly + once).quantize(Decimal("0.01"))),
        "realised_revenue": "0.00", "verified_orders": 0, "verified_payments": 0,
        "settlement_percentage_assumed": False, "scenario_not_a_forecast": True,
    }
