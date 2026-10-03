"""Provider-independent Empire deliverability health service."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from empire_os.outbound_deliverability_provider import (
    DeliverabilityMetricsProvider,
    rolling_windows,
)
from empire_os.outbound_deliverability_snapshot import build_deliverability_snapshot


def metric_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if isinstance(data, list):
        rows: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, Mapping):
                continue
            row = dict(item)
            if "domain" not in row:
                row["domain"] = (
                    row.get("domain_name")
                    or row.get("domain_id")
                    or "unknown"
                )
            rows.append(row)
        return rows

    totals = payload.get("totals")
    if isinstance(totals, Mapping):
        return [{"domain": "all", **dict(totals)}]
    return []


def build_rolling_health(
    provider: DeliverabilityMetricsProvider,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    raw = rolling_windows(provider, now=now)
    windows = {
        label: build_deliverability_snapshot(metric_rows(payload))
        for label, payload in raw.items()
    }

    health_order = {"GREEN": 0, "AMBER": 1, "HOLD": 2}
    worst = max(
        (window["health"] for window in windows.values()),
        key=lambda value: health_order.get(value, 99),
    )

    return {
        "overall_health": worst,
        "windows": windows,
        "source": "provider_metrics_adapter",
        "inbox_placement": {
            "status": "separate_measurement_required",
            "reason": "delivery_event_does_not_prove_inbox_placement",
        },
    }
