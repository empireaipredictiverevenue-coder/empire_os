"""Phase 7 freshness gate for evidence-only qualification signals."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from empire_os.conversation_qualification import ConversationQualificationReview


@dataclass(frozen=True)
class QualificationFreshnessReview:
    conversation_id: str
    fresh_for_operator_review: bool
    signal_ages_seconds: dict[str, float]
    blockers: tuple[str, ...]
    execution_authority: str = "none"
    send_execution: bool = False
    call_execution: bool = False
    voice_streaming: bool = False
    booking_execution: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_timestamp(value: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("qualification evidence timestamp required")
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(
            "qualification evidence timestamp must be ISO-8601"
        ) from exc
    if parsed.tzinfo is None:
        raise ValueError(
            "qualification evidence timestamp must include timezone"
        )
    return parsed.astimezone(timezone.utc)


def review_qualification_freshness(
    review: ConversationQualificationReview,
    *,
    now: datetime,
    max_age_seconds: int = 21600,
) -> QualificationFreshnessReview:
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")
    if now.tzinfo is None:
        raise ValueError("now must include timezone")

    blockers = list(review.blockers)
    ages: dict[str, float] = {}
    current = now.astimezone(timezone.utc)

    if not review.signal_evidence:
        blockers.append("explicit_qualification_evidence_missing")
    for item in review.signal_evidence:
        observed = _parse_timestamp(item.occurred_at)
        age = (current - observed).total_seconds()
        key = f"{item.provider_event_id}:{item.signal}"
        ages[key] = round(age, 3)
        if age < -60:
            blockers.append(f"{key}:evidence_from_future")
        elif age > max_age_seconds:
            blockers.append(f"{key}:evidence_stale")

    ordered = tuple(sorted(set(blockers)))
    return QualificationFreshnessReview(
        conversation_id=review.conversation_id,
        fresh_for_operator_review=not ordered,
        signal_ages_seconds=ages,
        blockers=ordered,
    )
