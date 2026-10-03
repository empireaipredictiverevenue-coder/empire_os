"""Seed-only transport failover drill planner and evaluator."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from empire_os.outbound_transport_benchmark import compare_seed_transports


def plan_failover_drill(
    transports: Iterable[Mapping[str, Any]],
    seed_recipients: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    eligible = [
        dict(row)
        for row in transports
        if row.get("enabled") is True
        and row.get("provider_policy_compatible") is True
        and row.get("auth_ready") is True
    ]
    seeds = [
        dict(row)
        for row in seed_recipients
        if row.get("recipient_class") == "empire_seed"
    ]

    if len(eligible) < 2:
        return {
            "posture": "HOLD",
            "reason": "need_two_policy_compatible_transports",
            "assignments": [],
            "mutation_authorized": False,
        }
    if not seeds:
        return {
            "posture": "HOLD",
            "reason": "no_empire_seed_recipients",
            "assignments": [],
            "mutation_authorized": False,
        }

    assignments = []
    for transport in eligible:
        for seed in seeds:
            assignments.append({
                "transport": transport["transport"],
                "recipient": seed.get("recipient_key"),
                "recipient_class": "empire_seed",
                "purpose": "failover_drill",
            })

    return {
        "posture": "READY_FOR_CONTROLLED_TEST",
        "reason": "seed_only_failover_drill",
        "assignments": assignments,
        "mutation_authorized": False,
    }


def evaluate_failover_drill(results: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    benchmark = compare_seed_transports(results)
    return {
        **benchmark,
        "decision": "EVIDENCE_ONLY",
        "automatic_transport_switch": False,
    }
