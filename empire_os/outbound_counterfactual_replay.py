"""Counterfactual replay for outbound reputation policy."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from empire_os.outbound_deliverability_snapshot import (
    DeliverabilityThresholds,
    build_deliverability_snapshot,
)


def replay_threshold_policy(
    windows: Iterable[Mapping[str, Any]],
    *,
    proposed: DeliverabilityThresholds,
) -> dict[str, Any]:
    outcomes: list[dict[str, Any]] = []
    counts = {"GREEN": 0, "AMBER": 0, "HOLD": 0}

    for index, raw in enumerate(windows):
        row = dict(raw)
        provider_rows = row.get("rows") or []
        result = build_deliverability_snapshot(
            provider_rows,
            thresholds=proposed,
        )
        health = result["health"]
        counts[health] = counts.get(health, 0) + 1
        outcomes.append({
            "index": index,
            "health": health,
            "sent": result["sent"],
            "bounce_rate": result["bounce_rate"],
            "complaint_rate": result["complaint_rate"],
        })

    total = len(outcomes)
    return {
        "windows": total,
        "counts": counts,
        "hold_rate": counts.get("HOLD", 0) / total if total else 0.0,
        "amber_rate": counts.get("AMBER", 0) / total if total else 0.0,
        "outcomes": outcomes,
        "production_mutation_authorized": False,
        "purpose": "historical_policy_replay_only",
    }
