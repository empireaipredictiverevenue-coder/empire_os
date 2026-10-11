"""Buyer-hours launch gate for Lead Smart roofing.

A reported 'CST' clock is ambiguous during US daylight-saving time. Until a
buyer-confirmed interpretation is supplied, never grant call authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping
from zoneinfo import ZoneInfo

REPORT = {
    "timezone": "CST",
    "monday_friday": "08:00-18:00",
    "saturday_sunday": "10:00-16:00",
}
# The buyer confirmed America/Chicago on 9 October, with US daylight saving.
# A fixed UTC-6 offset is NOT equivalent to that rule during US summer.
ALLOWED_ZONES = {"America/Chicago"}
MAX_CONFIRMATION_AGE_SECONDS = 30 * 86400


def _confirmed(evidence: Mapping[str, Any] | None, now: datetime) -> bool:
    if not isinstance(evidence, Mapping):
        return False
    if evidence.get("buyer_confirmed") is not True:
        return False
    zone_name = evidence.get("zone_name")
    if not isinstance(zone_name, str) or zone_name not in ALLOWED_ZONES:
        return False
    ref = evidence.get("source_ref")
    if not isinstance(ref, str) or not ref.startswith("gmail:") or len(ref) <= 6:
        return False
    observed_at = evidence.get("confirmed_at")
    if not isinstance(observed_at, str):
        return False
    try:
        observed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if observed.tzinfo is None:
        return False
    age = (now - observed.astimezone(timezone.utc)).total_seconds()
    return 0 <= age <= MAX_CONFIRMATION_AGE_SECONDS


def evaluate_buyer_hours(
    policy: Mapping[str, Any] | None,
    timezone_confirmation: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("timezone-aware current time required")
    now = now.astimezone(timezone.utc)
    contract_matches = isinstance(policy, Mapping) and dict(policy) == REPORT
    confirmation_valid = _confirmed(timezone_confirmation, now)
    zone_name = (
        timezone_confirmation["zone_name"]
        if confirmation_valid else "America/Chicago"
    )
    local = now.astimezone(ZoneInfo(zone_name))
    start_hour, end_hour = (8, 18) if local.weekday() < 5 else (10, 16)
    minute_of_day = 60 * local.hour + local.minute
    within_window = start_hour * 60 <= minute_of_day < end_hour * 60
    # Confirmed hours POLICY is independent of whether the clock is inside
    # this particular operating window. Caller routing remains fail-closed.
    hours_policy_confirmed = contract_matches and confirmation_valid
    verified = hours_policy_confirmed and within_window
    return {
        "schema_version": "empire.lead_smart.operating_hours_gate.v1",
        "reported_policy_matches": contract_matches,
        "timezone_interpretation_verified": confirmation_valid,
        "timezone_assumption": zone_name if not confirmation_valid else None,
        "buyer_zone_name": zone_name if confirmation_valid else None,
        "within_reported_window": within_window,
        "hours_policy_confirmed": hours_policy_confirmed,
        "buyer_window_open_now": within_window if hours_policy_confirmed else False,
        "evaluated_at": now.isoformat(),
        "operating_hours_verified": verified,
        "source_ref": (
            timezone_confirmation["source_ref"] if confirmation_valid else None
        ),
        "call_authorized": False,
        "execution_authority": "NONE",
    }
