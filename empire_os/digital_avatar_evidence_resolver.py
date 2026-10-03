"""Evidence resolvers for private Digital Avatar response drafting."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from empire_os.canonical_data_gateway import CanonicalDataGateway
from empire_os.digital_avatar_canonical_evidence import (
    CanonicalCommercialEvidenceResolver,
    CanonicalCommercialOutcomeResolver,
    CanonicalCommercialProductResolver,
    CanonicalCommercialTermsResolver,
)
from empire_os.digital_avatar_evidence_pack import AvatarEvidenceResolver


class CompositeAvatarEvidenceResolver:
    def __init__(self, resolvers: Iterable[AvatarEvidenceResolver]) -> None:
        self.resolvers = tuple(resolvers)

    def resolve(self, evidence_ref: str) -> Mapping[str, Any] | None:
        for resolver in self.resolvers:
            value = resolver.resolve(evidence_ref)
            if value is not None:
                return value
        return None


class RecallObservationEvidenceResolver:
    """Resolve exact signed Recall observation refs from the private store."""

    def __init__(self, observation_root: str | Path) -> None:
        self.observation_root = Path(observation_root)

    def resolve(self, evidence_ref: str) -> Mapping[str, Any] | None:
        clean_ref = str(evidence_ref or "").strip()
        if not clean_ref.startswith("recall:"):
            return None
        if not self.observation_root.is_dir():
            return None

        for path in sorted(self.observation_root.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(raw, Mapping):
                continue
            observation = raw.get("observation")
            if not isinstance(observation, Mapping):
                continue
            if str(observation.get("evidence_ref") or "").strip() != clean_ref:
                continue
            text = " ".join(str(observation.get("text") or "").split())
            if not text:
                return None
            verification_ref = str(raw.get("verification_ref") or "").strip()
            if not verification_ref:
                return None
            return {
                "evidence_ref": clean_ref,
                "content": text,
                "truth_class": "OBSERVED",
                "source_kind": "meeting_transcript",
                "provenance": verification_ref,
                "verified": True,
            }
        return None


class MappingAvatarEvidenceResolver:
    """Explicit in-memory adapter for already-normalized canonical evidence."""

    def __init__(self, values: Mapping[str, Mapping[str, Any]]) -> None:
        self.values = {
            str(key): dict(value)
            for key, value in values.items()
            if isinstance(value, Mapping)
        }

    def resolve(self, evidence_ref: str) -> Mapping[str, Any] | None:
        value = self.values.get(str(evidence_ref or "").strip())
        return dict(value) if value is not None else None


def build_canonical_commercial_evidence_resolver(
    gateway: CanonicalDataGateway,
) -> CompositeAvatarEvidenceResolver:
    """Compose buyer-safe canonical commercial evidence only."""
    return CompositeAvatarEvidenceResolver((
        CanonicalCommercialEvidenceResolver(gateway),
        CanonicalCommercialProductResolver(gateway),
        CanonicalCommercialTermsResolver(gateway),
        CanonicalCommercialOutcomeResolver(gateway),
    ))


def build_production_avatar_evidence_resolver(
    *,
    observation_root: str | Path,
    gateway: CanonicalDataGateway,
) -> CompositeAvatarEvidenceResolver:
    """Compose only production-safe evidence sources for Avatar drafting."""
    commercial = build_canonical_commercial_evidence_resolver(gateway)
    return CompositeAvatarEvidenceResolver((
        RecallObservationEvidenceResolver(observation_root),
        *commercial.resolvers,
    ))
