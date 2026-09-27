"""Governed Phase 13 Revenue Exchange observation ingestion."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from empire_os.revenue_exchange import (
    ExchangeSnapshot,
    normalise_exchange_snapshot,
)


@dataclass(frozen=True)
class CanonicalExchangeObservation:
    observation_key: str
    snapshot: ExchangeSnapshot
    evidence: Mapping[str, Any]

    def validate(self) -> None:
        if not str(self.observation_key or "").strip():
            raise ValueError("observation_key required")
        if not isinstance(self.evidence, Mapping):
            raise ValueError("evidence must be an object")


def build_exchange_observation(
    *,
    observation_key: str,
    row: Mapping[str, Any],
    evidence: Mapping[str, Any] | None = None,
) -> CanonicalExchangeObservation:
    snapshot = normalise_exchange_snapshot(row)
    item = CanonicalExchangeObservation(
        observation_key=str(observation_key).strip(),
        snapshot=snapshot,
        evidence=dict(evidence or {}),
    )
    item.validate()
    return item
