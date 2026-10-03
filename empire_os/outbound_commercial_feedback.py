"""Commercial-outcome feedback that avoids treating opens as success."""
from __future__ import annotations

from typing import Any, Iterable, Mapping


_WEIGHTS = {
    "positive_reply": 3.0,
    "meeting_booked": 5.0,
    "proposal_requested": 7.0,
    "commercial_terms": 9.0,
    "revenue": 12.0,
    "neutral_reply": 0.5,
    "negative_reply": -2.0,
    "opt_out": -5.0,
    "hard_bounce": -6.0,
    "complaint": -12.0,
}


def commercial_signal_score(events: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    total = 0.0
    counts: dict[str, int] = {}

    for event in events:
        kind = str(event.get("kind") or "")
        if kind not in _WEIGHTS:
            continue
        counts[kind] = counts.get(kind, 0) + 1
        total += _WEIGHTS[kind]

    if total > 10:
        signal = "STRONG_POSITIVE"
    elif total > 0:
        signal = "POSITIVE"
    elif total == 0:
        signal = "NEUTRAL"
    elif total > -10:
        signal = "NEGATIVE"
    else:
        signal = "STRONG_NEGATIVE"

    return {
        "score": total,
        "signal": signal,
        "counts": counts,
        "uses_open_tracking": False,
        "purpose": "targeting_and_offer_learning_not_send_authorization",
    }
