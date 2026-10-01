"""Evidence-first Partnership Progression for EmpireOS.

This module describes relationship maturity from explicit evidence only.
It does not score accounts, infer intent, send outreach, bind terms, move funds,
recognize revenue, or grant execution authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


POSITIVE_STATES: tuple[str, ...] = (
    "DISCOVERED",
    "PERSON_BOUND",
    "PARTNERSHIP_CANDIDATE",
    "ENGAGED",
    "NEEDS_DISCOVERED",
    "VALUE_PROVEN",
    "PILOT",
    "COMMERCIAL_PARTNER",
    "EXPANSION",
)

NEGATIVE_PRECEDENCE: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("STOP", ("suppressed", "opt_out", "explicit_rejection")),
    ("NO_FIT", ("verified_no_fit", "negative_economics")),
    ("HOLD", ("capacity_hold", "timing_hold")),
    ("STALLED", ("explicit_stalled",)),
)


def _flag(evidence: Mapping[str, Any], key: str) -> bool:
    return evidence.get(key) is True


def _refs(evidence: Mapping[str, Any]) -> tuple[str, ...]:
    values = evidence.get("evidence_refs") or ()
    if not isinstance(values, (list, tuple, set)):
        return ()
    return tuple(
        dict.fromkeys(
            str(value).strip()
            for value in values
            if str(value).strip()
        )
    )


@dataclass(frozen=True)
class PartnershipProgression:
    state: str
    state_class: str
    observed_positive_states: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    reasons: tuple[str, ...]
    blockers: tuple[str, ...]
    buyer_intent_inferred: bool = False
    commercial_intent_inferred: bool = False
    outreach_authorized: bool = False
    payment_authorized: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def derive_partnership_progression(
    evidence: Mapping[str, Any] | None,
) -> PartnershipProgression:
    """Derive one current relationship state from explicit evidence.

    Missing evidence remains UNKNOWN. Earlier positive stages are never inferred
    merely because a later stage is observed.
    """
    row = dict(evidence or {})
    refs = _refs(row)

    observed_positive = tuple(
        state
        for state in POSITIVE_STATES
        if _flag(row, state.lower())
    )

    negative_matches: list[tuple[str, tuple[str, ...]]] = []
    for state, keys in NEGATIVE_PRECEDENCE:
        matched = tuple(key for key in keys if _flag(row, key))
        if matched:
            negative_matches.append((state, matched))

    candidate_state: str
    state_class: str
    reasons: tuple[str, ...]

    if negative_matches:
        candidate_state, matched = negative_matches[0]
        state_class = "negative"
        reasons = tuple(f"explicit:{key}" for key in matched)
    elif observed_positive:
        candidate_state = observed_positive[-1]
        state_class = "positive"
        reasons = (f"explicit:{candidate_state.lower()}",)
    else:
        candidate_state = "UNKNOWN"
        state_class = "unknown"
        reasons = ("no_explicit_partnership_state_evidence",)

    blockers: list[str] = []
    if candidate_state != "UNKNOWN" and not refs:
        blockers.append("evidence_refs_missing")
        candidate_state = "UNKNOWN"
        state_class = "unknown"
        reasons = ("state_signal_without_evidence_reference",)

    return PartnershipProgression(
        state=candidate_state,
        state_class=state_class,
        observed_positive_states=observed_positive,
        evidence_refs=refs,
        reasons=reasons,
        blockers=tuple(blockers),
    )
