"""Lead Smart caller-local clock diagnostics only; never a call admission grant."""
from datetime import datetime, timezone

import pytest

from empire_os.lead_smart_operating_hours import (
    REPORT, evaluate_buyer_hours, reported_local_clock_status,
)


def t(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def test_monday_morning_regional_clocks_do_not_claim_nationwide_open():
    result = reported_local_clock_status(now=t("2026-10-26T13:35:00Z"))
    clocks = {r["region"]: r for r in result["contiguous_us_clocks"]}
    assert {name: value["within_historical_reported_hours"] for name, value in clocks.items()} == {
        "Eastern": True, "Central": True, "Mountain": False, "Pacific": False,
    }
    assert result["all_four_within_historical_reported_hours"] is False
    assert result["caller_timezone_verified"] is False
    assert result["receiving_buyer_capacity_verified"] is False
    assert result["call_authorized"] is False


@pytest.mark.parametrize("utc,overlap", [
    ("2026-10-26T14:59:00Z", False),
    ("2026-10-26T15:00:00Z", True),
    ("2026-10-26T21:59:00Z", True),
    ("2026-10-26T22:00:00Z", False),
    ("2026-01-12T15:59:00Z", False),
    ("2026-01-12T16:00:00Z", True),
    ("2026-01-12T23:00:00Z", False),
])
def test_weekday_reported_local_clock_overlap_handles_daylight_saving(utc, overlap):
    result = reported_local_clock_status(now=t(utc))
    assert result["all_four_within_historical_reported_hours"] is overlap
    assert result["call_authorized"] is False


def test_superseding_caller_local_buyer_policy_remains_held():
    now = t("2026-10-26T15:30:00Z")
    hours = evaluate_buyer_hours(
        REPORT,
        {"buyer_confirmed": True, "zone_name": "America/Chicago",
         "source_ref": "gmail:1a12229d9d3ffe75",
         "confirmed_at": "2026-10-09T19:35:28Z"},
        now=now,
        superseding_buyer_policy={"source_ref": "gmail:1a15ea2dfa8c46b1"},
    )
    assert hours["regional_clock_diagnostic"]["all_four_within_historical_reported_hours"] is True
    assert hours["operating_hours_verified"] is False
    assert hours["buyer_window_open_now"] is False
    assert hours["call_authorized"] is False


@pytest.mark.parametrize("utc,open_now", [
    ("2026-10-26T17:59:59Z", False),
    ("2026-10-26T18:00:00Z", True),
    ("2026-10-26T21:59:59Z", True),
    ("2026-10-26T22:00:00Z", False),
    ("2026-11-02T17:59:59Z", False),
    ("2026-11-02T18:00:00Z", True),
    ("2026-11-02T22:59:59Z", True),
    ("2026-11-02T23:00:00Z", False),
    ("2026-10-31T20:00:00Z", False),
])
def test_fifty_state_hours_only_in_full_reported_intersection(utc, open_now):
    from empire_os.lead_smart_operating_hours import fifty_state_hours_overlap
    result = fifty_state_hours_overlap(now=t(utc))
    assert len(result["zones"]) == 8
    assert result["all_reported_windows_open"] is open_now
    assert result["call_authorized"] is False


def test_source_bound_conservative_reconciliation_not_a_route_or_recording_grant():
    from empire_os.lead_smart_operating_hours import evaluate_buyer_hours
    now = t("2026-10-26T18:05:00Z")
    confirmation = {
        "buyer_confirmed": True,
        "zone_name": "America/Chicago",
        "source_ref": "gmail:1a12229d9d3ffe75",
        "confirmed_at": "2026-10-09T19:35:28Z",
    }
    valid = evaluate_buyer_hours(
        REPORT, confirmation, now=now,
        superseding_buyer_policy={"source_ref": "gmail:1a15ea2dfa8c46b1"},
    )
    assert valid["operating_hours_verified"] is True
    assert valid["caller_local_overlap_reconciled"] is True
    assert valid["buyer_window_open_now"] is True
    assert valid["receiving_buyer_capacity_verified"] is False
    assert valid["call_authorized"] is False
    wrong_source = evaluate_buyer_hours(
        REPORT, confirmation, now=now,
        superseding_buyer_policy={"source_ref": "claim:not-verified"},
    )
    assert wrong_source["operating_hours_verified"] is False
    wrong_contract = evaluate_buyer_hours(
        {**REPORT, "monday_friday": "00:00-23:59"}, confirmation, now=now,
        superseding_buyer_policy={"source_ref": "gmail:1a15ea2dfa8c46b1"},
    )
    assert wrong_contract["operating_hours_verified"] is False


def test_naive_timestamp_cannot_be_assumed_utc():
    with pytest.raises(ValueError):
        reported_local_clock_status(now=datetime(2026, 10, 26, 15))
