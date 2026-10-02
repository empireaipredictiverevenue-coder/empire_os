"""Evidence-backed revenue inventory ladder.

Classifies canonical prospect supply into the highest monetizable stage that is
actually supported by evidence. No database/network access and no execution.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from empire_os.buyer_allocation import (
    qualification_decision,
    qualification_identity_decision,
)
from empire_os.conversation_qualification import ALLOWED_SIGNALS

RAW_LEAD = "RAW_LEAD"
PREQUALIFIED_LEAD = "PREQUALIFIED_LEAD"
QUALIFIED_CALL = "QUALIFIED_CALL"
BOOKED_APPOINTMENT = "BOOKED_APPOINTMENT"
CPA_OUTCOME = "CPA_OUTCOME"

STAGES = (
    RAW_LEAD,
    PREQUALIFIED_LEAD,
    QUALIFIED_CALL,
    BOOKED_APPOINTMENT,
    CPA_OUTCOME,
)

MONETIZATION_MODEL = {
    RAW_LEAD: None,
    PREQUALIFIED_LEAD: "PPL",
    QUALIFIED_CALL: "PAY_PER_CALL",
    BOOKED_APPOINTMENT: "BOOKED_APPOINTMENT",
    CPA_OUTCOME: "CPA",
}

PRODUCT_FAMILY = {
    RAW_LEAD: None,
    PREQUALIFIED_LEAD: "ppl",
    QUALIFIED_CALL: "call",
    BOOKED_APPOINTMENT: "appointment",
    CPA_OUTCOME: "hybrid",
}


@dataclass(frozen=True)
class RevenueInventoryClassification:
    prospect_id: str
    stage: str
    monetization_model: str | None
    product_family: str | None
    evidence_refs: tuple[str, ...]
    blockers: tuple[str, ...]
    price_cents: int | None = None
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _call_evidence(rows: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    refs: list[str] = []
    for row in rows:
        if str(row.get("channel") or "").strip().lower() != "voice":
            continue
        if str(row.get("direction") or "").strip().lower() != "inbound":
            continue
        evidence = row.get("evidence")
        if not isinstance(evidence, Mapping):
            continue
        transcript_ref = str(evidence.get("transcript_ref") or "").strip()
        evidence_ref = str(evidence.get("evidence_ref") or "").strip()
        signals = evidence.get("qualification_signals")
        if not isinstance(signals, (list, tuple)):
            continue
        observed = {
            str(signal or "").strip().lower()
            for signal in signals
        } & ALLOWED_SIGNALS
        if transcript_ref and evidence_ref and observed:
            refs.extend((transcript_ref, evidence_ref))
    return tuple(dict.fromkeys(refs))


def _outcome_evidence(
    outcomes: Sequence[Mapping[str, Any]],
    conversion_outcome: str,
) -> tuple[str, ...]:
    refs: list[str] = []
    for row in outcomes:
        if str(row.get("conversion_outcome") or "").strip().lower() != conversion_outcome:
            continue
        ref = str(row.get("evidence_reference") or "").strip()
        if ref:
            refs.append(ref)
    return tuple(dict.fromkeys(refs))


def classify_revenue_inventory(
    *,
    prospect: Mapping[str, Any],
    qualification: Mapping[str, Any] | None = None,
    identity_link: Mapping[str, Any] | None = None,
    conversation_events: Sequence[Mapping[str, Any]] = (),
    commercial_outcomes: Sequence[Mapping[str, Any]] = (),
) -> RevenueInventoryClassification:
    prospect_id = str(prospect.get("id") or "").strip()
    if not prospect_id:
        raise ValueError("prospect id required")

    stage = RAW_LEAD
    evidence_refs = [f"prospect:{prospect_id}"]
    blockers: list[str] = []

    qualified, qualification_reason = qualification_decision(
        dict(qualification) if isinstance(qualification, Mapping) else None
    )
    identity_ok, identity_reason = qualification_identity_decision(
        prospect_id,
        dict(qualification) if isinstance(qualification, Mapping) else None,
        dict(identity_link) if isinstance(identity_link, Mapping) else None,
    )

    if qualified and identity_ok:
        stage = PREQUALIFIED_LEAD
        qid = str((qualification or {}).get("id") or "").strip()
        entity_id = str((identity_link or {}).get("entity_id") or "").strip()
        if qid:
            evidence_refs.append(f"qualification:{qid}")
        if entity_id:
            evidence_refs.append(f"entity:{entity_id}")
    else:
        if not qualified:
            blockers.append(qualification_reason)
        if not identity_ok:
            blockers.append(identity_reason)

    call_refs = _call_evidence(conversation_events)
    if stage != RAW_LEAD and call_refs:
        stage = QUALIFIED_CALL
        evidence_refs.extend(call_refs)

    booked_refs = _outcome_evidence(commercial_outcomes, "booked")
    if stage in {PREQUALIFIED_LEAD, QUALIFIED_CALL} and booked_refs:
        stage = BOOKED_APPOINTMENT
        evidence_refs.extend(booked_refs)

    won_refs = _outcome_evidence(commercial_outcomes, "won")
    if stage in {
        PREQUALIFIED_LEAD,
        QUALIFIED_CALL,
        BOOKED_APPOINTMENT,
    } and won_refs:
        stage = CPA_OUTCOME
        evidence_refs.extend(won_refs)

    return RevenueInventoryClassification(
        prospect_id=prospect_id,
        stage=stage,
        monetization_model=MONETIZATION_MODEL[stage],
        product_family=PRODUCT_FAMILY[stage],
        evidence_refs=tuple(dict.fromkeys(evidence_refs)),
        blockers=tuple(dict.fromkeys(blockers)),
        price_cents=None,
    )
