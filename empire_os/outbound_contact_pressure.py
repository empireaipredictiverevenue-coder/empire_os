"""Global contact-pressure policy across all Empire outbound agents and campaigns."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping


def _parse(value: Any) -> datetime | None:
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


def evaluate_contact_pressure(
    candidate: Mapping[str, Any],
    history: Iterable[Mapping[str, Any]],
    *,
    now: datetime | None = None,
    person_cooldown_days: int = 14,
    company_daily_cap: int = 2,
) -> dict[str, Any]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    person = str(candidate.get("person_key") or "").strip().lower()
    company = str(candidate.get("company_key") or "").strip().lower()

    if not person or not company:
        return {
            "decision": "ESCALATE",
            "reason": "identity_keys_missing",
            "mutation_authorized": False,
        }

    person_cutoff = now - timedelta(days=person_cooldown_days)
    company_day = now.date()
    recent_person = 0
    company_today = 0

    for raw in history:
        row = dict(raw)
        occurred = _parse(row.get("occurred_at"))
        if occurred is None:
            continue
        if str(row.get("person_key") or "").strip().lower() == person and occurred >= person_cutoff:
            recent_person += 1
        if (
            str(row.get("company_key") or "").strip().lower() == company
            and occurred.date() == company_day
        ):
            company_today += 1

    if recent_person:
        decision = "HOLD"
        reason = "person_contact_cooldown_active"
    elif company_today >= company_daily_cap:
        decision = "HOLD"
        reason = "company_contact_pressure_limit"
    else:
        decision = "READY"
        reason = "contact_pressure_clear"

    return {
        "decision": decision,
        "reason": reason,
        "person_contacts_in_cooldown": recent_person,
        "company_contacts_today": company_today,
        "mutation_authorized": False,
    }
