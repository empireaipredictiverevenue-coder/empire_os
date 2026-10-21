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


def readiness(*, track=None, zip_state=None, route=None, authority=False, publication=False, now=NOW, tz=None, operating_hours=None, caller_id=False, buyer_page=False, legal=False, pilot_stop=True, recording=True):
    return build_launch_readiness(
        tracking=tracking() if track is None else track,
        zip_gate=zip_gate() if zip_state is None else zip_state,
        routing=routing() if route is None else route,
        operating_hours=REPORT if operating_hours is None else operating_hours,
        timezone_confirmation=tz,
        caller_id_pass_through_verified=caller_id,
        buyer_landing_page_approved=buyer_page,
        legal_release_verified=legal,
        recording_notice_and_retention_verified=recording,
        landing_publication_authorized=publication,
        founder_live_traffic_authorized=authority,
        pilot_stop_verified=pilot_stop,
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
                       tz=timezone_confirmation(), caller_id=True, buyer_page=True, legal=True)
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
    assert result["hours_policy_confirmed"] is (zone == "America/Chicago")
    assert result["buyer_window_open_now"] is should_pass
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


def test_oct9_support_timezone_confirmation_closes_timezone_interpretation_only():
    from empire_os.buyer_supply_policy import lead_smart_confirmed_roofing_policy
    policy = lead_smart_confirmed_roofing_policy(
        source_ref="gmail:1a10c6b2530f2951"
    )
    confirmed = policy["operating_hours_confirmation"]
    result = readiness(
        now=datetime(2026, 10, 9, 19, 35, 30, tzinfo=timezone.utc),
        tz=confirmed,
        track={
            "state": "VERIFIED",
            "tracking_verified": True,
            "verified_at": "2026-10-09T19:35:28Z",
            "source_observed_at": "2026-10-09T19:35:28Z",
        },
        zip_state={
            "zip_targeting_gate_verified": True,
            "zip_coverage_activation_verified": True,
            "source_fresh_for_targeting": True,
            "source_observed_at": "2026-10-09T19:35:28Z",
            "verified_freshness": {
                "source_newest_last_updated": "2026-10-09T19:35:28Z"
            },
        },
    )
    assert result["operating_hours"]["timezone_interpretation_verified"] is True
    assert result["operating_hours_policy_confirmed"] is True
    assert result["buyer_window_open_now"] is True
    assert result["gates"]["operating_hours_verified"] is True
    assert result["gates"]["caller_id_pass_through_verified"] is False
    assert result["gates"]["buyer_landing_page_approved"] is False
    assert result["launch_ready"] is False
    assert result["execution_authority"] == "NONE"


def test_even_all_other_green_gates_cannot_override_missing_caller_id_proof():
    result = readiness(
        route=routing(True), authority=True, publication=True,
        tz=timezone_confirmation(), buyer_page=True, caller_id=False, legal=True,
    )
    assert result["blockers"] == ["caller_id_pass_through_verified"]
    assert result["launch_ready"] is False
    assert result["call_cta_enabled"] is False


def test_even_all_other_green_gates_cannot_override_buyer_page_pending():
    result = readiness(
        route=routing(True), authority=True, publication=True,
        tz=timezone_confirmation(), buyer_page=False, caller_id=True, legal=True,
    )
    assert result["blockers"] == ["buyer_landing_page_approved"]
    assert result["launch_ready"] is False
    assert result["organic_traffic_authorized"] is False

