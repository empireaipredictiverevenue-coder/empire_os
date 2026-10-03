"""Empire sender warm-up and pool state machine.

Warm-up builds legitimate reputation gradually. It does not create synthetic opens,
fake replies, or coordinated engagement.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class WarmupState(str, Enum):
    NEW = "NEW"
    VERIFYING = "VERIFYING"
    RAMPING = "RAMPING"
    ACTIVE = "ACTIVE"
    THROTTLED = "THROTTLED"
    QUARANTINED = "QUARANTINED"
    RECOVERY = "RECOVERY"
    RETIRED = "RETIRED"


@dataclass(frozen=True)
class WarmupPolicy:
    initial_daily_cap: int = 5
    max_daily_cap: int = 40
    green_growth_factor: float = 1.25
    recovery_growth_factor: float = 1.10
    max_bounce_rate: float = 0.02
    max_complaint_rate: float = 0.0005


def next_warmup_state(
    context: Mapping[str, Any],
    *,
    policy: WarmupPolicy | None = None,
) -> dict[str, Any]:
    policy = policy or WarmupPolicy()
    current = WarmupState(str(context.get("state") or WarmupState.NEW))
    dns_ready = context.get("dns_ready") is True
    placement_ready = context.get("placement_measured") is True
    provider_policy_ok = context.get("provider_policy_permits_use_case") is True
    real_traffic_only = context.get("real_traffic_only") is True

    bounce_rate = float(context.get("bounce_rate") or 0)
    complaint_rate = float(context.get("complaint_rate") or 0)
    deferrals = int(context.get("deferrals") or 0)
    hard_bounces = int(context.get("hard_bounces") or 0)
    current_cap = int(context.get("daily_cap") or policy.initial_daily_cap)

    holds: list[str] = []
    if not provider_policy_ok:
        holds.append("provider_policy_not_verified")
    if not real_traffic_only:
        holds.append("synthetic_warmup_not_allowed")
    if hard_bounces > 0 and bounce_rate > policy.max_bounce_rate:
        holds.append("bounce_health_bad")
    if complaint_rate > policy.max_complaint_rate:
        holds.append("complaint_health_bad")

    if holds:
        return {
            "state": WarmupState.QUARANTINED.value,
            "daily_cap": 0,
            "holds": holds,
            "action": "STOP_SEND",
        }

    if current == WarmupState.NEW:
        return {
            "state": WarmupState.VERIFYING.value,
            "daily_cap": 0,
            "holds": [],
            "action": "VERIFY_AUTH_AND_POLICY",
        }

    if current == WarmupState.VERIFYING:
        if not dns_ready:
            return {
                "state": current.value,
                "daily_cap": 0,
                "holds": ["dns_not_ready"],
                "action": "WAIT",
            }
        return {
            "state": WarmupState.RAMPING.value,
            "daily_cap": policy.initial_daily_cap,
            "holds": [],
            "action": "START_LOW_VOLUME",
        }

    if deferrals > 0:
        return {
            "state": WarmupState.THROTTLED.value,
            "daily_cap": max(1, current_cap // 2),
            "holds": [],
            "action": "BACK_OFF",
        }

    if current in {WarmupState.RAMPING, WarmupState.RECOVERY, WarmupState.THROTTLED}:
        factor = (
            policy.recovery_growth_factor
            if current in {WarmupState.RECOVERY, WarmupState.THROTTLED}
            else policy.green_growth_factor
        )
        next_cap = min(policy.max_daily_cap, max(current_cap + 1, int(current_cap * factor)))
        next_state = WarmupState.ACTIVE if placement_ready and next_cap >= policy.max_daily_cap else WarmupState.RAMPING
        return {
            "state": next_state.value,
            "daily_cap": next_cap,
            "holds": [],
            "action": "INCREASE_GRADUALLY",
        }

    return {
        "state": current.value,
        "daily_cap": min(current_cap, policy.max_daily_cap),
        "holds": [],
        "action": "MAINTAIN",
    }


def classify_pool(context: Mapping[str, Any]) -> dict[str, str]:
    """Declare a stable pool purpose. Pools are for isolation, not identity churn."""

    kind = str(context.get("kind") or "").upper()
    purpose = str(context.get("purpose") or "").lower()

    valid = {"DOMAIN", "MAILBOX", "TRANSPORT", "RECIPIENT_MX", "SEED_PLACEMENT"}
    if kind not in valid:
        raise ValueError("unsupported_pool_kind")

    if kind == "DOMAIN" and purpose in {"transactional", "relationship", "prospecting"}:
        isolation = "reputation_and_traffic_class"
    elif kind == "MAILBOX":
        isolation = "sender_capacity_and_identity"
    elif kind == "TRANSPORT":
        isolation = "provider_or_ip_reputation"
    elif kind == "RECIPIENT_MX":
        isolation = "destination_rate_control"
    else:
        isolation = "measurement_only"

    return {"kind": kind, "purpose": purpose, "isolation": isolation}
