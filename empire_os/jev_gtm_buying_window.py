"""Evidence-only buying-window timeline for Empire GTM JEV.

Correlated reports are one evidentiary group. Momentum is neither an
estimated purchase probability nor permission to contact an entity.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping


def assess_buying_window(signal_review: Mapping[str, Any], *, recent_days: int = 30) -> dict[str, Any]:
    """Summarize dated, already-validated first-party signals without re-scoring ICP."""
    if not 1 <= recent_days <= 90:
        raise ValueError("bounded recent window required")
    fresh = signal_review.get("fresh")
    if not isinstance(fresh, list):
        raise ValueError("validated signal review required")
    if signal_review.get("execution_authority") != "none":
        raise ValueError("signal review must have no authority")
    # Edge between identical source IDs OR overlapping evidence refs.
    recent = [s for s in fresh if isinstance(s, Mapping)
              and isinstance(s.get("age_days"), (int, float))
              and 0 <= s["age_days"] <= recent_days
              and isinstance(s.get("evidence_refs"), list)]
    parent = list(range(len(recent)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        parent[find(a)] = find(b)

    for i, a in enumerate(recent):
        for j in range(i):
            b = recent[j]
            if (a.get("source_id") == b.get("source_id")
                    or set(a["evidence_refs"]) & set(b["evidence_refs"])):
                union(i, j)
    groups: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for i, s in enumerate(recent):
        groups[find(i)].append(s)
    classes = sorted({str(s.get("signal_type") or "") for s in recent})
    independence = len(groups)
    contradiction = signal_review.get("has_contradiction") is True
    if contradiction:
        status = "CONTRADICTORY_REVIEW"
    elif independence >= 2 and len(classes) >= 2:
        status = "MULTI_SIGNAL_WINDOW_OBSERVED"
    elif recent:
        status = "SINGLE_SOURCE_OR_SIGNAL_WATCH"
    else:
        status = "NO_RECENT_SIGNAL"
    return {
        "schema_version": "empire.jev.gtm_buying_window.v1",
        "status": status,
        "signal_count": len(recent),
        "independent_evidence_group_count": independence,
        "distinct_signal_type_count": len(classes),
        "signal_types": classes,
        "recent_days": recent_days,
        "evidence_independence_proven": False,  # shared refs & source IDs are only a conservative filter
        "buyer_purchase_intent_verified": False,
        "purchase_probability": None,
        "contact_permission_granted": False,
        "execution_authority": "none",
    }
