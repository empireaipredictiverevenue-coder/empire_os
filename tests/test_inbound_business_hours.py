from datetime import datetime, timezone

import pytest

from empire_os.inbound_business_hours import (
    BusinessHoursPolicy, StaffedWindow, plan_hours_aware_reception_response,
    staffed_hours_status,
)
from empire_os.inbound_revenue_recovery import TenantReceptionProfile


def policy(*, verified=True, closed_dates=()):
    return BusinessHoursPolicy(
        tenant_id="plumber-1",
        timezone_name="Europe/London",
        windows=tuple(StaffedWindow(d, "09:00", "17:30") for d in range(5)),
        closed_dates=closed_dates,
        verified=verified,
    )


def at(utc_iso):
    return datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))


def profile():
    return TenantReceptionProfile(
        tenant_id="plumber-1", business_name="Acme Plumbing",
        human_transfer_configured=True,
    )


def test_uk_staffed_hours_respect_timezone():
    status = staffed_hours_status(policy(), at("2026-10-20T09:00:00Z"))
    assert status.verified
    assert status.open_now
    assert status.reason == "within_verified_hours"
    assert status.next_open_at.startswith("2026-10-21T09:00:00+01:00")


def test_before_open_next_open_and_after_close():
    before = staffed_hours_status(policy(), at("2026-10-20T06:00:00Z"))
    assert before.open_now is False
    assert before.next_open_at.startswith("2026-10-20T09:00:00+01:00")
    after = staffed_hours_status(policy(), at("2026-10-20T19:00:00Z"))
    assert after.open_now is False
    assert after.next_open_at.startswith("2026-10-21T09:00:00+01:00")


def test_holidays_override_weekly_openings():
    status = staffed_hours_status(
        policy(closed_dates=("2026-10-20",)),
        at("2026-10-20T11:00:00Z"),
    )
    assert status.open_now is False
    assert status.next_open_at.startswith("2026-10-21T09:00:00+01:00")


def test_friday_evening_next_open_skips_weekend():
    state = staffed_hours_status(policy(), at("2026-10-23T21:00:00Z"))
    assert state.open_now is False
    assert state.next_open_at.startswith("2026-10-26T09:00:00+00:00")


def test_unverified_hours_must_remain_unknown():
    status = staffed_hours_status(policy(verified=False), at("2026-10-20T10:00:00Z"))
    assert status.open_now is None
    assert status.next_open_at is None
    assert status.reason == "hours_not_verified"


def test_after_hours_human_request_cannot_claim_connected_transfer():
    decision = plan_hours_aware_reception_response(
        profile(), policy(), at("2026-10-20T21:00:00Z"), "human"
    )
    assert decision.action == "request_human_followup"
    assert not decision.booking_confirmed
    assert not decision.outbound_authorized
    assert "cannot confirm" in decision.spoken_text


def test_unknown_hours_cannot_claim_human_is_available():
    decision = plan_hours_aware_reception_response(
        profile(), policy(verified=False), at("2026-10-20T11:00:00Z"), "complaint"
    )
    assert decision.action == "request_human_followup"


def test_open_hours_can_offer_not_guarantee_transfer():
    decision = plan_hours_aware_reception_response(
        profile(), policy(), at("2026-10-20T11:00:00Z"), "human"
    )
    assert decision.action == "offer_human_transfer"
    assert "can try" in decision.spoken_text
    assert not decision.outbound_authorized


def test_opt_out_and_emergency_take_priority_over_hours():
    for intent, expected in [("stop", "honour_opt_out"), ("emergency", "urgent_human_escalation")]:
        result = plan_hours_aware_reception_response(
            profile(), policy(), at("2026-10-20T21:00:00Z"), intent
        )
        assert result.action == expected


def test_policy_cannot_be_cross_tenant():
    other = BusinessHoursPolicy(
        tenant_id="different-tenant", timezone_name="Europe/London",
        verified=True,
    )
    with pytest.raises(ValueError, match="tenant_mismatch"):
        plan_hours_aware_reception_response(profile(), other, at("2026-10-20T12:00:00Z"), "human")


@pytest.mark.parametrize("weekday,opening,closing", [
    (9, "09:00", "17:00"), (1, "17:00", "09:00"), (1, "99:00", "17:00"),
])
def test_invalid_hours_rejected(weekday, opening, closing):
    with pytest.raises(ValueError):
        StaffedWindow(weekday, opening, closing)


def test_overlapping_windows_rejected():
    with pytest.raises(ValueError, match="overlapping"):
        BusinessHoursPolicy(
            "tenant", "Europe/London",
            (StaffedWindow(0, "09:00", "13:00"), StaffedWindow(0, "12:30", "17:00")),
        )


def test_bad_timezone_or_naive_time_rejected():
    with pytest.raises(ValueError, match="timezone"):
        BusinessHoursPolicy("tenant", "unknown/nowhere")
    with pytest.raises(ValueError, match="aware_datetime"):
        staffed_hours_status(policy(), datetime(2026, 10, 20, 12, 0))
