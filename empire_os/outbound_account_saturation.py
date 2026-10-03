"""Cross-agent account and corridor saturation policy for outbound outreach.

This protects prospects and sender reputation when multiple Empire agents/campaigns target
the same company, corporate group, or commercial corridor. Existing conversations take
precedence over new cold touches.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping


def _parse_ts(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def evaluate_account_saturation(
    candidate: Mapping[str, Any],
    history: Iterable[Mapping[str, Any]],
    *,
    now: datetime | None = None,
    company_window_days: int = 30,
    company_cap: int = 4,
    parent_window_days: int = 30,
    parent_cap: int = 8,
    corridor_window_days: int = 7,
    corridor_cap: int = 20,
) -> dict[str, Any]:
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    company_key = str(candidate.get("company_key") or "").strip()
    parent_key = str(candidate.get("parent_company_key") or "").strip()
    corridor_key = str(candidate.get("corridor_key") or "").strip()

    if not company_key:
        return {
            "decision": "ESCALATE",
            "reason": "company_identity_missing",
            "counts": {},
            "mutation_authorized": False,
        }

    company_cutoff = timestamp - timedelta(days=max(1, company_window_days))
    parent_cutoff = timestamp - timedelta(days=max(1, parent_window_days))
    corridor_cutoff = timestamp - timedelta(days=max(1, corridor_window_days))

    company_contacts = 0
    parent_contacts = 0
    corridor_contacts = 0
    open_conversation = False
    latest_conversation_at: datetime | None = None

    for raw in history:
        row = dict(raw)
        occurred = _parse_ts(row.get("occurred_at"))
        if occurred is None or occurred > timestamp:
            continue

        event_kind = str(row.get("event_kind") or row.get("kind") or "").lower()
        is_contact = event_kind in {
            "sent",
            "outbound_touch",
            "followup_sent",
            "call_attempt",
        }
        is_conversation = event_kind in {
            "reply_received",
            "positive_reply",
            "negative_reply",
            "meeting_booked",
            "conversation_open",
        }

        row_company = str(row.get("company_key") or "").strip()
        row_parent = str(row.get("parent_company_key") or "").strip()
        row_corridor = str(row.get("corridor_key") or "").strip()

        if is_conversation and row_company == company_key:
            open_conversation = True
            if latest_conversation_at is None or occurred > latest_conversation_at:
                latest_conversation_at = occurred

        if not is_contact:
            continue

        if row_company == company_key and occurred >= company_cutoff:
            company_contacts += max(1, int(row.get("count") or 1))
        if parent_key and row_parent == parent_key and occurred >= parent_cutoff:
            parent_contacts += max(1, int(row.get("count") or 1))
        if corridor_key and row_corridor == corridor_key and occurred >= corridor_cutoff:
            corridor_contacts += max(1, int(row.get("count") or 1))

    counts = {
        "company_contacts": company_contacts,
        "parent_contacts": parent_contacts,
        "corridor_contacts": corridor_contacts,
    }

    if open_conversation:
        decision = "HOLD_NEW_OUTREACH"
        reason = "existing_company_conversation_takes_precedence"
    elif company_contacts >= max(1, company_cap):
        decision = "HOLD_NEW_OUTREACH"
        reason = "company_saturation_limit_reached"
    elif parent_key and parent_contacts >= max(1, parent_cap):
        decision = "HOLD_NEW_OUTREACH"
        reason = "parent_group_saturation_limit_reached"
    elif corridor_key and corridor_contacts >= max(1, corridor_cap):
        decision = "THROTTLE_CORRIDOR"
        reason = "corridor_saturation_limit_reached"
    else:
        decision = "READY"
        reason = "account_pressure_clear"

    return {
        "decision": decision,
        "reason": reason,
        "company_key": company_key,
        "parent_company_key": parent_key or None,
        "corridor_key": corridor_key or None,
        "counts": counts,
        "limits": {
            "company_cap": max(1, company_cap),
            "parent_cap": max(1, parent_cap),
            "corridor_cap": max(1, corridor_cap),
        },
        "open_conversation": open_conversation,
        "latest_conversation_at": (
            latest_conversation_at.isoformat()
            if latest_conversation_at is not None
            else None
        ),
        "mutation_authorized": False,
        "send_authorized": False,
    }
