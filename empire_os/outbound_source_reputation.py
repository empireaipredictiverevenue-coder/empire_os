"""Reputation model for prospect acquisition sources.

Empire treats data-source quality as part of deliverability. Scrapers, scouts, datasets,
referrals and enrichment sources earn or lose trust from verified downstream outcomes.
The score never authorizes sending; it can only increase verification or quarantine a
source for outbound use.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping


_NEGATIVE_WEIGHTS = {
    "hard_bounce": -8.0,
    "invalid_recipient": -8.0,
    "complaint": -25.0,
    "opt_out": -5.0,
    "negative_reply": -2.0,
    "soft_bounce": -1.0,
}

_POSITIVE_WEIGHTS = {
    "positive_reply": 3.0,
    "meeting_booked": 6.0,
    "proposal_requested": 8.0,
    "commercial_terms": 12.0,
    "revenue": 15.0,
}


def evaluate_source_reputation(
    source_key: str,
    events: Iterable[Mapping[str, Any]],
    *,
    minimum_sample: int = 10,
) -> dict[str, Any]:
    key = str(source_key or "").strip()
    if not key:
        raise ValueError("source_key_required")

    rows = [dict(row) for row in events]

    counts: Counter[str] = Counter()
    sent = 0
    score = 0.0
    revenue = 0.0

    for row in rows:
        if str(row.get("source_key") or "").strip() != key:
            continue

        kind = str(row.get("kind") or "").strip().lower()
        if not kind:
            continue

        counts[kind] += 1
        if kind == "sent":
            sent += max(1, int(row.get("count") or 1))
        elif kind in _NEGATIVE_WEIGHTS:
            score += _NEGATIVE_WEIGHTS[kind]
        elif kind in _POSITIVE_WEIGHTS:
            score += _POSITIVE_WEIGHTS[kind]
            if kind == "revenue":
                revenue += max(0.0, float(row.get("amount") or 0.0))

    # Some event feeds only emit outcomes; allow explicit sent totals to be carried
    # on any event without double-counting unless the event itself is "sent".
    explicit_sent = max(
        [
            max(0, int(dict(row).get("sent_total") or 0))
            for row in rows
            if str(row.get("source_key") or "").strip() == key
        ]
        or [0]
    )
    sent = max(sent, explicit_sent)

    hard_bounces = counts["hard_bounce"] + counts["invalid_recipient"]
    complaints = counts["complaint"]
    opt_outs = counts["opt_out"]

    hard_bounce_rate = hard_bounces / sent if sent else 0.0
    complaint_rate = complaints / sent if sent else 0.0
    opt_out_rate = opt_outs / sent if sent else 0.0

    blockers: list[str] = []
    warnings: list[str] = []

    if complaints:
        blockers.append("source_complaint_present")
    if sent >= minimum_sample and hard_bounce_rate >= 0.05:
        blockers.append("source_hard_bounce_rate_high")
    elif sent >= minimum_sample and hard_bounce_rate >= 0.02:
        warnings.append("source_hard_bounce_rate_elevated")

    if sent >= minimum_sample and opt_out_rate >= 0.10:
        warnings.append("source_opt_out_rate_high")

    if blockers:
        posture = "QUARANTINE"
    elif sent < minimum_sample:
        posture = "LEARNING"
    elif warnings:
        posture = "DEGRADED"
    else:
        posture = "HEALTHY"

    return {
        "source_key": key,
        "posture": posture,
        "score": round(score, 4),
        "sent": sent,
        "hard_bounces": hard_bounces,
        "complaints": complaints,
        "opt_outs": opt_outs,
        "hard_bounce_rate": round(hard_bounce_rate, 6),
        "complaint_rate": round(complaint_rate, 6),
        "opt_out_rate": round(opt_out_rate, 6),
        "revenue": revenue,
        "blockers": blockers,
        "warnings": warnings,
        "minimum_sample": minimum_sample,
        "mutation_authorized": False,
        "send_authorized": False,
    }
