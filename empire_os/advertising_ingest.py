"""Governed Phase 9 advertising observation ingestion."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from empire_os.advertising_brain import (
    AdPerformanceObservation,
    normalise_ad_observation,
)


def _payload_hash(
    observation: AdPerformanceObservation,
    evidence: Mapping[str, Any],
) -> str:
    payload = {
        "observation": observation.as_dict(),
        "evidence": dict(evidence),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class CanonicalAdObservation:
    canonical_campaign_id: str
    provider_observation_id: str
    observation: AdPerformanceObservation
    evidence: Mapping[str, Any]
    payload_sha256: str
    canonical_creative_id: str | None = None

    def validate(self) -> None:
        if not str(self.canonical_campaign_id or "").strip():
            raise ValueError("canonical_campaign_id required")
        if not str(self.provider_observation_id or "").strip():
            raise ValueError("provider_observation_id required")
        if not str(self.payload_sha256 or "").strip():
            raise ValueError("payload_sha256 required")
        if not isinstance(self.evidence, Mapping):
            raise ValueError("evidence must be an object")
        if self.canonical_creative_id is not None:
            if not str(self.canonical_creative_id).strip():
                raise ValueError("canonical_creative_id cannot be blank")


def build_canonical_ad_observation(
    *,
    canonical_campaign_id: str,
    provider_observation_id: str,
    row: Mapping[str, Any],
    evidence: Mapping[str, Any] | None = None,
    canonical_creative_id: str | None = None,
) -> CanonicalAdObservation:
    observation = normalise_ad_observation(row)
    observed_evidence = dict(evidence or {})
    item = CanonicalAdObservation(
        canonical_campaign_id=str(canonical_campaign_id).strip(),
        provider_observation_id=str(provider_observation_id).strip(),
        observation=observation,
        evidence=observed_evidence,
        payload_sha256=_payload_hash(
            observation,
            observed_evidence,
        ),
        canonical_creative_id=(
            str(canonical_creative_id).strip()
            if canonical_creative_id is not None
            else None
        ),
    )
    item.validate()
    return item
