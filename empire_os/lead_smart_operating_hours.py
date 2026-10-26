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

# Cover the earliest and latest local clocks in all 50 US states, including
# non-DST Arizona, Alaska's western Aleutian Islands, and Hawaii. This is
# intentionally stricter than a Chicago or lower-48 opening-hours shortcut.
# These represent timezones, NOT a geolocation claim for any individual.
FIFTY_STATE_HOURS_ZONES = {
    **CONTIGUOUS_US_ZONES,
    "Arizona": "America/Phoenix",
    "Alaska": "America/Anchorage",
    "Western Aleutians": "America/Adak",
    "Hawaii": "Pacific/Honolulu",
}


def fifty_state_hours_overlap(*, now: datetime) -> dict[str, Any]:
    """Conservative 50-state intersection of buyer-reported local windows.

    The two buyer emails establish reported hours and caller-local semantics.
    This does not show that a particular receiving buyer is accepting calls,
    certify recording compliance, or enable consumer call admission.
    """
    if now.tzinfo is None:
        raise ValueError("timezone-aware current time required")
    utc = now.astimezone(timezone.utc)
    details = []
    for region, zone_name in FIFTY_STATE_HOURS_ZONES.items():
        local = utc.astimezone(ZoneInfo(zone_name))
        start, end = (8, 18) if local.weekday() < 5 else (10, 16)
        minute = local.hour * 60 + local.minute
        details.append({
            "region": region,
            "zone": zone_name,
            "local_time": local.isoformat(),
            "within_reported_hours": start * 60 <= minute < end * 60,
        })
    return {
        "schema_version": "empire.lead_smart.fifty_state_hours_overlap.v1",
        "source_refs": ["gmail:1a12229d9d3ffe75", "gmail:1a15ea2dfa8c46b1"],
        "scope": "50_US_STATES_ONLY_NOT_TERRITORIES",
        "all_reported_windows_open": all(item["within_reported_hours"] for item in details),
        "observed_at": utc.isoformat(),
        "zones": details,
        "live_buyer_capacity_verified": False,
        "specific_caller_zone_verified": False,
        "call_authorized": False,
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
    # Merge BOTH source-bound buyer statements: 9 October reported 8-18 / 10-16
    # local hours, then 21 October superseded the *universal Chicago zone* with
    # caller-local semantics. During the clock intersection of all 50 states,
    # no individual caller timezone is needed to evaluate these hours. Outside
    # it we cannot infer origin from a project ZIP and remain fail-closed.
    supersession_review_required = superseding_buyer_policy is not None
    caller_local_source_confirmed = (
        isinstance(superseding_buyer_policy, Mapping)
        and superseding_buyer_policy.get("source_ref") == "gmail:1a15ea2dfa8c46b1"
    )
    fifty_state = fifty_state_hours_overlap(now=now)
    conservative_reconciliation = (
        contract_matches and confirmation_valid and caller_local_source_confirmed
        and fifty_state["all_reported_windows_open"]
    )
    hours_policy_confirmed = contract_matches and confirmation_valid and (
        not supersession_review_required or conservative_reconciliation
    )
    verified = hours_policy_confirmed and (
        fifty_state["all_reported_windows_open"]
        if supersession_review_required else within_window
    )
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
        "buyer_window_open_now": verified,
        "caller_local_overlap_reconciled": conservative_reconciliation,
        "fifty_state_hour_overlap": fifty_state,
        "receiving_buyer_capacity_verified": False,
        "evaluated_at": now.isoformat(),
        "operating_hours_verified": verified,
        "source_ref": (
            timezone_confirmation["source_ref"] if confirmation_valid else None
        ),
        "regional_clock_diagnostic": reported_local_clock_status(now=now),
        "call_authorized": False,
        "execution_authority": "NONE",
    }
