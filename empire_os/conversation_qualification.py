"""Phase 7 evidence-only conversation qualification review."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from empire_os.conversation_os import ConversationDirection


ALLOWED_SIGNALS = frozenset({
    "interest",
    "commercial_need",
    "decision_authority",
    "timing",
    "budget",
})


@dataclass(frozen=True)
class QualificationSignalEvidence:
    signal: str
    provider_event_id: str
    occurred_at: str
    transcript_ref: str
    evidence_ref: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConversationQualificationReview:
    conversation_id: str
    inbound_event_count: int
    transcript_backed_inbound_count: int
    observed_signals: tuple[str, ...]
    signal_evidence: tuple[QualificationSignalEvidence, ...]
    review_state: str
    evidence_available_for_operator_review: bool
    blockers: tuple[str, ...]
    execution_authority: str = "none"
    send_execution: bool = False
    call_execution: bool = False
    voice_streaming: bool = False
    booking_execution: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "signal_evidence": [
                item.as_dict() for item in self.signal_evidence
            ],
        }


def review_conversation_qualification(
    rows: Sequence[Mapping[str, Any]],
    *,
    conversation_id: str,
) -> ConversationQualificationReview:
    cid = str(conversation_id or "").strip()
    if not cid:
        raise ValueError("conversation_id required")

    inbound = 0
    transcript_backed = 0
    evidence_rows: list[QualificationSignalEvidence] = []

    for row in rows:
        row_cid = str(row.get("conversation_id") or "").strip()
        if row_cid != cid:
            raise ValueError("qualification review contains mixed identities")

        direction_raw = str(row.get("direction") or "").strip().lower()
        try:
            direction = ConversationDirection(direction_raw)
        except ValueError as exc:
            raise ValueError("unsupported conversation direction") from exc
        if direction is not ConversationDirection.INBOUND:
            continue
        inbound += 1

        event_id = str(row.get("provider_event_id") or "").strip()
        occurred_at = str(row.get("occurred_at") or "").strip()
        evidence = dict(row.get("evidence") or {})
        transcript_ref = str(evidence.get("transcript_ref") or "").strip()
        evidence_ref = str(evidence.get("evidence_ref") or "").strip()
        raw_signals = evidence.get("qualification_signals") or ()

        if transcript_ref:
            transcript_backed += 1

        if not (
            event_id
            and occurred_at
            and transcript_ref
            and evidence_ref
            and isinstance(raw_signals, (list, tuple))
        ):
            continue

        for raw_signal in raw_signals:
            signal = str(raw_signal or "").strip().lower()
            if signal not in ALLOWED_SIGNALS:
                continue
            evidence_rows.append(QualificationSignalEvidence(
                signal=signal,
                provider_event_id=event_id,
                occurred_at=occurred_at,
                transcript_ref=transcript_ref,
                evidence_ref=evidence_ref,
            ))


    signals = tuple(sorted({
        item.signal for item in evidence_rows
    }))
    blockers: list[str] = []
    if inbound == 0:
        state = "no_observed_inbound_response"
        blockers.append("inbound_response_not_observed")
    elif transcript_backed == 0:
        state = "inbound_observed_without_transcript_evidence"
        blockers.append("transcript_evidence_missing")
    elif not signals:
        state = "inbound_observed_no_explicit_qualification_signals"
        blockers.append("explicit_qualification_signals_missing")
    else:
        state = "explicit_qualification_evidence_observed"

    return ConversationQualificationReview(
        conversation_id=cid,
        inbound_event_count=inbound,
        transcript_backed_inbound_count=transcript_backed,
        observed_signals=signals,
        signal_evidence=tuple(evidence_rows),
        review_state=state,
        evidence_available_for_operator_review=bool(signals),
        blockers=tuple(blockers),
    )
