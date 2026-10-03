"""Infrastructure concentration risk for sender reputation portfolios."""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping


def _hhi(values: list[str]) -> float:
    if not values:
        return 0.0
    counts = Counter(values)
    total = len(values)
    return sum((count / total) ** 2 for count in counts.values())


def evaluate_concentration(
    senders: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    rows = [dict(row) for row in senders if row.get("enabled") is True]

    domains = [str(row.get("domain") or "unknown") for row in rows]
    transports = [str(row.get("transport_key") or "unknown") for row in rows]
    ip_pools = [str(row.get("ip_pool_key") or "unknown") for row in rows]

    metrics = {
        "domain_hhi": round(_hhi(domains), 4),
        "transport_hhi": round(_hhi(transports), 4),
        "ip_pool_hhi": round(_hhi(ip_pools), 4),
    }
    worst = max(metrics.values(), default=0.0)

    if worst >= 0.80 and len(rows) >= 3:
        posture = "HIGH_CONCENTRATION"
    elif worst >= 0.50 and len(rows) >= 3:
        posture = "MODERATE_CONCENTRATION"
    else:
        posture = "DIVERSIFIED_OR_SMALL"

    return {
        "posture": posture,
        "enabled_senders": len(rows),
        **metrics,
        "meaning": "blast_radius_concentration_not_send_authority",
    }
