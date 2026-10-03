"""Canonical outbound deliverability snapshot and traffic-light health classification."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class DeliverabilityThresholds:
    """Empire internal thresholds; intentionally conservative."""

    green_bounce_rate: float = 0.01
    amber_bounce_rate: float = 0.02
    red_bounce_rate: float = 0.03
    green_complaint_rate: float = 0.0002
    amber_complaint_rate: float = 0.0005
    red_complaint_rate: float = 0.0008
    min_delivery_rate: float = 0.97


def _number(row: Mapping[str, Any], key: str) -> float:
    try:
        return float(row.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def _rate(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def build_deliverability_snapshot(
    rows: Iterable[Mapping[str, Any]],
    *,
    thresholds: DeliverabilityThresholds | None = None,
) -> dict[str, Any]:
    thresholds = thresholds or DeliverabilityThresholds()
    totals = {
        "sent": 0.0,
        "delivered": 0.0,
        "bounced": 0.0,
        "bounced_permanent": 0.0,
        "bounced_transient": 0.0,
        "complained": 0.0,
        "suppressed": 0.0,
        "failed": 0.0,
        "delivery_delayed": 0.0,
    }

    domains: dict[str, dict[str, float]] = {}
    for row in rows:
        domain = str(row.get("domain") or "unknown")
        bucket = domains.setdefault(domain, {key: 0.0 for key in totals})
        for key in totals:
            value = _number(row, key)
            totals[key] += value
            bucket[key] += value

    sent = totals["sent"]
    delivery_rate = _rate(totals["delivered"], sent)
    bounce_rate = _rate(totals["bounced"], sent)
    permanent_bounce_rate = _rate(totals["bounced_permanent"], sent)
    complaint_rate = _rate(totals["complained"], sent)
    suppression_rate = _rate(totals["suppressed"], sent)

    hard_holds: list[str] = []
    warnings: list[str] = []

    if complaint_rate >= thresholds.red_complaint_rate:
        hard_holds.append("complaint_rate_red")
    elif complaint_rate >= thresholds.amber_complaint_rate:
        warnings.append("complaint_rate_amber")

    if bounce_rate >= thresholds.red_bounce_rate:
        hard_holds.append("bounce_rate_red")
    elif bounce_rate >= thresholds.amber_bounce_rate:
        warnings.append("bounce_rate_amber")
    elif bounce_rate >= thresholds.green_bounce_rate:
        warnings.append("bounce_rate_elevated")

    if delivery_rate and delivery_rate < thresholds.min_delivery_rate:
        warnings.append("delivery_rate_below_target")

    if totals["bounced_permanent"]:
        warnings.append("permanent_bounces_present")
    if totals["delivery_delayed"]:
        warnings.append("delivery_delays_present")
    if totals["failed"]:
        warnings.append("provider_failures_present")

    if hard_holds:
        health = "HOLD"
    elif warnings:
        health = "AMBER"
    else:
        health = "GREEN"

    domain_snapshots: dict[str, dict[str, Any]] = {}
    for domain, values in sorted(domains.items()):
        domain_sent = values["sent"]
        domain_snapshots[domain] = {
            **{key: int(value) for key, value in values.items()},
            "delivery_rate": _rate(values["delivered"], domain_sent),
            "bounce_rate": _rate(values["bounced"], domain_sent),
            "complaint_rate": _rate(values["complained"], domain_sent),
        }

    return {
        "health": health,
        "sent": int(sent),
        "delivered": int(totals["delivered"]),
        "bounced": int(totals["bounced"]),
        "bounced_permanent": int(totals["bounced_permanent"]),
        "bounced_transient": int(totals["bounced_transient"]),
        "complained": int(totals["complained"]),
        "suppressed": int(totals["suppressed"]),
        "failed": int(totals["failed"]),
        "delivery_delayed": int(totals["delivery_delayed"]),
        "delivery_rate": delivery_rate,
        "bounce_rate": bounce_rate,
        "permanent_bounce_rate": permanent_bounce_rate,
        "complaint_rate": complaint_rate,
        "suppression_rate": suppression_rate,
        "hard_holds": hard_holds,
        "warnings": warnings,
        "domains": domain_snapshots,
        "inbox_placement_rate": None,
        "inbox_placement_status": "requires_seed_or_mailbox_placement_measurement",
    }
