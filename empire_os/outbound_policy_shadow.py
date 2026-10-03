"""Shadow-policy evaluation for Ringleader changes.

Candidate policy logic is observed against historical/current contexts without gaining
send authority. This allows safe promotion decisions based on disagreement evidence.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping


Evaluator = Callable[[Mapping[str, Any]], Mapping[str, Any]]


def compare_policies(
    contexts: Iterable[Mapping[str, Any]],
    *,
    current: Evaluator,
    candidate: Evaluator,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    disagreements = 0
    stricter = 0
    looser = 0

    rank = {
        "READY": 0,
        "LIMITED": 1,
        "REMEDIATE": 2,
        "HOLD": 3,
    }

    for index, raw in enumerate(contexts):
        context = dict(raw)
        existing = dict(current(context))
        proposed = dict(candidate(context))
        current_posture = str(existing.get("posture") or "READY")
        candidate_posture = str(proposed.get("posture") or "READY")

        disagree = current_posture != candidate_posture
        if disagree:
            disagreements += 1
            current_rank = rank.get(current_posture, 99)
            candidate_rank = rank.get(candidate_posture, 99)
            if candidate_rank > current_rank:
                stricter += 1
            elif candidate_rank < current_rank:
                looser += 1

        rows.append({
            "index": index,
            "current_posture": current_posture,
            "candidate_posture": candidate_posture,
            "disagreement": disagree,
            "candidate_mutation_authorized": proposed.get("mutation_authorized"),
        })

    total = len(rows)
    return {
        "samples": total,
        "disagreements": disagreements,
        "disagreement_rate": disagreements / total if total else 0.0,
        "candidate_stricter": stricter,
        "candidate_looser": looser,
        "rows": rows,
        "promotion_authorized": False,
        "mode": "SHADOW",
    }
