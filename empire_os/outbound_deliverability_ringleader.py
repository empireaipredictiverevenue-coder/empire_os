"""Ringleader: supervisory decision layer for Empire outbound deliverability."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from empire_os.outbound_domain_sovereignty import evaluate_domain_sovereignty
from empire_os.outbound_canary import evaluate_canary
from empire_os.outbound_deliverability_twin import simulate_batch
from empire_os.outbound_mx_pacing import evaluate_mx_pool
from empire_os.outbound_reputation_budget import allocate_reputation_budget


@dataclass(frozen=True)
class RingleaderPolicy:
    require_inbox_placement_evidence_before_scale: bool = True


_PRIORITY = {
    "STOP_SEND": 100,
    "MIGRATE_TRANSPORT": 95,
    "REPAIR_AUTH": 90,
    "REMEDIATE_DOMAIN_CONTROL": 85,
    "VERIFY_RECIPIENTS": 80,
    "RUN_CANARY": 75,
    "MEASURE_PLACEMENT": 70,
    "THROTTLE_MX": 65,
    "THROTTLE": 60,
    "OBSERVE": 10,
}


def _task(action: str, reason: str, owner: str) -> dict[str, Any]:
    return {
        "action": action,
        "reason": reason,
        "owner": owner,
        "priority": _PRIORITY[action],
    }


def evaluate_ringleader(
    context: Mapping[str, Any] | None,
    *,
    policy: RingleaderPolicy | None = None,
) -> dict[str, Any]:
    """Fuse deliverability, policy, placement and sovereignty into one send posture."""

    policy = policy or RingleaderPolicy()
    context = dict(context or {})
    tasks: list[dict[str, Any]] = []
    hard_holds: list[str] = []

    deliverability = dict(context.get("deliverability") or {})
    health = str(deliverability.get("health") or deliverability.get("overall_health") or "UNKNOWN")
    if health == "HOLD":
        hard_holds.append("deliverability_hold")
        tasks.append(_task("STOP_SEND", "deliverability_hold", "outbound_governor"))
    elif health in {"AMBER", "RED"}:
        tasks.append(_task("THROTTLE", f"deliverability_{health.lower()}", "pacing_controller"))

    provider_policy = context.get("provider_policy_permits_use_case")
    if provider_policy is False:
        hard_holds.append("provider_policy_mismatch")
        tasks.append(_task("MIGRATE_TRANSPORT", "provider_policy_mismatch", "transport_adapter"))
    elif provider_policy is not True:
        tasks.append(_task("OBSERVE", "provider_policy_unverified", "policy_observer"))

    auth = dict(context.get("authentication") or {})
    missing_auth = [
        key for key in ("spf_aligned", "dkim_aligned", "dmarc_valid", "tls_ready")
        if auth.get(key) is not True
    ]
    if missing_auth:
        tasks.append(_task("REPAIR_AUTH", ",".join(missing_auth), "auth_observer"))

    recipient_quality = dict(context.get("recipient_quality") or {})
    if recipient_quality.get("verified") is not True:
        tasks.append(_task("VERIFY_RECIPIENTS", "recipient_quality_unverified", "recipient_verifier"))

    placement = dict(context.get("placement") or {})
    if (
        policy.require_inbox_placement_evidence_before_scale
        and placement.get("measured") is not True
    ):
        tasks.append(_task("MEASURE_PLACEMENT", "inbox_placement_unknown", "placement_lab"))

    twin = None
    planned_batch = context.get("planned_batch")
    if isinstance(planned_batch, Mapping):
        twin_current = dict(context.get("twin_current") or {})
        twin = simulate_batch(twin_current, planned_batch)
        if twin["posture"] == "HOLD":
            hard_holds.append("pre_send_twin_hold")
            tasks.append(_task("STOP_SEND", "pre_send_twin_hold", "deliverability_twin"))
        elif twin["posture"] == "CANARY_ONLY":
            tasks.append(_task("RUN_CANARY", "pre_send_twin_requires_canary", "canary_controller"))

    mx_pacing = None
    mx_pool = context.get("mx_pool")
    if isinstance(mx_pool, Mapping):
        mx_pacing = evaluate_mx_pool(mx_pool)
        if mx_pacing["state"] == "HOLD":
            tasks.append(_task("THROTTLE_MX", mx_pacing["reason"], "mx_pacing_controller"))
        elif mx_pacing["state"] == "BACKOFF":
            tasks.append(_task("THROTTLE_MX", mx_pacing["reason"], "mx_pacing_controller"))

    canary = None
    canary_result = context.get("canary_result")
    if isinstance(canary_result, Mapping):
        canary = evaluate_canary(canary_result)
        if canary["decision"] == "HOLD":
            hard_holds.append("canary_hold")
            tasks.append(_task("STOP_SEND", canary["reason"], "canary_controller"))
        elif canary["decision"] == "THROTTLE":
            tasks.append(_task("THROTTLE", canary["reason"], "pacing_controller"))

    reputation_budget = None
    budget = context.get("reputation_budget")
    if isinstance(budget, Mapping):
        opportunities = budget.get("opportunities")
        capacity = budget.get("capacity")
        if isinstance(opportunities, list) and isinstance(capacity, int):
            reputation_budget = allocate_reputation_budget(
                opportunities,
                capacity=capacity,
            )

    sovereignty = evaluate_domain_sovereignty(context.get("domain_sovereignty"))
    if sovereignty["status"] in {"HOLD", "WEAK"}:
        tasks.append(
            _task(
                "REMEDIATE_DOMAIN_CONTROL",
                f"domain_sovereignty_{sovereignty['status'].lower()}",
                "domain_sovereignty",
            )
        )
        if sovereignty["status"] == "HOLD":
            hard_holds.append("domain_sovereignty_hold")

    # Deduplicate exact actions/reasons while keeping deterministic priority order.
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for task in tasks:
        unique[(task["action"], task["reason"])] = task
    tasks = sorted(
        unique.values(),
        key=lambda item: (-int(item["priority"]), str(item["action"]), str(item["reason"])),
    )

    if hard_holds:
        posture = "HOLD"
    elif any(task["action"] in {"REPAIR_AUTH", "REMEDIATE_DOMAIN_CONTROL"} for task in tasks):
        posture = "REMEDIATE"
    elif any(
        task["action"] in {
            "VERIFY_RECIPIENTS",
            "RUN_CANARY",
            "MEASURE_PLACEMENT",
            "THROTTLE_MX",
            "THROTTLE",
        }
        for task in tasks
    ):
        posture = "LIMITED"
    else:
        posture = "READY"

    return {
        "posture": posture,
        "hard_holds": hard_holds,
        "tasks": tasks,
        "domain_sovereignty": sovereignty,
        "deliverability_twin": twin,
        "mx_pacing": mx_pacing,
        "canary": canary,
        "reputation_budget": reputation_budget,
        "mutation_authorized": False,
    }
