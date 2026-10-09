from datetime import datetime, timedelta, timezone

import pytest

from empire_os.lead_smart_launch_readiness import build_launch_readiness
from empire_os.lead_smart_operating_hours import REPORT, evaluate_buyer_hours

NOW = datetime(2026, 10, 9, 16, 5, tzinfo=timezone.utc)


def tracking():
    return {
        "state": "VERIFIED",
        "tracking_verified": True,
        "verified_at": NOW.isoformat(),
        "source_observed_at": NOW.isoformat(),
    }


def zip_gate():
    return {
        "zip_targeting_gate_verified": True,
        "zip_coverage_activation_verified": True,
        "source_fresh_for_targeting": True,
        "source_observed_at": NOW.isoformat(),
        "verified_freshness": {
            "source_newest_last_updated": NOW.isoformat(),
        },
    }


def routing(value=False):
    return {
        "routing_runtime_verified": value,
        "observed_at": NOW.isoformat(),
    }


def timezone_confirmation(now=NOW, zone="America/Chicago"):
    return {
        "buyer_confirmed": True,
        "source_ref": "gmail:buyer-timezone-confirmation",
        "zone_name": zone,
        "confirmed_at": now.isoformat(),
    }


def readiness(*, track=None, zip_state=None, route=None, authority=False, publication=False, now=NOW, tz=None, operating_hours=None):
    return build_launch_readiness(
        tracking=tracking() if track is None else track,
        zip_gate=zip_gate() if zip_state is None else zip_state,
        routing=routing() if route is None else route,
        operating_hours=REPORT if operating_hours is None else operating_hours,
        timezone_confirmation=tz,
        landing_publication_authorized=publication,
        founder_live_traffic_authorized=authority,
        now=now,
    )


def test_present_state_is_not_launch_ready():
    result = readiness()
    assert result["gates"]["tracking_verified"] is True
    assert result["gates"]["zip_targeting_verified"] is True
    assert result["gates"]["routing_runtime_verified"] is False
    assert result["launch_ready"] is False
    assert result["call_cta_enabled"] is False
    assert result["organic_traffic_authorized"] is False
    assert result["execution_authority"] == "NONE"


def test_routing_alone_cannot_activate_campaign():
    result = readiness(route=routing(True))
    assert result["launch_ready"] is False
    assert "landing_publication_authorized" in result["blockers"]
    assert "founder_live_traffic_authorized" in result["blockers"]


def test_founder_authority_alone_cannot_bypass_routing():
    result = readiness(authority=True, publication=True)
    assert result["launch_ready"] is False
    assert "routing_runtime_verified" in result["blockers"]


def test_all_independent_fresh_gates_required():
    result = readiness(route=routing(True), authority=True, publication=True,
                       tz=timezone_confirmation())
    assert result["blockers"] == []
    assert result["launch_ready"] is True
    assert result["call_cta_enabled"] is True
    assert result["organic_traffic_authorized"] is True
    assert result["provider_route_mutation"] is False
    assert result["execution_authority"] == "LIVE_TRAFFIC"


def test_stale_tracking_cannot_activate_even_when_true():
    data = tracking()
    data["source_observed_at"] = (NOW - timedelta(days=3)).isoformat()
    result = readiness(track=data, route=routing(True), authority=True, publication=True)
    assert "tracking_verified" in result["blockers"]
    assert result["launch_ready"] is False


def test_stale_zip_snapshot_cannot_activate_even_when_true():
    data = zip_gate()
    data["source_observed_at"] = (NOW - timedelta(hours=7)).isoformat()
    result = readiness(zip_state=data, route=routing(True), authority=True, publication=True)
    assert "zip_targeting_verified" in result["blockers"]


def test_stale_source_update_cannot_activate_even_when_true():
    data = zip_gate()
    data["verified_freshness"]["source_newest_last_updated"] = (
        NOW - timedelta(hours=31)
    ).isoformat()
    result = readiness(zip_state=data, route=routing(True), authority=True, publication=True)
    assert "zip_targeting_verified" in result["blockers"]