def test_confirmed_hours_policy_is_distinct_from_an_outside_call_window():
    closed = datetime.fromisoformat("2026-10-11T10:00:00+00:00")  # Sunday 05:00 CDT
    result = readiness(
        now=closed,
        tz=timezone_confirmation(now=closed),
        route={"routing_runtime_verified": True, "observed_at": closed.isoformat()},
        track={"state": "VERIFIED", "tracking_verified": True,
               "verified_at": closed.isoformat(),
               "source_observed_at": closed.isoformat()},
        zip_state={"zip_targeting_gate_verified": True,
                   "zip_coverage_activation_verified": True,
                   "source_fresh_for_targeting": True,
                   "source_observed_at": closed.isoformat(),
                   "verified_freshness": {
                       "source_newest_last_updated": closed.isoformat()}},
        caller_id=True, buyer_page=True, authority=True, publication=True, legal=True,
    )
    assert result["operating_hours_policy_confirmed"] is True
    assert result["buyer_window_open_now"] is False
    assert result["gates"]["operating_hours_verified"] is False
    assert result["blockers"] == ["operating_hours_verified"]
    assert result["call_cta_enabled"] is False
    assert result["organic_traffic_authorized"] is False
    assert result["execution_authority"] == "NONE"


@pytest.mark.parametrize("field", ["authority", "publication"])
@pytest.mark.parametrize("value", ["false", "true", "0", "1", 1, 0, None, [], {}, [True], {"approved": True}])
def test_approval_gates_require_literal_boolean_true(field, value):
    arguments = dict(route=routing(True), authority=True, publication=True,
                     tz=timezone_confirmation(), caller_id=True, buyer_page=True, legal=True)
    arguments[field] = value
    result = readiness(**arguments)
    gate = {"authority": "founder_live_traffic_authorized",
            "publication": "landing_publication_authorized"}[field]
    assert result["blockers"] == [gate]
    assert result["launch_ready"] is False
    assert result["call_cta_enabled"] is False
    assert result["organic_traffic_authorized"] is False
    assert result["execution_authority"] == "NONE"


def test_all_old_gates_cannot_authorize_traffic_without_effective_legal_release():
    result = readiness(route=routing(True), authority=True, publication=True,
                       tz=timezone_confirmation(), caller_id=True, buyer_page=True)
    assert result["launch_ready"] is False
    assert "legal_release_verified" in result["blockers"]
    assert result["execution_authority"] == "NONE"


@pytest.mark.parametrize("legal", [None, False, 0, 1, "true", "false", {}, [True]])
def test_legal_release_requires_literal_verified_boolean(legal):
    result = readiness(route=routing(True), authority=True, publication=True,
                       tz=timezone_confirmation(), caller_id=True, buyer_page=True,
                       legal=legal)
    assert result["gates"]["legal_release_verified"] is False
    assert result["launch_ready"] is False
    assert result["execution_authority"] == "NONE"



def test_live_launch_requires_independently_verified_pilot_stop():
    result = readiness(
        route=routing(True), authority=True, publication=True,
        tz=timezone_confirmation(), caller_id=True, buyer_page=True,
        legal=True, pilot_stop=False,
    )
    assert result["gates"]["pilot_stop_verified"] is False
    assert result["blockers"] == ["pilot_stop_verified"]
    assert result["call_cta_enabled"] is False
    assert result["organic_traffic_authorized"] is False
    assert result["execution_authority"] == "NONE"


@pytest.mark.parametrize("untrusted", [None, 0, 1, "true", "false", [], {}, [True]])
def test_pilot_stop_requires_strict_boolean_and_not_a_claim(untrusted):
    result = readiness(
        route=routing(True), authority=True, publication=True,
        tz=timezone_confirmation(), caller_id=True, buyer_page=True,
        legal=True, pilot_stop=untrusted,
    )
    assert result["blockers"] == ["pilot_stop_verified"]
    assert result["execution_authority"] == "NONE"



def test_founder_decision_is_consumed_only_at_exact_campaign_scope(tmp_path):
    import json
    from pathlib import Path
    from scripts.materialize_lead_smart_launch_readiness import founder_launch_approved
    assert founder_launch_approved() is True
    path = tmp_path / "docs/evidence/lead_smart_founder_launch_intent_20261011.json"
    path.parent.mkdir(parents=True)
    record = json.loads(
        (Path("docs/evidence/lead_smart_founder_launch_intent_20261011.json")).read_text()
    )
    record["scope"]["acquisition"] = "paid media"
    path.write_text(json.dumps(record))
    assert founder_launch_approved(tmp_path) is False


