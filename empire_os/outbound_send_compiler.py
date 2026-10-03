"""Compile an approved outbound batch into a bounded, auditable execution plan.

The compiler cannot authorize a lead. It only schedules opportunities that are already
approved, verified, unsuppressed, and compatible with healthy sender/MX pools.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

from empire_os.outbound_reputation_budget import allocate_reputation_budget


def compile_send_plan(
    opportunities: Iterable[Mapping[str, Any]],
    senders: Iterable[Mapping[str, Any]],
    mx_limits: Mapping[str, int],
    *,
    total_capacity: int,
    canary_size: int,
) -> dict[str, Any]:
    if total_capacity < 0 or canary_size < 0:
        raise ValueError("capacity_must_be_nonnegative")

    sender_rows = [dict(row) for row in senders]
    healthy = [
        row
        for row in sender_rows
        if row.get("health") == "GREEN"
        and row.get("enabled") is True
        and int(row.get("remaining_capacity") or 0) > 0
    ]

    if not healthy or total_capacity == 0:
        return {
            "posture": "HOLD",
            "reason": "no_healthy_sender_capacity",
            "canary": [],
            "remainder": [],
            "unallocated": [],
        }

    budget = allocate_reputation_budget(
        opportunities,
        capacity=total_capacity,
    )
    selected_ids = {row["opportunity_id"] for row in budget["selected"]}
    source = {
        str(row.get("opportunity_id") or ""): dict(row)
        for row in opportunities
        if str(row.get("opportunity_id") or "") in selected_ids
    }

    sender_capacity = {
        str(row.get("sender_id") or ""): int(row.get("remaining_capacity") or 0)
        for row in healthy
    }
    sender_domain = {
        str(row.get("sender_id") or ""): str(row.get("domain") or "")
        for row in healthy
    }
    mx_used: dict[str, int] = defaultdict(int)

    assignments: list[dict[str, Any]] = []
    unallocated: list[dict[str, str]] = []

    ordered = [row["opportunity_id"] for row in budget["selected"]]
    for opportunity_id in ordered:
        item = source[opportunity_id]
        mx = str(item.get("recipient_mx") or "unknown")
        mx_cap = max(0, int(mx_limits.get(mx, 0)))
        if mx_used[mx] >= mx_cap:
            unallocated.append({
                "opportunity_id": opportunity_id,
                "reason": "recipient_mx_capacity_exhausted",
            })
            continue

        candidates = [
            sender_id
            for sender_id, capacity in sender_capacity.items()
            if capacity > 0
        ]
        if not candidates:
            unallocated.append({
                "opportunity_id": opportunity_id,
                "reason": "sender_capacity_exhausted",
            })
            continue

        # Least-used remaining-capacity allocation; deterministic tie-break.
        sender_id = sorted(
            candidates,
            key=lambda candidate: (
                -sender_capacity[candidate],
                candidate,
            ),
        )[0]

        assignments.append({
            "opportunity_id": opportunity_id,
            "sender_id": sender_id,
            "sender_domain": sender_domain[sender_id],
            "recipient_mx": mx,
        })
        sender_capacity[sender_id] -= 1
        mx_used[mx] += 1

    actual_canary_size = min(canary_size, len(assignments))
    canary = assignments[:actual_canary_size]
    remainder = assignments[actual_canary_size:]

    return {
        "posture": "CANARY_REQUIRED" if canary else "HOLD",
        "reason": "bounded_compilation_complete" if canary else "no_assignments",
        "canary": canary,
        "remainder": remainder,
        "unallocated": unallocated + budget["deferred"] + budget["held"],
        "sender_capacity_remaining": sender_capacity,
        "mx_usage": dict(mx_used),
        "mutation_authorized": False,
        "policy": "compile_only_outbound_governor_retains_send_authority",
    }
