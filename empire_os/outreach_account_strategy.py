"""Account-level strategy helpers for governed Outreach Intelligence.

Pure analysis only. No contact, provider or CRM mutation authority.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping


ROLE_PRIORITY = {
    "economic_buyer": 0,
    "functional_buyer": 1,
    "influencer": 2,
    "champion": 2,
    "other": 3,
    "unknown": 4,
}

INTRO_KINDS = {
    "customer_referral",
    "partner_intro",
    "affiliate_intro",
    "advisor_intro",
    "a2a_intro",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


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


def build_buying_committee(
    people: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Rank only explicitly observed people; never invent contacts or roles."""
    members: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in people or ():
        person_id = _text(raw.get("person_id"))
        name = _text(raw.get("name"))
        title = _text(raw.get("title"))
        role = _text(raw.get("decision_role")).lower() or "unknown"
        evidence_ref = _text(raw.get("evidence_ref"))
        if not person_id or not name or not evidence_ref:
            continue
        if person_id in seen:
            continue
        seen.add(person_id)
        members.append({
            "person_id": person_id,
            "name": name,
            "title": title or None,
            "decision_role": role if role in ROLE_PRIORITY else "unknown",
            "contact_verified": raw.get("contact_verified") is True,
            "evidence_ref": evidence_ref,
        })
    members.sort(
        key=lambda row: (
            ROLE_PRIORITY.get(row["decision_role"], 99),
            not row["contact_verified"],
            row["name"].lower(),
        )
    )
    return {
        "members": members,
        "primary": members[0] if members else None,
        "multi_thread_candidate": len(members) >= 2,
        "observed_member_count": len(members),
        "invented_members": 0,
    }


def choose_introduction_path(
    paths: Iterable[Mapping[str, Any]],
) -> dict[str, Any] | None:
    """Prefer verified warm paths with evidence; never infer relationships."""
    candidates: list[dict[str, Any]] = []
    for raw in paths or ():
        kind = _text(raw.get("kind")).lower()
        referrer = _text(raw.get("referrer"))
        evidence_ref = _text(raw.get("evidence_ref"))
        if (
            kind not in INTRO_KINDS
            or raw.get("verified") is not True
            or not referrer
            or not evidence_ref
        ):
            continue
        candidates.append({
            "kind": kind,
            "referrer": referrer,
            "evidence_ref": evidence_ref,
            "relationship_strength": _text(raw.get("relationship_strength")) or None,
            "execution_authority": "none",
        })
    if not candidates:
        return None
    strength = {"strong": 0, "medium": 1, "weak": 2, None: 3}
    candidates.sort(
        key=lambda row: (
            strength.get(row["relationship_strength"], 3),
            row["kind"],
            row["referrer"].lower(),
        )
    )
    return candidates[0]


def evaluate_contact_fatigue(
    touches: Iterable[Mapping[str, Any]],
    *,
    now: datetime | None = None,
    max_touches_30d: int = 4,
    min_cooldown_hours: int = 72,
) -> dict[str, Any]:
    """Review recent observed contact events and fail closed on excessive cadence."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = now - timedelta(days=30)
    valid: list[datetime] = []
    invalid_or_future = 0

    for raw in touches or ():
        occurred = _parse_time(raw.get("occurred_at"))
        if occurred is None or occurred > now:
            invalid_or_future += 1
            continue
        if occurred >= cutoff:
            valid.append(occurred)

    valid.sort(reverse=True)
    last_touch = valid[0] if valid else None
    age_hours = (
        (now - last_touch).total_seconds() / 3600
        if last_touch is not None
        else None
    )

    blockers: list[str] = []
    if len(valid) >= max_touches_30d:
        blockers.append("max_30d_touch_count_reached")
    if age_hours is not None and age_hours < min_cooldown_hours:
        blockers.append("contact_cooldown_active")
    if invalid_or_future:
        blockers.append("invalid_or_future_touch_evidence")

    return {
        "touches_last_30d": len(valid),
        "last_touch_at": last_touch.isoformat() if last_touch else None,
        "hours_since_last_touch": round(age_hours, 2) if age_hours is not None else None,
        "max_touches_30d": max_touches_30d,
        "min_cooldown_hours": min_cooldown_hours,
        "blocked": bool(blockers),
        "blockers": blockers,
        "execution_authority": "none",
    }