def test_site_legal_release_cannot_substitute_for_call_recording_governance():
    ready_without_recording = readiness(
        route=routing(True), authority=True, publication=True,
        tz=timezone_confirmation(), caller_id=True, buyer_page=True,
        legal=True, recording=False,
    )
    assert ready_without_recording["blockers"] == [
        "recording_notice_and_retention_verified"
    ]
    assert ready_without_recording["launch_ready"] is False
    assert ready_without_recording["call_cta_enabled"] is False
    assert ready_without_recording["execution_authority"] == "NONE"


def test_recording_claim_string_cannot_grant_launch_authority():
    candidate = readiness(
        route=routing(True), authority=True, publication=True,
        tz=timezone_confirmation(), caller_id=True, buyer_page=True,
        legal=True, recording="true",
    )
    assert candidate["gates"]["recording_notice_and_retention_verified"] is False
    assert candidate["launch_ready"] is False


def test_exact_founder_witnessed_buyer_configuration_is_valid_for_original_window_only():
    from empire_os.lead_smart_launch_readiness import _supervised_buyer_confirmation
    now = datetime(2026, 10, 19, 15, 35, tzinfo=timezone.utc)
    record = {
        "buyer":"Lead Smart","campaign_id":"CA8278ed3f26e9495b881fe3833174d007",
        "tracking_number":"+18883579305","source_ref":"gmail:1a145122e620d481",
        "founder_authority_ref":"docs/evidence/lead_smart_founder_launch_intent_20261011.json",
        "buyer_confirmed_direct_route":True,"buyer_confirmed_original_ani":True,
        "founder_witnessed_voice_connection":True,
        "independently_proven_admin_api":False,
        "starts_at":"2026-10-19T15:00:00+00:00",
        "ends_at":"2026-10-19T17:00:00+00:00",
    }
    assert _supervised_buyer_confirmation(record,now)
    assert not _supervised_buyer_confirmation(record,datetime(2026,10,19,17,0,tzinfo=timezone.utc))
    assert not _supervised_buyer_confirmation({**record,"source_ref":"gmail:invented"},now)
    assert not _supervised_buyer_confirmation({**record,"independently_proven_admin_api":True},now)
    assert not _supervised_buyer_confirmation({**record,"founder_witnessed_voice_connection":"true"},now)
    assert not _supervised_buyer_confirmation({**record,"campaign_id":"wrong"},now)
    # The buyer's written Direct-route evidence remains scoped to a selected
    # short weekday window, including a separately scheduled Tuesday retry.
    retry = {**record, "starts_at":"2026-10-20T15:00:00Z",
             "ends_at":"2026-10-20T15:15:00Z"}
    assert _supervised_buyer_confirmation(
        retry,datetime(2026,10,20,15,5,tzinfo=timezone.utc))
    assert not _supervised_buyer_confirmation(
        {**retry,"ends_at":"2026-10-20T23:15:00Z"},
        datetime(2026,10,20,15,5,tzinfo=timezone.utc))
    assert not _supervised_buyer_confirmation(
        {**retry,"starts_at":"2026-10-17T15:00:00Z",
         "ends_at":"2026-10-17T15:15:00Z"},
        datetime(2026,10,17,15,5,tzinfo=timezone.utc))


