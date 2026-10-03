"""Ringleader: supervisory decision layer for Empire outbound deliverability."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from empire_os.outbound_domain_sovereignty import evaluate_domain_sovereignty


@dataclass(frozen=True)
class RingleaderPolicy:
    require_inbox_placement_evidence_before_scale: bool = True


_PRIORITY = {
    "STOP_SEND": 100,
    "MIGRATE_TRANSPORT": 95,
    "REPAIR_AUTH": 90,
    "REMEDIATE_DOMAIN_CONTROL": 85,
    "VERIFY_RECIPIENTS": 80,
    "MEASURE_PLACEMENT": 70,
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
    elif any(task["action"] in {"VERIFY_RECIPIENTS", "MEASURE_PLACEMENT", "THROTTLE"} for task in tasks):
        posture = "LIMITED"
    else:
        posture = "READY"

    return {
        "posture": posture,
        "hard_holds": hard_holds,
        "tasks": tasks,
        "domain_sovereignty": sovereignty,
        "mutation_authorized": False,
    }
