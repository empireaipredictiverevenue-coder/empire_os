"""Outcome calibration for Empire Hunter.

Only verified downstream observations may influence contact/pattern confidence.
Forecasts, model scores, and unverified outcomes are ignored.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from empire_os.hunter.models import ContactEvidence, VerificationState
from empire_os.hunter.pattern_brain import infer_pattern, normalize_domain


VERIFIED_EVENT_WEIGHTS = {
    "delivered": 0.10,
    "reply_received": 0.18,
    "positive_reply": 0.22,
    "meeting_booked": 0.28,
    "agreement_signed": 0.32,
    "payment_verified": 0.36,
    "revenue_recognized": 0.40,
    "bounced": -0.70,
    "complained": -0.85,
    "suppressed": -0.90,
}


@dataclass(frozen=True)
class HunterOutcomeObservation:
    email: str
    event_type: str
    observed_at: str
    verified: bool
    evidence_ref: str
    person_name: str | None = None
    domain: str | None = None
    actual_revenue_cents: int | None = None
    gross_profit_cents: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContactCalibration:
    email: str
    prior_confidence: float
    posterior_confidence: float
    state: VerificationState
    verified_events: tuple[str, ...]
    ignored_events: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    actual_revenue_cents: int | None
    gross_profit_cents: int | None
    actual_revenue_observed: bool
    realized_gp_observed: bool

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["state"] = self.state.value
        return data


@dataclass(frozen=True)
class PatternOutcomeCalibration:
    domain: str
    pattern: str | None
    verified_attempts: int
    positive_events: int
    negative_events: int
    delivered_or_better: int
    confidence_delta: float
    evidence_refs: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _bounded_confidence(value: float) -> float:
    return round(max(0.0, min(0.999, value)), 4)


def calibrate_contact(
    contact: ContactEvidence,
    observations: Iterable[Mapping[str, Any] | HunterOutcomeObservation],
) -> ContactCalibration:
    email = contact.email.strip().lower()
    confidence = float(contact.confidence)
    verified_events: list[str] = []
    ignored_events: list[str] = []
    evidence_refs: list[str] = []
    actual_revenue_values: list[int] = []
    gp_values: list[int] = []

    for raw in observations:
        row = raw.as_dict() if isinstance(raw, HunterOutcomeObservation) else dict(raw)
        if str(row.get("email") or "").strip().lower() != email:
            continue

        event_type = str(row.get("event_type") or "").strip().lower()
        verified = row.get("verified") is True
        evidence_ref = str(row.get("evidence_ref") or "").strip()
        if not verified or not evidence_ref:
            ignored_events.append(event_type or "unknown")
            continue

        weight = VERIFIED_EVENT_WEIGHTS.get(event_type)
        if weight is None:
            ignored_events.append(event_type or "unknown")
            continue

        verified_events.append(event_type)
        evidence_refs.append(evidence_ref)
        confidence += weight

        if row.get("actual_revenue_cents") is not None:
            actual_revenue_values.append(int(row["actual_revenue_cents"]))
        if row.get("gross_profit_cents") is not None:
            gp_values.append(int(row["gross_profit_cents"]))

    unique_events = tuple(dict.fromkeys(verified_events))
    unique_refs = tuple(dict.fromkeys(evidence_refs))
    posterior = _bounded_confidence(confidence)

    if any(
        event in {"bounced", "complained", "suppressed"}
        for event in unique_events
    ):
        state = VerificationState.REJECTED
        posterior = min(posterior, 0.10)
    elif any(
        event in {
            "delivered",
            "reply_received",
            "positive_reply",
            "meeting_booked",
            "agreement_signed",
            "payment_verified",
            "revenue_recognized",
        }
        for event in unique_events
    ):
        state = VerificationState.CONFIRMED
        posterior = max(posterior, 0.95)
    else:
        state = contact.state

    return ContactCalibration(
        email=email,
        prior_confidence=round(contact.confidence, 4),
        posterior_confidence=round(posterior, 4),
        state=state,
        verified_events=unique_events,
        ignored_events=tuple(dict.fromkeys(ignored_events)),
        evidence_refs=unique_refs,
        actual_revenue_cents=(
            sum(actual_revenue_values) if actual_revenue_values else None
        ),
        gross_profit_cents=(sum(gp_values) if gp_values else None),
        actual_revenue_observed=bool(actual_revenue_values),
        realized_gp_observed=bool(gp_values),
    )


def calibrate_pattern_outcomes(
    observations: Iterable[Mapping[str, Any] | HunterOutcomeObservation],
    *,
    domain: str,
) -> PatternOutcomeCalibration:
    host = normalize_domain(domain)
    attempts = 0
    positive = 0
    negative = 0
    delivered_or_better = 0
    patterns: list[str] = []
    refs: list[str] = []

    for raw in observations:
        row = raw.as_dict() if isinstance(raw, HunterOutcomeObservation) else dict(raw)
        if row.get("verified") is not True:
            continue
        evidence_ref = str(row.get("evidence_ref") or "").strip()
        if not evidence_ref:
            continue

        email = str(row.get("email") or "").strip().lower()
        person_name = str(row.get("person_name") or "").strip()
        row_domain = normalize_domain(
            str(row.get("domain") or (email.rsplit("@", 1)[1] if "@" in email else ""))
        )
        if row_domain != host:
            continue

        pattern = infer_pattern(email, person_name, domain=host) if person_name else None
        if pattern:
            patterns.append(pattern)

        event_type = str(row.get("event_type") or "").strip().lower()
        if event_type not in VERIFIED_EVENT_WEIGHTS:
            continue

        attempts += 1
        refs.append(evidence_ref)
        if VERIFIED_EVENT_WEIGHTS[event_type] > 0:
            positive += 1
            delivered_or_better += 1
        else:
            negative += 1

    chosen = None
    if patterns:
        counts: dict[str, int] = {}
        for pattern in patterns:
            counts[pattern] = counts.get(pattern, 0) + 1
        chosen = max(counts, key=counts.get)

    delta = 0.0
    if attempts:
        delta = ((positive - negative) / attempts) * min(0.25, 0.05 * attempts)

    return PatternOutcomeCalibration(
        domain=host,
        pattern=chosen,
        verified_attempts=attempts,
        positive_events=positive,
        negative_events=negative,
        delivered_or_better=delivered_or_better,
        confidence_delta=round(delta, 4),
        evidence_refs=tuple(dict.fromkeys(refs)),
    )
