"""Canonical Economic Signal Fabric contract.

Economic Signal Fabric is the evidence boundary between EmpireOS observation
systems and opportunity intelligence.

It does NOT grant execution authority and does NOT establish tenant ownership
from caller input.

Evidence flow:

    source observation
      -> canonical entity
      -> canonical source
      -> economic signal validation
      -> deterministic identity / deduplication
      -> opportunity convergence
      -> Radar / Factory / Predictive Revenue

Tenant ownership must already be verified by a trusted canonical reader.
Supplying a tenant_id alone is not proof of ownership.

Unknown remains unknown. OBSERVE only.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from math import isfinite
from typing import Any
from uuid import UUID


SCHEMA_VERSION = "empire.economic-signal.v1"

SUPPORTED_SIGNAL_TYPES = frozenset({
    "revenue_leak",
    "idle_asset",
    "market_gap",
    "idle_waste",
})

SUPPORTED_TRUTH_CLASSES = frozenset({
    "OBSERVED",
})

MAX_SIGNAL_AGE_SECONDS = 86400


class EconomicSignalError(ValueError):
    """Economic signal fails the canonical evidence contract."""


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _uuid(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    try:
        return str(UUID(text))
    except (ValueError, TypeError, AttributeError):
        return ""


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError, OverflowError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _score(value: Any) -> float | None:
    if type(value) not in (int, float):
        return None
    value = float(value)
    if not isfinite(value) or not 0 <= value <= 1:
        return None
    return value


def _stable_key(*parts: Any) -> str:
    material = "|".join(str(part) for part in parts)
    return sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EconomicSignal:
    signal_id: str
    tenant_id: str
    tenant_binding_ref: str
    entity_id: str
    source_id: str
    signal_type: str
    signal_domain: str
    observed_at: str
    expires_at: str | None
    strength: float
    confidence: float
    evidence_refs: tuple[str, ...]
    payload: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "signal_id": self.signal_id,
            "tenant_id": self.tenant_id,
            "tenant_binding_ref": self.tenant_binding_ref,
            "entity_id": self.entity_id,
            "source_id": self.source_id,
            "signal_type": self.signal_type,
            "signal_domain": self.signal_domain,
            "observed_at": self.observed_at,
            "expires_at": self.expires_at,
            "strength": self.strength,
            "confidence": self.confidence,
            "evidence_refs": list(self.evidence_refs),
            "payload": dict(self.payload),
            "truth_class": "OBSERVED",
            "data_backend": "empiredb",
            "execution_authority": "none",
            "outreach_authority": "none",
            "calls_authority": "none",
            "traffic_authority": "none",
            "commercial_authority": "none",
            "payment_authority": "none",
            "revenue_recognition_authority": "none",
        }


def validate_economic_signal(
    row: Mapping[str, Any],
    *,
    expected_tenant_id: str,
    as_of: datetime,
) -> EconomicSignal:
    """Validate trusted canonical evidence without manufacturing provenance."""

    if not isinstance(row, Mapping):
        raise EconomicSignalError("signal_mapping_required")

    tenant_id = _text(row.get("tenant_id"))
    expected_tenant = _text(expected_tenant_id)

    if not expected_tenant:
        raise EconomicSignalError("expected_tenant_required")

    if tenant_id != expected_tenant:
        raise EconomicSignalError("tenant_mismatch")

    # Crucial invariant:
    # tenant_id alone is NOT evidence. A trusted canonical reader must supply
    # an immutable provenance reference proving how entity ownership/scope was
    # established.
    tenant_binding_ref = _text(row.get("tenant_binding_ref"))
    if not tenant_binding_ref:
        raise EconomicSignalError("verified_tenant_binding_required")

    entity_id = _uuid(row.get("entity_id"))
    if not entity_id:
        raise EconomicSignalError("canonical_entity_required")

    source_id = _uuid(row.get("source_id"))
    if not source_id:
        raise EconomicSignalError("canonical_source_required")

    signal_type = _text(row.get("signal_type"))
    if signal_type not in SUPPORTED_SIGNAL_TYPES:
        raise EconomicSignalError("unsupported_signal_type")

    signal_domain = _text(row.get("signal_domain"))
    if not signal_domain:
        raise EconomicSignalError("signal_domain_required")

    if row.get("truth_class") != "OBSERVED":
        raise EconomicSignalError("observed_truth_required")

    if row.get("data_backend") != "empiredb":
        raise EconomicSignalError("canonical_backend_required")

    observed = _timestamp(row.get("observed_at"))
    if observed is None:
        raise EconomicSignalError("aware_observed_at_required")

    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise EconomicSignalError("aware_as_of_required")

    canonical_as_of = as_of.astimezone(timezone.utc)
    age = (canonical_as_of - observed).total_seconds()

    if age < 0:
        raise EconomicSignalError("future_observation_rejected")

    if age > MAX_SIGNAL_AGE_SECONDS:
        raise EconomicSignalError("stale_observation")

    expires = None
    if row.get("expires_at") is not None:
        expires_dt = _timestamp(row.get("expires_at"))
        if expires_dt is None:
            raise EconomicSignalError("invalid_expiry")
        if expires_dt <= canonical_as_of:
            raise EconomicSignalError("expired_signal")
        expires = expires_dt.isoformat()

    strength = _score(row.get("strength"))
    if strength is None:
        raise EconomicSignalError("invalid_strength")

    confidence = _score(row.get("confidence"))
    if confidence is None:
        raise EconomicSignalError("invalid_confidence")

    raw_refs = row.get("evidence_refs")
    if (
        not isinstance(raw_refs, (list, tuple))
        or not raw_refs
        or any(not _text(ref) for ref in raw_refs)
    ):
        raise EconomicSignalError("evidence_refs_required")

    evidence_refs = tuple(dict.fromkeys(_text(ref) for ref in raw_refs))

    payload = row.get("payload")
    if not isinstance(payload, Mapping):
        raise EconomicSignalError("payload_mapping_required")

    # Stable identity deliberately excludes confidence/strength so rescoring the
    # same observation cannot manufacture another economic event.
    signal_id = "economic_signal_" + _stable_key(
        tenant_id,
        tenant_binding_ref,
        entity_id,
        source_id,
        signal_type,
        signal_domain,
        observed.isoformat(),
        *evidence_refs,
    )

    return EconomicSignal(
        signal_id=signal_id,
        tenant_id=tenant_id,
        tenant_binding_ref=tenant_binding_ref,
        entity_id=entity_id,
        source_id=source_id,
        signal_type=signal_type,
        signal_domain=signal_domain,
        observed_at=observed.isoformat(),
        expires_at=expires,
        strength=strength,
        confidence=confidence,
        evidence_refs=evidence_refs,
        payload=dict(payload),
    )


def normalize_economic_signals(
    rows: Iterable[Mapping[str, Any]],
    *,
    expected_tenant_id: str,
    as_of: datetime,
) -> dict[str, Any]:
    """Validate, dedupe and quarantine malformed economic evidence."""

    accepted: dict[str, EconomicSignal] = {}
    rejected: list[dict[str, Any]] = []
    conflicts: set[str] = set()

    for index, row in enumerate(rows):
        try:
            signal = validate_economic_signal(
                row,
                expected_tenant_id=expected_tenant_id,
                as_of=as_of,
            )
        except EconomicSignalError as exc:
            rejected.append({
                "index": index,
                "reason": str(exc),
            })
            continue

        previous = accepted.get(signal.signal_id)
        if previous is None:
            accepted[signal.signal_id] = signal
            continue

        if previous.as_dict() != signal.as_dict():
            conflicts.add(signal.signal_id)

    for signal_id in conflicts:
        accepted.pop(signal_id, None)

    return {
        "schema_version": SCHEMA_VERSION,
        "tenant_id": _text(expected_tenant_id),
        "accepted": [
            accepted[key].as_dict()
            for key in sorted(accepted)
        ],
        "rejected": rejected,
        "conflicting_signal_ids": sorted(conflicts),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "conflict_count": len(conflicts),
        "execution_authority": "none",
        "unknown_stays_unknown": True,
    }
