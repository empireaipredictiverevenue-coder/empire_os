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


def _stage_time(value):
    from datetime import datetime
    clock = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if clock.tzinfo is None:
        raise ValueError("timezone-aware commercial stage evidence required")
    return clock


def _observed_stage_row(row, *, as_of):
    """Reject explicit non-observations, including nested evidence flags."""
    if not isinstance(row, Mapping):
        raise ValueError("canonical commercial stage record required")
    if (any(row.get(key) is True for key in ("synthetic", "forecast_derived", "model_inferred", "advisory"))
            or row.get("verified") is False
            or row.get("source_type") in ("model", "model_inference", "ai_generated", "forecast", "prediction", "recommendation")):
        raise ValueError("commercial stage must be persisted observed evidence")
    for key, value in row.items():
        if isinstance(value, Mapping):
            _observed_stage_row(value, as_of=as_of)
        elif key in ("created_at", "occurred_at", "proposed_at", "decided_at", "approved_at",
                     "accepted_at", "qualified_at", "terms_approved_at", "buyer_accepted_at") and value:
            if _stage_time(value) > as_of:
                raise ValueError("future commercial stage evidence")


def _validate_stage_binding(stage, record, *, as_of):
    if as_of.tzinfo is None or stage.get("execution_authority") != "none":
        raise ValueError("commercial stage cannot grant authority")
    if not record.get("intent_id") or stage.get("outbound_intent_id") != record["intent_id"]:
        raise ValueError("commercial stage outbound intent mismatch")
    for key in ("tenant_id", "outbound_intent_id", "reply_id", "closer_case_id", "prospect_id", "buyer_id", "opportunity_id"):
        if not stage.get(key):
            raise ValueError(f"commercial stage {key} missing")
        if key in record and record[key] != stage[key]:
            raise ValueError(f"commercial stage {key} mismatch")
    if not record.get("tenant_id"):
        raise ValueError("commercial stage tenant scope required")
    for key in ("conversation_id", "fulfilment_order_id", "prediction_ref", "decision_ref", "execution_ref", "outcome_ref"):
        if record.get(key) is not None and record[key] != stage.get(key):
            raise ValueError(f"commercial stage {key} mismatch")
    _observed_stage_row(stage, as_of=as_of)


def build_persisted_qualification_stage(event, *, context, as_of):
    """Read the existing closer's recorded qualification decision, never its model review."""
    _observed_stage_row(event, as_of=as_of)
    payload = event.get("payload") or {}
    if context.get("closer_state") not in ("qualified", "proposal_ready", "proposal_approved", "awaiting_payment", "won", "lost", "paused"):
        raise ValueError("qualification event contradicts persisted closer progression")
    if (not event.get("id") or event.get("case_id") != context.get("closer_case_id")
            or event.get("event_type") != "state_advanced" or payload.get("state") != "qualified"
            or not str(event.get("actor") or "").strip() or not str(payload.get("note") or "").strip()):
        raise ValueError("persisted qualification decision with actor and rationale required")
    for key in ("tenant_id", "outbound_intent_id", "reply_id", "conversation_id", "closer_case_id",
                "prospect_id", "buyer_id", "opportunity_id", "fulfilment_order_id"):
        for row in (event, payload):
            if row.get(key) is not None and row[key] != context.get(key):
                raise ValueError(f"qualification {key} mismatch")
    qualified_at = _stage_time(event.get("occurred_at"))
    if qualified_at > as_of:
        raise ValueError("future qualification decision")
    return {**context, "schema_version": "empire.outreach-qualified-conversation.v1",
            "state": "QUALIFIED", "qualified_at": qualified_at.isoformat(),
            "stage_ref": "canonical:closer_events:" + event["id"],
            "evidence_refs": ["canonical:closer_events:" + event["id"],
                              "canonical:outbound_replies:" + context["reply_id"]],
            "source": "persisted_closer_state_advanced", "qualification_event": dict(event),
            "execution_authority": "none"}


def validate_qualified_conversation_stage(stage, record, *, as_of):
    _validate_stage_binding(stage, record, as_of=as_of)
    if stage.get("schema_version") != "empire.outreach-qualified-conversation.v1":
        raise ValueError("canonical qualification contract required")
    expected = build_persisted_qualification_stage(stage.get("qualification_event"), context=stage, as_of=as_of)
    for key in ("state", "qualified_at", "stage_ref", "evidence_refs", "source"):
        if stage.get(key) != expected[key]:
            raise ValueError("qualification evidence projection mismatch")
