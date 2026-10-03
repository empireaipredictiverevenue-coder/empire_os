"""Provider policy compatibility registry.

Provider rules change independently of Empire. Ringleader consumes dated policy evidence
and refuses to treat an unknown or incompatible transport as production-ready.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable


@dataclass(frozen=True)
class ProviderPolicySnapshot:
    provider: str
    effective_date: date
    reviewed_date: date
    allowed_traffic_classes: frozenset[str]
    source_url: str
    source_hash: str = ""


def evaluate_provider_policy(
    snapshots: Iterable[ProviderPolicySnapshot],
    *,
    provider: str,
    traffic_class: str,
    as_of: date,
) -> dict[str, object]:
    candidates = [
        snapshot
        for snapshot in snapshots
        if snapshot.provider == provider and snapshot.effective_date <= as_of
    ]
    if not candidates:
        return {
            "status": "UNKNOWN",
            "provider": provider,
            "traffic_class": traffic_class,
            "permitted": None,
            "reason": "no_current_policy_snapshot",
        }

    current = max(candidates, key=lambda snapshot: snapshot.effective_date)
    permitted = traffic_class in current.allowed_traffic_classes
    return {
        "status": "PERMITTED" if permitted else "PROHIBITED",
        "provider": provider,
        "traffic_class": traffic_class,
        "permitted": permitted,
        "effective_date": current.effective_date.isoformat(),
        "reviewed_date": current.reviewed_date.isoformat(),
        "source_url": current.source_url,
        "source_hash": current.source_hash,
    }
