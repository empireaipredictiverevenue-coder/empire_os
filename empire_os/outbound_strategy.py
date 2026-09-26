"""Evidence-led contact channel planning for governed outbound.

Pure planning only: no writes, sends, scraping, or account actions.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from empire_os.phone_quality import normalized_e164


def _text(value: Any) -> str:
    return str(value or "").strip()


def _e164(value: Any) -> str:
    return normalized_e164(value)


def build_contact_channel_plan(
    contact_plan: Mapping[str, Any],
    *,
    channel_evidence: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Rank only evidence-backed channels; keep company phone separate from person-bound paths."""
    direct: list[dict[str, Any]] = []
    company: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    email = _text(contact_plan.get("preferred_email")).lower()
    if contact_plan.get("outreach_ready") and email:
        direct.append({"channel": "email", "recipient": email, "evidence": "verified_person_email"})

    for raw in channel_evidence or ():
        item = dict(raw)
        channel = _text(item.get("channel")).lower()
        value = _text(item.get("value"))
        verified = bool(item.get("verified"))
        person_bound = bool(item.get("person_bound"))
        source = _text(item.get("source")) or "unknown"
        if channel not in {"sms", "voice", "a2a"} or not verified or not value:
            blocked.append({"channel": channel or "unknown", "reason": "unverified_or_unsupported"})
            continue
        if channel in {"sms", "voice"}:
            value = _e164(value)
            if not value:
                blocked.append({"channel": channel, "reason": "valid_e164_required"})
                continue
        record = {"channel": channel, "recipient": value, "evidence": source}
        if person_bound:
            direct.append(record)
        elif channel == "voice":
            record["scope"] = "company"
            company.append(record)
        else:
            blocked.append({"channel": channel, "reason": "person_binding_required"})

    order = {"email": 0, "sms": 1, "voice": 2, "a2a": 3}
    direct.sort(key=lambda x: order[x["channel"]])
    return {
        "mode": "OBSERVE",
        "write_authorized": False,
        "primary": direct[0] if direct else None,
        "fallbacks": direct[1:],
        "company_fallbacks": company,
        "blocked": blocked,
    }
