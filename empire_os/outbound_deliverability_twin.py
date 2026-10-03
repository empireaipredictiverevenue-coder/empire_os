"""Bounded pre-send deliverability simulation for Empire Ringleader.

This is a risk model, not a promise of inbox placement. It estimates whether a planned
batch materially increases reputation risk before any message is released.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Any, Mapping


@dataclass(frozen=True)
class TwinPolicy:
    max_batch_risk: float = 0.35
    canary_fraction: float = 0.10
    min_canary: int = 3
    max_canary: int = 10


def simulate_batch(
    current: Mapping[str, Any],
    planned: Mapping[str, Any],
    *,
    policy: TwinPolicy | None = None,
) -> dict[str, Any]:
    policy = policy or TwinPolicy()

    sent_7d = max(1, int(current.get("sent_7d") or 1))
    planned_count = max(0, int(planned.get("count") or 0))
    bounce_rate = max(0.0, float(current.get("bounce_rate") or 0.0))
    complaint_rate = max(0.0, float(current.get("complaint_rate") or 0.0))
    deferral_rate = max(0.0, float(current.get("deferral_rate") or 0.0))
    placement_rate = current.get("placement_rate")
    auth_ready = current.get("auth_ready") is True
    recipient_verified_fraction = max(
        0.0, min(1.0, float(planned.get("recipient_verified_fraction") or 0.0))
    )

    volume_ratio = planned_count / sent_7d
    volume_risk = min(1.0, volume_ratio / 0.50)
    bounce_risk = min(1.0, bounce_rate / 0.03)
    complaint_risk = min(1.0, complaint_rate / 0.001)
    deferral_risk = min(1.0, deferral_rate / 0.05)
    verification_risk = 1.0 - recipient_verified_fraction
    auth_risk = 0.0 if auth_ready else 1.0

    placement_risk = 0.25
    if placement_rate is not None:
        placement_risk = max(0.0, min(1.0, (0.95 - float(placement_rate)) / 0.20))

    risk = (
        0.22 * volume_risk
        + 0.22 * bounce_risk
        + 0.12 * complaint_risk
        + 0.12 * deferral_risk
        + 0.12 * verification_risk
        + 0.10 * auth_risk
        + 0.10 * placement_risk
    )

    if planned_count == 0:
        posture = "NOOP"
    elif risk > policy.max_batch_risk:
        posture = "HOLD"
    elif risk > policy.max_batch_risk * 0.60:
        posture = "CANARY_ONLY"
    else:
        posture = "ALLOW_BOUNDED"

    canary_size = 0
    if planned_count:
        canary_size = min(
            policy.max_canary,
            max(policy.min_canary, ceil(planned_count * policy.canary_fraction)),
            planned_count,
        )

    return {
        "posture": posture,
        "risk": round(risk, 4),
        "planned_count": planned_count,
        "canary_size": canary_size,
        "components": {
            "volume": round(volume_risk, 4),
            "bounce": round(bounce_risk, 4),
            "complaint": round(complaint_risk, 4),
            "deferral": round(deferral_risk, 4),
            "verification": round(verification_risk, 4),
            "authentication": round(auth_risk, 4),
            "placement": round(placement_risk, 4),
        },
        "prediction_claim": "bounded_risk_simulation_not_inbox_guarantee",
    }