def test_source_bound_pilot_substitutes_unreadable_admin_route_not_recording_or_legal():
    from empire_os.lead_smart_launch_readiness import build_launch_readiness
    now = datetime(2026, 10, 19, 15, 35, tzinfo=timezone.utc)
    moment = now.isoformat()
    record = {
        "buyer":"Lead Smart","campaign_id":"CA8278ed3f26e9495b881fe3833174d007",
        "tracking_number":"+18883579305","source_ref":"gmail:1a145122e620d481",
        "founder_authority_ref":"docs/evidence/lead_smart_founder_launch_intent_20261011.json",
        "buyer_confirmed_direct_route":True,"buyer_confirmed_original_ani":True,
        "founder_witnessed_voice_connection":True,"independently_proven_admin_api":False,
        "starts_at":"2026-10-19T15:00:00Z","ends_at":"2026-10-19T17:00:00Z",
    }
    track={"state":"VERIFIED","tracking_verified":True,"verified_at":moment,
           "source_observed_at":moment}
    covered={"zip_targeting_gate_verified":True,"zip_coverage_activation_verified":True,
             "source_fresh_for_targeting":True,"source_observed_at":moment,
             "verified_freshness":{"source_newest_last_updated":moment}}
    result=build_launch_readiness(
        tracking=track,zip_gate=covered,
        routing={"routing_runtime_verified":False,"observed_at":moment},
        operating_hours=REPORT,
        timezone_confirmation=timezone_confirmation(now=now),
        supervised_buyer_confirmation=record,
        caller_id_pass_through_verified=False,
        buyer_landing_page_approved=True,landing_publication_authorized=True,
        founder_live_traffic_authorized=True,
        pilot_stop_verified=True,legal_release_verified=False,
        recording_notice_and_retention_verified=False,now=now
    )
    assert result["buyer_attested_supervised_route"] is True
    assert result["gates"]["routing_runtime_verified"] is False
    assert result["gates"]["caller_id_pass_through_verified"] is False
    assert result["independent_route_proven"] is False
    assert result["revenue_verified"] is False
    assert result["pilot_admission_substitutions"] == [
        "caller_id_pass_through_verified","routing_runtime_verified"]
    assert set(result["blockers"]) == {
        "legal_release_verified","recording_notice_and_retention_verified"}
    assert result["launch_ready"] is False
    assert result["call_cta_enabled"] is False


def test_recording_approach_is_exact_source_bound_not_fake_legal_certification():
    from empire_os.lead_smart_launch_readiness import _supervised_consumer_disclosure
    proof={
        "mandatory_recording_source_ref":"gmail:1a13568711da9a5b",
        "buyer_disclaimer_test_ref":"gmail:1a145b32d742f3b1",
        "buyer_deletion_source_ref":"gmail:1a145a443180606f",
        "buyer_mandatory_recording":True,
        "buyer_deletes_if_legally_required":True,
        "pre_dial_affirmative_consent_proven":True,
        "specific_call_privacy_notice_live":True,
        "general_privacy_terms_live":True,
        "call_api_exact_sha256":"4ad55e9de33009ce75a9981cd83a962f15004f7a8f9b1a79e5cdf40c1713fb60",
        "buyer_admin_configuration_proven":False,
        "legal_compliance_certified":False,
    }
    assert _supervised_consumer_disclosure(proof)
    for field,bad in [
        ("pre_dial_affirmative_consent_proven",False),
        ("general_privacy_terms_live",False),
        ("specific_call_privacy_notice_live",False),
        ("buyer_deletes_if_legally_required",False),
        ("call_api_exact_sha256","unreviewed-drift"),
        ("buyer_admin_configuration_proven",True),
        ("legal_compliance_certified",True),
    ]:
        assert not _supervised_consumer_disclosure({**proof,field:bad})


def test_static_provider_number_assignment_two_hour_window_only():
    source=tracking()
    for key in ("verified_at","source_observed_at"):
        source[key]=(NOW-timedelta(minutes=80)).isoformat()
    assert readiness(track=source)["gates"]["tracking_verified"] is True
    source["source_observed_at"]=(NOW-timedelta(minutes=121)).isoformat()
    assert readiness(track=source)["gates"]["tracking_verified"] is False


def test_exact_direct_assignment_stays_verified_for_next_day_retry_not_forever():
    now=NOW+timedelta(hours=26)
    source=tracking()
    source.update({
        "campaign_id":"CA8278ed3f26e9495b881fe3833174d007",
        "tracking_number":"+18883579305",
        "tracking_number_assigned":True,
        "verification_path":"DIRECT_CAMPAIGN_OBJECT",
        "verification_scope":"NUMBER_TO_CAMPAIGN_BINDING",
    })
    assert readiness(track=source,now=now)["gates"]["tracking_verified"] is True
    assert readiness(track={**source,"campaign_id":"wrong"},now=now)["gates"]["tracking_verified"] is False
    assert readiness(track={**source,"tracking_number_assigned":False},now=now)["gates"]["tracking_verified"] is False
    later=NOW+timedelta(hours=49)
    assert readiness(track=source,now=later)["gates"]["tracking_verified"] is False

