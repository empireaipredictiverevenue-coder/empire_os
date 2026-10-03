"""Recipient-MX pacing and circuit-breaker policy."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class MxPacingPolicy:
    default_cap: int = 20
    min_cap: int = 1
    max_cap: int = 40
    transient_backoff_factor: float = 0.50
    healthy_growth_factor: float = 1.10
    max_deferral_rate: float = 0.05


def evaluate_mx_pool(
    context: Mapping[str, Any],
    *,
    policy: MxPacingPolicy | None = None,
) -> dict[str, Any]:
    policy = policy or MxPacingPolicy()
    current_cap = max(policy.min_cap, int(context.get("daily_cap") or policy.default_cap))
    deferral_rate = max(0.0, float(context.get("deferral_rate") or 0.0))
    auth_failures = int(context.get("auth_failures") or 0)
    complaints = int(context.get("complaints") or 0)
    consecutive_green_windows = int(context.get("consecutive_green_windows") or 0)

    if auth_failures:
        return {
            "state": "HOLD",
            "daily_cap": 0,
            "reason": "destination_auth_failures",
        }

    if complaints:
        return {
            "state": "HOLD",
            "daily_cap": 0,
            "reason": "destination_complaints_present",
        }

    if deferral_rate > policy.max_deferral_rate:
        return {
            "state": "BACKOFF",
            "daily_cap": max(
                policy.min_cap,
                int(current_cap * policy.transient_backoff_factor),
            ),
            "reason": "destination_deferral_rate_high",
        }

    if consecutive_green_windows >= 3:
        return {
            "state": "GREEN",
            "daily_cap": min(
                policy.max_cap,
                max(current_cap + 1, int(current_cap * policy.healthy_growth_factor)),
            ),
            "reason": "stable_destination_health",
        }

    return {
        "state": "MAINTAIN",
        "daily_cap": min(current_cap, policy.max_cap),
        "reason": "insufficient_green_history",
    }