def test_stale_routing_cannot_activate_even_when_true():
    data = routing(True)
    data["observed_at"] = (NOW - timedelta(hours=2)).isoformat()
    result = readiness(route=data, authority=True, publication=True)
    assert "routing_runtime_verified" in result["blockers"]


@pytest.mark.parametrize("field", ["verified_at", "source_observed_at"])
def test_missing_tracking_timestamp_is_not_accepted(field):
    data = tracking()
    del data[field]
    assert readiness(track=data)["gates"]["tracking_verified"] is False


def test_future_evidence_fails_closed():
    data = routing(True)
    data["observed_at"] = (NOW + timedelta(minutes=15)).isoformat()
    result = readiness(route=data, authority=True, publication=True)
    assert result["launch_ready"] is False


def test_naive_verification_clock_rejected():
    with pytest.raises(ValueError, match="timezone"):
        readiness(now=datetime(2026, 10, 9, 16, 5))


def test_routing_and_founder_approval_cannot_bypass_unconfirmed_cst():
    result = readiness(route=routing(True), authority=True, publication=True)
    assert result["operating_hours"]["timezone_interpretation_verified"] is False
    assert result["gates"]["operating_hours_verified"] is False
    assert "operating_hours_verified" in result["blockers"]
    assert result["call_cta_enabled"] is False


def test_expired_confirmation_cannot_open_hours_gate():
    old = timezone_confirmation(now=NOW - timedelta(days=32))
    result = readiness(route=routing(True), authority=True, publication=True, tz=old)
    assert "operating_hours_verified" in result["blockers"]


def test_policy_drift_fails_closed_even_with_confirmed_zone():
    result = readiness(
        route=routing(True), authority=True, publication=True,
        tz=timezone_confirmation(),
        operating_hours={"timezone": "CST", "monday_friday": "24/7"},
    )
    assert result["operating_hours"]["reported_policy_matches"] is False
    assert result["launch_ready"] is False


@pytest.mark.parametrize(("timestamp", "zone", "should_pass"), [
    ("2026-01-12T14:00:00+00:00", "America/Chicago", True),
    ("2026-01-12T13:59:00+00:00", "America/Chicago", False),
    ("2026-07-06T13:00:00+00:00", "America/Chicago", True),
    ("2026-07-06T13:00:00+00:00", "Etc/GMT+6", False),
    ("2026-07-05T14:59:00+00:00", "America/Chicago", False),
    ("2026-07-05T15:00:00+00:00", "America/Chicago", True),
    ("2026-07-05T21:00:00+00:00", "America/Chicago", False),
])
def test_hour_boundaries_and_daylight_saving(timestamp, zone, should_pass):
    now = datetime.fromisoformat(timestamp)
    result = evaluate_buyer_hours(
        REPORT, timezone_confirmation(now=now, zone=zone), now=now
    )
    assert result["operating_hours_verified"] is should_pass
    assert result["call_authorized"] is False


@pytest.mark.parametrize("bad", [
    {"buyer_confirmed": "true", "zone_name": "America/Chicago", "source_ref": "gmail:x"},
    {"buyer_confirmed": True, "zone_name": "US/Eastern", "source_ref": "gmail:x"},
    {"buyer_confirmed": True, "zone_name": ["America/Chicago"], "source_ref": "gmail:x"},
    {"buyer_confirmed": True, "zone_name": "America/Chicago", "source_ref": "manual"},
    {"buyer_confirmed": True, "zone_name": "America/Chicago", "source_ref": "gmail:x",
     "confirmed_at": "naive date"},
])
def test_untrusted_or_invalid_timezone_claim_fails_closed(bad):
    result = evaluate_buyer_hours(REPORT, bad, now=NOW)
    assert result["operating_hours_verified"] is False
