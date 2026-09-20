"""Phase 7 evidence-only human escalation readiness."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.conversation_qualification import ConversationQualificationReview
from empire_os.conversation_qualification_freshness import (
    QualificationFreshnessReview,
)


@dataclass(frozen=True)
class ConversationEscalationReadiness:
    conversation_id: str
    closer_case_id: str | None
    ready_for_human_escalation_review: bool
    observed_signals: tuple[str, ...]
    blockers: tuple[str, ...]
    execution_authority: str = "none"
    human_escalation_execution: bool = False
    call_execution: bool = False
    voice_streaming: bool = False
    booking_execution: bool = False
    closer_state_mutation: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def review_human_escalation_readiness(
    *,
    qualification: ConversationQualificationReview,
    freshness: QualificationFreshnessReview,
    closer_case_id: str | None,
) -> ConversationEscalationReadiness:
    if qualification.conversation_id != freshness.conversation_id:
        raise ValueError("qualification/freshness conversation mismatch")

    blockers = list(freshness.blockers)
    closer = str(closer_case_id or "").strip() or None
    if closer is None:
        blockers.append("canonical_closer_case_missing")
    if not qualification.observed_signals:
        blockers.append("explicit_qualification_signals_missing")
    if not freshness.fresh_for_operator_review:
        blockers.append("qualification_not_fresh_for_operator_review")

    ordered = tuple(sorted(set(blockers)))
    return ConversationEscalationReadiness(
        conversation_id=qualification.conversation_id,
        closer_case_id=closer,
        ready_for_human_escalation_review=not ordered,
        observed_signals=qualification.observed_signals,
        blockers=ordered,
    )
