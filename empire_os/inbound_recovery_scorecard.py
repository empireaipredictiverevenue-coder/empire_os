"""Executive recovery scorecard based strictly on scoped, evidenced aggregates.

No forecasted pounds, market size, sale value, or spend can become realized
revenue here. Percentages are null if there is no eligible denominator.
"""
from __future__ import annotations

from typing import Any


def _pct(numerator: int, denominator: int) -> float | None:
    return round(numerator * 100.0 / denominator, 1) if denominator > 0 else None


def build_inbound_recovery_scorecard(report: dict[str, Any]) -> dict[str, Any]:
    """Operational funnel plus evidence quality; no money/call outcome inflation."""
    required = (
        "tenant_id", "calls_observed", "missed_calls", "answered_calls",
        "callback_requests", "verified_connections", "confirmed_bookings",
        "verified_recovered_calls", "verified_paid_recovery_minor_by_currency",
    )
    if any(key not in report for key in required):
        raise ValueError("incomplete_recovery_report")
    observed = report["calls_observed"]
    missed = report["missed_calls"]
    recovered = report["verified_recovered_calls"]
    for key in required[1:-1]:
        value = report[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("invalid_recovery_count")
    if missed > observed or recovered > missed:
        raise ValueError("inconsistent_recovery_funnel")
    money = report["verified_paid_recovery_minor_by_currency"]
    if not isinstance(money, dict) or any(
        not isinstance(currency, str) or len(currency) != 3
        or isinstance(amount, bool) or not isinstance(amount, int) or amount < 0
        for currency, amount in money.items()
    ):
        raise ValueError("invalid_paid_recovery_receipts")
    return {
        "tenant_id": report["tenant_id"],
        "environment": report.get("store", report.get("mode", "unverified_origin")),
        "evidence_level": "offline_not_a_live_revenue_claim",
        "calls_observed": observed,
        "answered_calls": report["answered_calls"],
        "missed_calls": missed,
        "open_missed_opportunities": missed - recovered,
        "verified_recovered_calls": recovered,
        "missed_call_rate_percent": _pct(missed, observed),
        "verified_missed_recovery_rate_percent": _pct(recovered, missed),
        "callback_requests": report["callback_requests"],
        "verified_connections": report["verified_connections"],
        "confirmed_bookings": report["confirmed_bookings"],
        "verified_paid_recovery_minor_by_currency": dict(sorted(money.items())),
        "revenue_estimates_included": False,
        "pricing_activated": False,
        "outbound_sent": False,
        "actions": (
            ["Review unresolved missed calls with the authorized business operator"]
            if missed > recovered else []
        ),
    }
