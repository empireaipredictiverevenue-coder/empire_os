"""Temporal commercial signal derivation for Empire Hunter."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class HunterSignal:
    entity_id: str
    signal_type: str
    observed_at: str
    strength: float
    confidence: float
    evidence_refs: tuple[str, ...]
    payload: dict[str, Any]
    expires_at: str | None = None
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _refs(values: Iterable[str]) -> tuple[str, ...]:
    refs = tuple(
        dict.fromkeys(
            str(value).strip()
            for value in values
            if str(value).strip()
        )
    )
    if not refs:
        raise ValueError("signal requires evidence refs")
    return refs


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def derive_temporal_signals(
    *,
    entity_id: str,
    observed_at: str,
    previous: Mapping[str, Any] | None,
    current: Mapping[str, Any],
    evidence_refs: Iterable[str],
) -> tuple[HunterSignal, ...]:
    eid = str(entity_id or "").strip()
    when = str(observed_at or "").strip()
    if not eid:
        raise ValueError("entity_id required")
    if not when:
        raise ValueError("observed_at required")

    refs = _refs(evidence_refs)
    before = dict(previous or {})
    now = dict(current or {})
    signals: list[HunterSignal] = []

    old_people = {
        (
            _norm(row.get("name")),
            _norm(row.get("title")),
        )
        for row in before.get("people") or []
        if isinstance(row, Mapping)
        and _norm(row.get("name"))
    }
    new_people = {
        (
            _norm(row.get("name")),
            _norm(row.get("title")),
        )
        for row in now.get("people") or []
        if isinstance(row, Mapping)
        and _norm(row.get("name"))
    }
    added_people = sorted(new_people - old_people)
    removed_people = sorted(old_people - new_people)
    if old_people and (added_people or removed_people):
        signals.append(
            HunterSignal(
                entity_id=eid,
                signal_type="leadership_change",
                observed_at=when,
                strength=0.85,
                confidence=0.9,
                evidence_refs=refs,
                payload={
                    "added": added_people,
                    "removed": removed_people,
                },
            )
        )

    old_contacts = {
        _norm(value)
        for value in before.get("emails") or []
        if _norm(value)
    }
    new_contacts = {
        _norm(value)
        for value in now.get("emails") or []
        if _norm(value)
    }
    contact_added = sorted(new_contacts - old_contacts)
    contact_removed = sorted(old_contacts - new_contacts)
    if old_contacts and (contact_added or contact_removed):
        signals.append(
            HunterSignal(
                entity_id=eid,
                signal_type="contact_surface_change",
                observed_at=when,
                strength=0.65,
                confidence=0.85,
                evidence_refs=refs,
                payload={
                    "added": contact_added,
                    "removed": contact_removed,
                },
            )
        )

    old_services = {
        _norm(value)
        for value in before.get("services") or []
        if _norm(value)
    }
    new_services = {
        _norm(value)
        for value in now.get("services") or []
        if _norm(value)
    }
    added_services = sorted(new_services - old_services)
    if old_services and added_services:
        signals.append(
            HunterSignal(
                entity_id=eid,
                signal_type="service_expansion",
                observed_at=when,
                strength=min(1.0, 0.55 + 0.08 * len(added_services)),
                confidence=0.8,
                evidence_refs=refs,
                payload={"added_services": added_services},
            )
        )

    old_domain = _norm(before.get("domain"))
    new_domain = _norm(now.get("domain"))
    if old_domain and new_domain and old_domain != new_domain:
        signals.append(
            HunterSignal(
                entity_id=eid,
                signal_type="domain_change",
                observed_at=when,
                strength=0.8,
                confidence=0.95,
                evidence_refs=refs,
                payload={
                    "previous_domain": old_domain,
                    "current_domain": new_domain,
                },
            )
        )

    previous_pattern = before.get("pattern")
    current_pattern = now.get("pattern")
    if isinstance(previous_pattern, Mapping) and isinstance(
        current_pattern,
        Mapping,
    ):
        old_pattern = _norm(previous_pattern.get("pattern"))
        new_pattern = _norm(current_pattern.get("pattern"))
        old_conf = float(previous_pattern.get("confidence") or 0.0)
        new_conf = float(current_pattern.get("confidence") or 0.0)
        if (
            new_pattern
            and (
                new_pattern != old_pattern
                or abs(new_conf - old_conf) >= 0.15
            )
        ):
            signals.append(
                HunterSignal(
                    entity_id=eid,
                    signal_type="email_pattern_shift",
                    observed_at=when,
                    strength=min(
                        1.0,
                        0.5 + abs(new_conf - old_conf),
                    ),
                    confidence=max(old_conf, new_conf),
                    evidence_refs=refs,
                    payload={
                        "previous_pattern": old_pattern or None,
                        "current_pattern": new_pattern,
                        "previous_confidence": round(old_conf, 4),
                        "current_confidence": round(new_conf, 4),
                    },
                )
            )

    return tuple(signals)


def outcome_signal(
    *,
    entity_id: str,
    event_type: str,
    observed_at: str,
    evidence_refs: Iterable[str],
    email: str | None = None,
) -> HunterSignal:
    mapping = {
        "delivered": ("contact_delivery_confirmed", 0.45, 0.99),
        "reply_received": ("contact_reply_confirmed", 0.75, 0.99),
        "bounced": ("contact_degraded", 0.9, 0.99),
        "complained": ("contact_complaint", 1.0, 0.99),
        "payment_verified": ("commercial_payment_signal", 1.0, 1.0),
    }
    key = str(event_type or "").strip().lower()
    if key not in mapping:
        raise ValueError("unsupported outcome signal type")
    signal_type, strength, confidence = mapping[key]
    return HunterSignal(
        entity_id=str(entity_id or "").strip(),
        signal_type=signal_type,
        observed_at=str(observed_at or "").strip(),
        strength=strength,
        confidence=confidence,
        evidence_refs=_refs(evidence_refs),
        payload={
            "event_type": key,
            "email": str(email or "").strip().lower() or None,
            "commercial_revenue": False,
        },
    )
