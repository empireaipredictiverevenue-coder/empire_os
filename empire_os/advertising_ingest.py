"""Governed Phase 9 advertising observation ingestion."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from empire_os.advertising_brain import (
    AdPerformanceObservation,
    normalise_ad_observation,
)


@dataclass(frozen=True)
class CanonicalAdObservation:
    canonical_campaign_id: str
    provider_observation_id: str
    observation: AdPerformanceObservation
    evidence: Mapping[str, Any]

    def validate(self) -> None:
        if not str(self.canonical_campaign_id or "").strip():
            raise ValueError("canonical_campaign_id required")
        if not str(self.provider_observation_id or "").strip():
            raise ValueError("provider_observation_id required")
        if not isinstance(self.evidence, Mapping):
            raise ValueError("evidence must be an object")


def build_canonical_ad_observation(
    *,
    canonical_campaign_id: str,
    provider_observation_id: str,
    row: Mapping[str, Any],
    evidence: Mapping[str, Any] | None = None,
) -> CanonicalAdObservation:
    observation = normalise_ad_observation(row)
    item = CanonicalAdObservation(
        canonical_campaign_id=str(canonical_campaign_id).strip(),
        provider_observation_id=str(provider_observation_id).strip(),
        observation=observation,
        evidence=dict(evidence or {}),
    )
    item.validate()
    return item
