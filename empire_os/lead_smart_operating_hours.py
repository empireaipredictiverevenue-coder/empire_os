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

# These are reporting-only continental US clocks. Buyer confirmation of a
# caller-local rule is NOT a live buyer-capacity or caller-location signal.
CONTIGUOUS_US_ZONES = {
    "Eastern": "America/New_York",
    "Central": "America/Chicago",
    "Mountain": "America/Denver",
    "Pacific": "America/Los_Angeles",
}


def reported_local_clock_status(*, now: datetime | None = None) -> dict[str, Any]:
    """Compare historical reported hours across four contiguous US clocks.

    Diagnostic only. No origin timezone or downstream accepting buyer is
    identified, and Alaska/Hawaii/territory caller hours are not covered.
    """
    when = now or datetime.now(timezone.utc)
    if when.tzinfo is None:
        raise ValueError("timezone-aware current time required")
    when = when.astimezone(timezone.utc)
    clocks = []
    for region, zone_name in CONTIGUOUS_US_ZONES.items():
        local = when.astimezone(ZoneInfo(zone_name))
        start, end = (8, 18) if local.weekday() < 5 else (10, 16)
        minute = local.hour * 60 + local.minute
        clocks.append({
            "region": region,
            "timezone": zone_name,
            "local_time": local.isoformat(),
            "within_historical_reported_hours": start * 60 <= minute < end * 60,
        })
    return {
        "schema_version": "empire.lead_smart.reported_local_clock.v1",
        "source_ref": "gmail:1a15ea2dfa8c46b1",
        "policy": "CALLER_LOCAL_HOURS_REPORTED_NOT_VERIFIED_FOR_BUYER_CAPACITY",
        "checked_at": when.isoformat(),
        "contiguous_us_clocks": clocks,
        "all_four_within_historical_reported_hours": all(
            entry["within_historical_reported_hours"] for entry in clocks
        ),
        "caller_timezone_verified": False,
        "receiving_buyer_capacity_verified": False,
        "call_authorized": False,
    }


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
    superseding_buyer_policy: Mapping[str, Any] | None = None,
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
    # The 21 Oct buyer correction says hours depend on the caller's time
    # zone, NOT the old universal Chicago time. We have no authenticated
    # caller-zone or receiving-buyer window mapping. Any newer policy claim
    # holds the legacy policy; extra "verified" flags cannot self-clear it.
    supersession_review_required = superseding_buyer_policy is not None
    hours_policy_confirmed = (
        contract_matches and confirmation_valid
        and not supersession_review_required
    )
    verified = hours_policy_confirmed and within_window
    return {
        "schema_version": "empire.lead_smart.operating_hours_gate.v1",
        "reported_policy_matches": contract_matches,
        "timezone_interpretation_verified": confirmation_valid,
        "timezone_assumption": zone_name if not confirmation_valid else None,
        "buyer_zone_name": zone_name if confirmation_valid else None,
        "within_reported_window": within_window,
        "hours_policy_confirmed": hours_policy_confirmed,
        "supersession_review_required": supersession_review_required,
        "supersession_source_ref": (
            superseding_buyer_policy.get("source_ref")
            if isinstance(superseding_buyer_policy, Mapping)
            and superseding_buyer_policy.get("source_ref")
                == "gmail:1a15ea2dfa8c46b1"
            else None
        ),
        "buyer_window_open_now": within_window if hours_policy_confirmed else False,
        "evaluated_at": now.isoformat(),
        "operating_hours_verified": verified,
        "source_ref": (
            timezone_confirmation["source_ref"] if confirmation_valid else None
        ),
        "regional_clock_diagnostic": reported_local_clock_status(now=now),
        "call_authorized": False,
        "execution_authority": "NONE",
    }
