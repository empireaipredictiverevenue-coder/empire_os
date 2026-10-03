"""Rebuild bounded Ringleader health state from persisted EmpireDB evidence."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping


_RATE_METRICS = {
    "bounce_rate",
    "complaint_rate",
    "delivery_rate",
    "inbox_placement_rate",
    "deferral_rate",
}


def replay_health_state(
    observations: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Deterministically reconstruct latest metrics by asset from append-only evidence."""

    latest: dict[str, dict[str, Any]] = {}
    history: dict[str, list[dict[str, Any]]] = defaultdict(list)

    rows = sorted(
        (dict(row) for row in observations),
        key=lambda row: (
            str(row.get("observed_at") or ""),
            str(row.get("id") or ""),
        ),
    )

    for row in rows:
        asset = (
            str(row.get("mailbox_key") or "").strip()
            or str(row.get("domain") or "").strip()
            or str(row.get("transport_key") or "").strip()
            or str(row.get("recipient_mx") or "").strip()
        )
        metric = str(row.get("metric_name") or "").strip()
        if not asset or not metric:
            continue

        state = latest.setdefault(asset, {"asset_key": asset, "metrics": {}})
        state["metrics"][metric] = row.get("metric_value")
        state["last_observed_at"] = row.get("observed_at")
        state["last_source"] = row.get("source")

        if metric in _RATE_METRICS:
            history[asset].append({
                metric: row.get("metric_value"),
                "observed_at": row.get("observed_at"),
            })

    return {
        "assets": latest,
        "rate_history": dict(history),
        "replay_source": "empiredb_append_only_evidence",
        "mutation_authorized": False,
    }
