"""Bounded no-reply follow-up proposal worker.

This worker never sends email. It only asks the database for follow-ups that are
already due under the governed sequence contract and proposes deterministic
copy. Approval and send remain separate outbound-governor steps.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping

from empire_os.conversation_value import (
    POSTAL_ADDRESS,
    build_followup_copy as build_value_followup_copy,
)
from empire_os.geo_registry import acquisition_markets
from empire_os.locale_intelligence import (
    contact_window_status,
    resolve_locale,
)

@dataclass(frozen=True)
class FollowupWorkerResult:
    due_seen: int
    proposed: int
    deferred_outside_window: bool
    local_window_deferred: int
    locale_blocked: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "due_seen": self.due_seen,
            "proposed": self.proposed,
            "deferred_outside_window": self.deferred_outside_window,
            "local_window_deferred": self.local_window_deferred,
            "locale_blocked": self.locale_blocked,
            "errors": list(self.errors),
            "actual_revenue": False,
            "send_executed": False,
            "payment_mutation": False,
        }


Request = Callable[..., Any]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _city(value: Any) -> str:
    return _text(value).split(",", 1)[0].strip().casefold()


def _registry_locale_for_metro(metro: str):
    city = _city(metro)
    if not city:
        return None
    matches = [
        market
        for market in acquisition_markets()
        if _city(market.metro) == city
    ]
    if len(matches) != 1:
        return None
    market = matches[0]
    return resolve_locale({
        "country_code": market.country_code,
        "state": market.region_code,
        "metro": market.metro,
        "timezone": market.timezone,
        "source_language": market.language_code,
    })


def followup_locale(row: Mapping[str, Any]):
    explicit = row.get("recipient_locale")
    locale_input = dict(explicit) if isinstance(explicit, Mapping) else {}
    evidence = row.get("candidate_evidence")
    evidence = evidence if isinstance(evidence, Mapping) else {}

    embedded = evidence.get("locale")
    if isinstance(embedded, Mapping):
        for key, value in embedded.items():
            locale_input.setdefault(key, value)

    for key in (
        "metro", "state", "country_code", "country",
        "timezone", "source_language", "language_code",
    ):
        value = evidence.get(key)
        if value not in (None, ""):
            locale_input.setdefault(key, value)

    locale = resolve_locale(locale_input)
    if locale.timezone:
        return locale

    metro = str(evidence.get("metro") or "").strip()
    registry = _registry_locale_for_metro(metro)
    return registry or locale


def followup_contact_eligibility(
    row: Mapping[str, Any],
    *,
    now: datetime,
    start_hour: int = 8,
    end_hour: int = 18,
) -> dict[str, Any]:
    locale = followup_locale(row)
    language = str(locale.outreach_language or "").strip()

    if not language:
        return {
            "eligible": False,
            "reason": "recipient_outreach_language_unresolved",
            "locale": locale.as_dict(),
            "timing": None,
        }

    # Follow-up copy is currently English. Global acquisition may continue,
    # but non-English outbound fails closed until localized copy is shipped.
    if not language.lower().startswith("en"):
        return {
            "eligible": False,
            "reason": f"localized_followup_copy_unavailable:{language}",
            "locale": locale.as_dict(),
            "timing": None,
        }

    timing = contact_window_status(
        locale,
        now=now,
        start_hour=start_hour,
        end_hour=end_hour,
    )
    return {
        "eligible": timing["eligible"] is True,
        "reason": timing["reason"],
        "locale": locale.as_dict(),
        "timing": timing,
    }


def build_followup_copy(
    row: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> tuple[str, str]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must include timezone")
    step = int(row.get("followup_step") or 0)
    copy = build_value_followup_copy(
        row,
        step=step,
        now=current,
    )
    return copy.subject, copy.body


def within_send_window(
    now: datetime,
    *,
    start_hour_utc: int = 14,
    end_hour_utc: int = 21,
) -> bool:
    current = now.astimezone(timezone.utc)
    if current.weekday() >= 5:
        return False
    return start_hour_utc <= current.hour <= end_hour_utc


def run_followup_worker(
    request: Request,
    *,
    limit: int = 25,
    now: datetime | None = None,
    start_hour_local: int = 8,
    end_hour_local: int = 18,
    # Deprecated compatibility arguments: local recipient windows now govern.
    start_hour_utc: int | None = None,
    end_hour_utc: int | None = None,
) -> FollowupWorkerResult:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    bounded = max(1, min(int(limit), 100))

    rows = request(
        "POST",
        "/rest/v1/rpc/list_due_outbound_followups",
        payload={"p_limit": bounded},
    ) or []
    if not isinstance(rows, list):
        raise ValueError("due follow-up projection must be a list")

    proposed = 0
    local_window_deferred = 0
    locale_blocked = 0
    errors: list[str] = []

    for row in rows:
        if not isinstance(row, Mapping):
            continue
        root_id = _text(row.get("root_intent_id"))
        try:
            eligibility = followup_contact_eligibility(
                row,
                now=current,
                start_hour=start_hour_local,
                end_hour=end_hour_local,
            )
            if eligibility["eligible"] is not True:
                reason = str(eligibility.get("reason") or "")
                if reason in {
                    "recipient_timezone_unresolved",
                    "recipient_timezone_invalid",
                    "recipient_outreach_language_unresolved",
                } or reason.startswith("localized_followup_copy_unavailable:"):
                    locale_blocked += 1
                else:
                    local_window_deferred += 1
                continue

            step = int(row.get("followup_step") or 0)
            subject, body = build_followup_copy(row, now=current)
            result = request(
                "POST",
                "/rest/v1/rpc/propose_outbound_followup",
                payload={
                    "p_root_intent_id": root_id,
                    "p_step": step,
                    "p_subject": subject,
                    "p_body_text": body,
                    "p_idempotency_key": f"followup:{root_id}:step:{step}:v2-local",
                    "p_proposed_by": "empire_followup_worker_v2_local",
                    "p_expires_at": (
                        current + timedelta(hours=18)
                    ).isoformat(),
                },
            )
            if isinstance(result, Mapping) and result.get("intent_id"):
                proposed += 1
            else:
                errors.append(f"{root_id}:proposal_returned_no_intent")
        except Exception as exc:
            errors.append(
                f"{root_id or 'unknown'}:{type(exc).__name__}:{str(exc)[:180]}"
            )

    return FollowupWorkerResult(
        due_seen=len(rows),
        proposed=proposed,
        deferred_outside_window=local_window_deferred > 0,
        local_window_deferred=local_window_deferred,
        locale_blocked=locale_blocked,
        errors=tuple(errors),
    )
