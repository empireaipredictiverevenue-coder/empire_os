"""Canary cohort evaluation before a larger approved batch is released."""
from __future__ import annotations

from typing import Any, Mapping


def evaluate_canary(result: Mapping[str, Any]) -> dict[str, Any]:
    sent = max(0, int(result.get("sent") or 0))
    if sent == 0:
        return {"decision": "HOLD", "reason": "no_canary_evidence"}

    hard_bounces = max(0, int(result.get("hard_bounces") or 0))
    complaints = max(0, int(result.get("complaints") or 0))
    deferrals = max(0, int(result.get("deferrals") or 0))
    inbox = result.get("inbox_placement_rate")

    hard_bounce_rate = hard_bounces / sent
    deferral_rate = deferrals / sent

    if complaints:
        return {"decision": "HOLD", "reason": "canary_complaint"}
    if hard_bounce_rate > 0.02:
        return {"decision": "HOLD", "reason": "canary_hard_bounce_rate"}
    if deferral_rate > 0.10:
        return {"decision": "THROTTLE", "reason": "canary_deferral_rate"}
    if inbox is not None and float(inbox) < 0.90:
        return {"decision": "HOLD", "reason": "canary_inbox_placement_low"}

    return {"decision": "EXPAND_BOUNDED", "reason": "canary_green"}
