"""Founder-facing deliverability alert derivation."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


def build_founder_alert(snapshot: Mapping[str, Any]) -> dict[str, Any] | None:
    posture = str(snapshot.get("posture") or snapshot.get("overall_health") or "UNKNOWN")
    hard_holds = list(snapshot.get("hard_holds") or [])
    tasks = list(snapshot.get("tasks") or [])

    if posture in {"READY", "GREEN"} and not hard_holds:
        return None

    if posture in {"HOLD", "RED"} or hard_holds:
        severity = "CRITICAL"
    elif posture in {"REMEDIATE", "AMBER"}:
        severity = "HIGH"
    else:
        severity = "NOTICE"

    body = {
        "severity": severity,
        "posture": posture,
        "hard_holds": hard_holds,
        "tasks": tasks,
    }
    fingerprint = hashlib.sha256(
        json.dumps(body, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:20]

    return {
        **body,
        "fingerprint": fingerprint,
        "notification_policy": "dedupe_by_fingerprint",
        "mutation_authorized": False,
    }
