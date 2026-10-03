"""Reputation model for outbound content families and message strategies.

A content family is an explicit stable template/angle identifier, not a fingerprint of
personalised recipient text. This lets Empire learn from placement, complaints, opt-outs
and commercial outcomes without treating individual message bodies as reusable identity.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping


def evaluate_content_family_reputation(
    family_key: str,
    events: Iterable[Mapping[str, Any]],
    *,
    minimum_send_sample: int = 20,
    minimum_seed_sample: int = 5,
) -> dict[str, Any]:
    key = str(family_key or "").strip()
    if not key:
        raise ValueError("family_key_required")

    rows = [dict(row) for row in events]
    counts: Counter[str] = Counter()
    sent = 0
    seed_tests = 0
    revenue = 0.0

    for row in rows:
        if str(row.get("family_key") or "").strip() != key:
            continue
        kind = str(row.get("kind") or "").strip().lower()
        if not kind:
            continue

        counts[kind] += max(1, int(row.get("count") or 1))
        if kind == "sent":
            sent += max(1, int(row.get("count") or 1))
        elif kind == "seed_test":
            seed_tests += max(1, int(row.get("count") or 1))
        elif kind == "revenue":
            revenue += max(0.0, float(row.get("amount") or 0.0))

    explicit_sent = max(
        [
            max(0, int(row.get("sent_total") or 0))
            for row in rows
            if str(row.get("family_key") or "").strip() == key
        ]
        or [0]
    )
    explicit_seed = max(
        [
            max(0, int(row.get("seed_tests_total") or 0))
            for row in rows
            if str(row.get("family_key") or "").strip() == key
        ]
        or [0]
    )
    sent = max(sent, explicit_sent)
    seed_tests = max(seed_tests, explicit_seed)

    complaints = counts["complaint"]
    opt_outs = counts["opt_out"]
    spam_placements = counts["spam_placement"]
    positive_replies = counts["positive_reply"]
    meetings = counts["meeting_booked"]

    complaint_rate = complaints / sent if sent else 0.0
    opt_out_rate = opt_outs / sent if sent else 0.0
    spam_placement_rate = (
        spam_placements / seed_tests
        if seed_tests
        else 0.0
    )

    blockers: list[str] = []
    warnings: list[str] = []

    if complaints:
        blockers.append("content_family_complaint_present")

    if (
        seed_tests >= minimum_seed_sample
        and spam_placement_rate >= 0.20
    ):
        blockers.append("content_family_seed_spam_rate_high")
    elif (
        seed_tests >= minimum_seed_sample
        and spam_placement_rate >= 0.10
    ):
        warnings.append("content_family_seed_spam_rate_elevated")

    if (
        sent >= minimum_send_sample
        and opt_out_rate >= 0.10
    ):
        warnings.append("content_family_opt_out_rate_high")

    if blockers:
        posture = "QUARANTINE"
    elif (
        sent < minimum_send_sample
        and seed_tests < minimum_seed_sample
    ):
        posture = "LEARNING"
    elif warnings:
        posture = "DEGRADED"
    else:
        posture = "HEALTHY"

    commercial_score = (
        positive_replies * 3.0
        + meetings * 6.0
        + revenue / 1000.0
    )

    return {
        "family_key": key,
        "posture": posture,
        "sent": sent,
        "seed_tests": seed_tests,
        "complaints": complaints,
        "opt_outs": opt_outs,
        "spam_placements": spam_placements,
        "positive_replies": positive_replies,
        "meetings": meetings,
        "revenue": revenue,
        "commercial_score": round(commercial_score, 4),
        "complaint_rate": round(complaint_rate, 6),
        "opt_out_rate": round(opt_out_rate, 6),
        "spam_placement_rate": round(spam_placement_rate, 6),
        "blockers": blockers,
        "warnings": warnings,
        "mutation_authorized": False,
        "send_authorized": False,
    }
