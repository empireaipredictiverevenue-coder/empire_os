"""Read-only conversation recovery projection for delivered first-touch email."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

from empire_os.conversation_value import build_followup_copy


FOLLOWUP_ONE_HOURS = 72
FOLLOWUP_TWO_HOURS = 168


@dataclass(frozen=True)
class RecoveryRow:
    root_intent_id: str
    recipient: str
    delivered_at: str
    age_hours: float
    hours_until_followup: float
    due_now: bool
    due_within_24h: bool
    business_name: str | None
    niche: str | None
    metro: str | None
    legacy_generic_subject: bool
    placeholder_evidence: bool
    recoverable: bool
    recovery_reason: str
    followup_subject_preview: str | None
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _parse_time(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _placeholder(value: Any) -> bool:
    return _text(value).lower() in {
        "", "unknown", "your team", "your market", "local market",
        "n/a", "none", "null",
    }


def _merge_context(
    intent: Mapping[str, Any],
    prospect: Mapping[str, Any] | None,
) -> dict[str, Any]:
    metadata = intent.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    candidate = metadata.get("candidate_evidence")
    candidate = dict(candidate) if isinstance(candidate, Mapping) else {}
    prospect = prospect or {}

    for key in ("business_name", "niche", "metro"):
        if _placeholder(candidate.get(key)):
            value = prospect.get(key)
            if key == "business_name":
                value = prospect.get("business_name")
            if not _placeholder(value):
                candidate[key] = value

    for key in ("rating", "review_count", "buy_signal_score", "runs_ads"):
        value = prospect.get(key)
        if value not in (None, ""):
            candidate[key] = value
    return candidate


def build_conversation_recovery(
    intents: Iterable[Mapping[str, Any]],
    delivered_events: Mapping[str, datetime],
    prospects: Mapping[str, Mapping[str, Any]],
    *,
    now: datetime,
) -> dict[str, Any]:
    if now.tzinfo is None:
        raise ValueError("now must include timezone")
    current = now.astimezone(timezone.utc)
    rows: list[RecoveryRow] = []

    for intent in intents:
        if _text(intent.get("status")).lower() != "delivered":
            continue
        metadata = intent.get("metadata")
        metadata = metadata if isinstance(metadata, Mapping) else {}
        if _text(metadata.get("sequence_kind")).lower() == "followup":
            continue

        intent_id = _text(intent.get("id"))
        delivered = delivered_events.get(intent_id)
        if not intent_id or delivered is None:
            continue

        prospect_id = _text(intent.get("prospect_id"))
        candidate = _merge_context(
            intent,
            prospects.get(prospect_id) if prospect_id else None,
        )
        business = _text(candidate.get("business_name"))
        niche = _text(candidate.get("niche"))
        metro = _text(candidate.get("metro"))
        placeholder = any(
            _placeholder(value) for value in (business, niche, metro)
        )

        age_hours = max(
            0.0,
            (current - delivered.astimezone(timezone.utc)).total_seconds() / 3600,
        )
        hours_until = max(0.0, FOLLOWUP_ONE_HOURS - age_hours)
        due_now = age_hours >= FOLLOWUP_ONE_HOURS
        due_within = 0 < hours_until <= 24
        subject = _text(intent.get("subject"))
        generic = (
            "opportunities in" in subject.lower()
            or "local market opportunities" in subject.lower()
        )

        recoverable = False
        preview = None
        reason = "missing_canonical_context" if placeholder else "ready_when_due"
        if not placeholder:
            try:
                copy = build_followup_copy(
                    {
                        "root_subject": subject,
                        "candidate_evidence": candidate,
                    },
                    step=1,
                    now=current,
                )
                preview = copy.subject
                recoverable = True
                reason = "due_now" if due_now else "waiting_for_72h_cadence"
            except ValueError as exc:
                reason = f"copy_blocked:{str(exc)[:120]}"

        rows.append(
            RecoveryRow(
                root_intent_id=intent_id,
                recipient=_text(intent.get("recipient")),
                delivered_at=delivered.isoformat(),
                age_hours=round(age_hours, 2),
                hours_until_followup=round(hours_until, 2),
                due_now=due_now,
                due_within_24h=due_within,
                business_name=business or None,
                niche=niche or None,
                metro=metro or None,
                legacy_generic_subject=generic,
                placeholder_evidence=placeholder,
                recoverable=recoverable,
                recovery_reason=reason,
                followup_subject_preview=preview,
            )
        )

    rows.sort(key=lambda row: (-row.age_hours, row.root_intent_id))
    return {
        "schema_version": "empire.conversation_recovery.v1",
        "observed_at": current.isoformat(),
        "followup_one_hours": FOLLOWUP_ONE_HOURS,
        "followup_two_hours": FOLLOWUP_TWO_HOURS,
        "delivered_first_touches": len(rows),
        "due_now": sum(row.due_now for row in rows),
        "due_within_24h": sum(row.due_within_24h for row in rows),
        "recoverable": sum(row.recoverable for row in rows),
        "blocked_missing_context": sum(row.placeholder_evidence for row in rows),
        "legacy_generic_subjects": sum(row.legacy_generic_subject for row in rows),
        "next_due_in_hours": (
            min(
                (row.hours_until_followup for row in rows if not row.due_now),
                default=None,
            )
        ),
        "items": [row.as_dict() for row in rows],
        "send_executed": False,
        "proposal_created": False,
        "execution_authority": "none",
    }


def parse_delivered_events(
    rows: Iterable[Mapping[str, Any]],
) -> dict[str, datetime]:
    result: dict[str, datetime] = {}
    for row in rows:
        if _text(row.get("event_type")).lower() != "delivered":
            continue
        intent_id = _text(row.get("intent_id"))
        occurred = _parse_time(row.get("occurred_at"))
        if not intent_id or occurred is None:
            continue
        existing = result.get(intent_id)
        if existing is None or occurred > existing:
            result[intent_id] = occurred
    return result
