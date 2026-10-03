"""Bounded change-point and root-cause evidence ranking for deliverability drift."""
from __future__ import annotations

from typing import Any, Iterable, Mapping


def detect_metric_shift(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    min_relative_change: float = 0.25,
) -> dict[str, Any]:
    shifts: list[dict[str, Any]] = []

    for key in (
        "delivery_rate",
        "bounce_rate",
        "complaint_rate",
        "deferral_rate",
        "inbox_placement_rate",
    ):
        if key not in before or key not in after:
            continue
        try:
            old = float(before[key])
            new = float(after[key])
        except (TypeError, ValueError):
            continue

        denominator = max(abs(old), 0.0001)
        relative = (new - old) / denominator
        if abs(relative) >= min_relative_change:
            shifts.append({
                "metric": key,
                "before": old,
                "after": new,
                "relative_change": round(relative, 4),
            })

    return {
        "shift_detected": bool(shifts),
        "shifts": shifts,
    }


def rank_candidate_causes(
    changes: Iterable[Mapping[str, Any]],
    metric_shift: Mapping[str, Any],
) -> dict[str, Any]:
    """Rank evidence-backed correlations; never claim causation from timing alone."""

    shifted = {row["metric"] for row in metric_shift.get("shifts", []) if "metric" in row}
    ranked: list[dict[str, Any]] = []

    for raw in changes:
        row = dict(raw)
        kind = str(row.get("kind") or "")
        evidence_strength = max(0.0, min(1.0, float(row.get("evidence_strength") or 0.0)))
        temporal_proximity = max(0.0, min(1.0, float(row.get("temporal_proximity") or 0.0)))
        affected_metrics = set(row.get("affected_metrics") or [])
        overlap = len(shifted.intersection(affected_metrics))
        overlap_score = min(1.0, overlap / max(1, len(shifted)))

        score = 0.45 * evidence_strength + 0.30 * temporal_proximity + 0.25 * overlap_score
        ranked.append({
            "kind": kind,
            "change_id": str(row.get("change_id") or ""),
            "score": round(score, 4),
            "evidence_strength": evidence_strength,
            "temporal_proximity": temporal_proximity,
            "metric_overlap": overlap_score,
            "claim": "candidate_cause_not_proven_causation",
        })

    ranked.sort(key=lambda item: (-item["score"], item["kind"], item["change_id"]))
    return {"candidates": ranked}
