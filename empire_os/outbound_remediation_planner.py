"""Evidence-driven remediation planning for Ringleader.

Plans are advisory and fail closed. This module never mutates DNS, providers, mailboxes,
or outbound state.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping


_ACTIONS = {
    "authentication_changed": [
        ("FREEZE_DOMAIN_POOL", "domain_pool"),
        ("REVERIFY_AUTH", "auth_observer"),
        ("RUN_SEED_PLACEMENT", "placement_lab"),
    ],
    "recipient_source_changed": [
        ("FREEZE_RECIPIENT_SOURCE", "recipient_verifier"),
        ("REVERIFY_RECIPIENT_SAMPLE", "recipient_verifier"),
        ("RECALCULATE_BOUNCE_RISK", "deliverability_twin"),
    ],
    "transport_changed": [
        ("THROTTLE_TRANSPORT", "transport_adapter"),
        ("RUN_SEED_TRANSPORT_BENCHMARK", "placement_lab"),
        ("COMPARE_TRANSPORT_EVIDENCE", "ringleader"),
    ],
    "provider_policy_changed": [
        ("HOLD_PROVIDER_TRAFFIC", "outbound_governor"),
        ("REVIEW_PROVIDER_POLICY", "policy_observer"),
        ("BENCHMARK_COMPATIBLE_TRANSPORT", "placement_lab"),
    ],
    "volume_changed": [
        ("RESTORE_PREVIOUS_CAP", "pacing_controller"),
        ("OBSERVE_NEXT_HEALTH_WINDOW", "ringleader"),
    ],
    "content_profile_changed": [
        ("RUN_MESSAGE_PREFLIGHT", "message_preflight"),
        ("COMPARE_CANARY_PLACEMENT", "placement_lab"),
    ],
}


def plan_remediation(
    candidates: Iterable[Mapping[str, Any]],
    *,
    minimum_score: float = 0.55,
) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    considered: list[dict[str, Any]] = []

    for raw in candidates:
        row = dict(raw)
        kind = str(row.get("kind") or "")
        score = float(row.get("score") or 0.0)
        considered.append({"kind": kind, "score": score})
        if score < minimum_score:
            continue
        for action, owner in _ACTIONS.get(kind, []):
            tasks.append({
                "action": action,
                "owner": owner,
                "candidate_cause": kind,
                "evidence_score": score,
                "mutation_authorized": False,
            })

    if not tasks:
        tasks.append({
            "action": "COLLECT_MORE_EVIDENCE",
            "owner": "ringleader",
            "candidate_cause": "unresolved",
            "evidence_score": 0.0,
            "mutation_authorized": False,
        })

    return {
        "posture": "REMEDIATE" if tasks[0]["action"] != "COLLECT_MORE_EVIDENCE" else "OBSERVE",
        "tasks": tasks,
        "considered": considered,
        "mutation_authorized": False,
    }