def test_newer_lead_smart_caller_local_hours_supersede_old_chicago_authority():
    from empire_os.buyer_supply_policy import lead_smart_confirmed_roofing_policy
    from empire_os.lead_smart_operating_hours import evaluate_buyer_hours
    current = datetime(2026, 10, 21, 15, 10, tzinfo=timezone.utc)
    policy = lead_smart_confirmed_roofing_policy(
        source_ref="gmail:1a10c6b2530f2951"
    )
    supersession = policy["operating_hours_supersession"]
    assert supersession["source_ref"] == "gmail:1a15ea2dfa8c46b1"
    assert supersession["rule"] == "HOURS_DEPEND_ON_CALLER_TIMEZONE"
    assert supersession["caller_timezone_verified"] is False
    assert supersession["buyer_acceptance_window_verified"] is False
    original = evaluate_buyer_hours(
        REPORT, policy["operating_hours_confirmation"], now=current
    )
    assert original["operating_hours_verified"] is True  # historical view only
    reconciled = evaluate_buyer_hours(
        REPORT, policy["operating_hours_confirmation"], now=current,
        superseding_buyer_policy=supersession,
    )
    assert reconciled["within_reported_window"] is True
    assert reconciled["buyer_window_open_now"] is False
    assert reconciled["operating_hours_verified"] is False
    assert reconciled["hours_policy_confirmed"] is False
    assert reconciled["supersession_review_required"] is True
    assert reconciled["supersession_source_ref"] == "gmail:1a15ea2dfa8c46b1"
    assert reconciled["execution_authority"] == "NONE"

    # Even a future arbitrary boolean must not silently "verify" caller location.
    unreviewed = {**supersession, "caller_timezone_verified": True,
                  "buyer_acceptance_window_verified": True}
    fail_closed = evaluate_buyer_hours(
        REPORT, policy["operating_hours_confirmation"], now=current,
        superseding_buyer_policy=unreviewed,
    )
    assert fail_closed["operating_hours_verified"] is False


def test_full_release_cannot_pass_using_superseded_chicago_policy():
    from empire_os.buyer_supply_policy import lead_smart_confirmed_roofing_policy
    policy = lead_smart_confirmed_roofing_policy(
        source_ref="gmail:1a10c6b2530f2951"
    )
    now = datetime(2026, 10, 21, 15, 10, tzinfo=timezone.utc)
    fresh = {
        "state": "VERIFIED", "tracking_verified": True,
        "verified_at": now.isoformat(), "source_observed_at": now.isoformat(),
    }
    zips = {
        "zip_targeting_gate_verified": True,
        "zip_coverage_activation_verified": True,
        "source_fresh_for_targeting": True,
        "source_observed_at": now.isoformat(),
        "verified_freshness": {"source_newest_last_updated": now.isoformat()},
    }
    result = build_launch_readiness(
        tracking=fresh, zip_gate=zips,
        routing={"routing_runtime_verified": True, "observed_at": now.isoformat()},
        operating_hours=policy["operating_hours"],
        timezone_confirmation=policy["operating_hours_confirmation"],
        operating_hours_supersession=policy["operating_hours_supersession"],
        caller_id_pass_through_verified=True, buyer_landing_page_approved=True,
        legal_release_verified=True, recording_notice_and_retention_verified=True,
        landing_publication_authorized=True, founder_live_traffic_authorized=True,
        pilot_stop_verified=True, now=now,
    )
    assert result["blockers"] == ["operating_hours_verified"]
    assert result["launch_ready"] is False
    assert result["call_cta_enabled"] is False
    assert result["execution_authority"] == "NONE"
