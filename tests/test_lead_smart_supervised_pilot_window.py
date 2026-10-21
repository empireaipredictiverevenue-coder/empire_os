"""Lead Smart first revenue pilot cannot leak outside supervised Chicago window."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json
import pytest

from empire_os.lead_smart_site_handoff import (
    CAMPAIGN, NUMBER, SCHEMA, HandoffHeld,
    _control, verified_site_handoff_control, chicago_buyer_hours_open,
)

CHICAGO = ZoneInfo("America/Chicago")

def local(day, hour, minute=0):
    return datetime(2026, 10, day, hour, minute, tzinfo=CHICAGO).astimezone(timezone.utc)

def spec(start, end):
    return {
        "schema_version":SCHEMA,
        "enabled":True,
        "campaign_id":CAMPAIGN,
        "tracking_number":NUMBER,
        "max_site_handoffs":5,
        "stop_method":"atomic_site_handoff_gate",
        "monitoring_owner":"Founder pilot operator",
        "founder_authority_ref":"docs/evidence/lead_smart_founder_launch_intent_20261011.json",
        "starts_at":start.isoformat(),
        "ends_at":end.isoformat(),
    }

def test_actual_buyer_general_hours_are_preserved_and_pilot_is_narrower():
    assert chicago_buyer_hours_open(local(12, 8, 30)) is True
    assert chicago_buyer_hours_open(local(17, 11)) is True
    assert chicago_buyer_hours_open(local(12, 7, 59)) is False

def test_bounded_weekday_pilot_and_tuesday_retry_are_supported():
    start, end = local(12, 10), local(12, 12)
    control=spec(start,end)
    result=_control(control,local(12, 10, 45))
    assert result[1]==end
    retry_start,retry_end=local(20,10),local(20,10,15)
    assert _control(spec(retry_start,retry_end),local(20,10,5))[1]==retry_end

@pytest.mark.parametrize("start,end,checked",[
    ((12,7,30),(12,9,30),(12,8,30)),  # outside weekday offer hours
    ((12,17,0),(12,19,0),(12,17,30)), # extends past 6PM buyer close
    ((17,10,0),(17,12,0),(17,11,0)), # Saturday, not in supervised weekday scope
    ((18,10,0),(18,12,0),(18,11,0)), # Sunday
])
def test_control_denies_outside_bounded_weekday_offer_hours(
        start,end,checked):
    with pytest.raises(HandoffHeld):
        _control(spec(local(*start),local(*end)),local(*checked))

def test_live_control_receipt_cannot_self_activate_outside_supervised_window(tmp_path):
    config=tmp_path/"approved_control.json"
    ledger=tmp_path/"site_handoffs.json"
    config.write_text(json.dumps(spec(local(17,10),local(17,12))))
    assert verified_site_handoff_control(
        config_path=config,ledger_path=ledger,now=local(17,11),
    ) is False
    assert not ledger.exists()

def test_fails_closed_on_invalid_operator_and_unapproved_control(tmp_path):
    start,end=local(12,10),local(12,12)
    control=spec(start,end)
    control["monitoring_owner"]=""
    with pytest.raises(HandoffHeld):
        _control(control,local(12,11))
    control=spec(start,end)
    control["enabled"]=False
    with pytest.raises(HandoffHeld):
        _control(control,local(12,11))

def test_prepared_operator_template_never_counts_as_live_approval(tmp_path):
    from pathlib import Path
    template = (
        Path(__file__).resolve().parents[1]
        / "docs/evidence/lead_smart_supervised_pilot_DISABLED_TEMPLATE_20261012.json"
    )
    control = json.loads(template.read_text())
    assert control["enabled"] is False
    assert control["max_site_handoffs"] == 5
    assert control["stop_method"] == "atomic_site_handoff_gate"
    assert control["starts_at"] is None
    assert control["ends_at"] is None
    assert verified_site_handoff_control(
        config_path=template,
        ledger_path=tmp_path/"site_handoffs.json",
        now=local(12,11),
    ) is False
    assert not (tmp_path/"site_handoffs.json").exists()


def test_pending_monitor_never_valid_if_disabled_template_is_accidentally_enabled(tmp_path):
    from pathlib import Path
    template=Path(__file__).resolve().parents[1] / "docs/evidence/lead_smart_supervised_pilot_DISABLED_TEMPLATE_20261012.json"
    control=json.loads(template.read_text())
    control.update({"enabled":True,"starts_at":local(19,10).isoformat(),
                    "ends_at":local(19,12).isoformat()})
    with pytest.raises(HandoffHeld):
        _control(control,local(19,10))
    candidate=tmp_path / "not_really_approved.json"
    candidate.write_text(json.dumps(control))
    assert verified_site_handoff_control(config_path=candidate,
             ledger_path=tmp_path / "no_handoffs.json",now=local(19,10)) is False


def test_monday_20261019_prepared_control_remains_disabled(tmp_path):
    from pathlib import Path
    prepared=Path(__file__).resolve().parents[1] / "docs/evidence/lead_smart_20261019_SUPERVISED_DISABLED_PREPARED.json"
    control=json.loads(prepared.read_text())
    assert control['enabled'] is False
    assert control['monitoring_owner'].startswith('PENDING')
    assert control['max_site_handoffs']==5
    assert control['starts_at']==local(19,10).isoformat()
    assert control['ends_at']==local(19,12).isoformat()
    assert verified_site_handoff_control(config_path=prepared,
             ledger_path=tmp_path / "no_handoffs.json",now=local(19,10)) is False
    assert not (tmp_path / "no_handoffs.json").exists()


def test_monday_five_handoff_cap_and_noon_cutoff_in_isolated_simulation(tmp_path):
    from empire_os.lead_smart_site_handoff import reserve_site_handoff,site_handoff_available
    control=spec(local(19,10),local(19,12))
    conf=tmp_path / "approved_control.json"
    ledger=tmp_path / "site_handoffs.json"
    conf.write_text(json.dumps(control))
    checked=local(19,10,15)
    readiness={
        "schema_version":"empire.lead_smart.launch_readiness.v1",
        "mode":"READY", "launch_ready":True,
        "call_cta_enabled":True,"execution_authority":"LIVE_TRAFFIC",
        "buyer_window_open_now":True, "gates":{"all_preflight_gates":True},
        "operating_hours":{"evaluated_at":checked.isoformat()},
    }
    for _ in range(5):
        assert reserve_site_handoff("60601",config_path=conf,ledger_path=ledger,
                    readiness=readiness,eligible_zip=True,now=checked).startswith("tel:")
    assert json.loads(ledger.read_text())["site_handoffs"]==5
    assert not site_handoff_available("60601",config_path=conf,ledger_path=ledger,
                readiness=readiness,eligible_zip=True,now=checked)
    with pytest.raises(HandoffHeld):
        reserve_site_handoff("60601",config_path=conf,ledger_path=ledger,
                readiness=readiness,eligible_zip=True,now=checked)
    at_noon=local(19,12)
    readiness["operating_hours"]["evaluated_at"]=at_noon.isoformat()
    assert not site_handoff_available("60601",config_path=conf,ledger_path=ledger,
                readiness=readiness,eligible_zip=True,now=at_noon)


def test_configurable_handoff_limit_replaces_hardcoded_five_without_disabling_stop(tmp_path):
    from empire_os.lead_smart_site_handoff import (
        reserve_site_handoff, site_handoff_available, LEDGER_SCHEMA,
    )
    check = local(19, 10, 15)
    config = spec(local(19, 10),local(19, 12))
    config["max_site_handoffs"] = 8
    f = tmp_path / "approved_control.json"
    ledger = tmp_path / "site_handoffs.json"
    f.write_text(json.dumps(config))
    ready = {
        "schema_version":"empire.lead_smart.launch_readiness.v1",
        "mode":"READY", "launch_ready":True,"call_cta_enabled":True,
        "execution_authority":"LIVE_TRAFFIC","buyer_window_open_now":True,
        "gates":{"test_release":True},
        "operating_hours":{"evaluated_at":check.isoformat()},
    }
    for count in range(8):
        assert site_handoff_available(
            "60601",config_path=f,ledger_path=ledger,
            readiness=ready,eligible_zip=True,now=check
        )
        assert reserve_site_handoff(
            "60601",config_path=f,ledger_path=ledger,
            readiness=ready,eligible_zip=True,now=check
        ).startswith("tel:")
    data = json.loads(ledger.read_text())
    assert data["schema_version"] == LEDGER_SCHEMA
    assert data["site_handoffs"] == 8
    assert not site_handoff_available("60601",config_path=f,ledger_path=ledger,
                                    readiness=ready,eligible_zip=True,now=check)
    with pytest.raises(HandoffHeld):
        reserve_site_handoff("60601",config_path=f,ledger_path=ledger,
                             readiness=ready,eligible_zip=True,now=check)


@pytest.mark.parametrize("bad_limit",[0,-1,10001,"100",True,None])
def test_reusable_campaign_control_rejects_untrusted_limits(bad_limit):
    c=spec(local(19,10),local(19,12))
    c["max_site_handoffs"]=bad_limit
    with pytest.raises(HandoffHeld):
        _control(c,local(19,11))


def test_pilot_readiness_accepts_source_labelled_buyer_route_without_faking_provider_proof(tmp_path):
    from empire_os.lead_smart_site_handoff import site_handoff_available
    checked=local(19,10,25)
    conf=tmp_path/"control.json"; led=tmp_path/"ledger.json"
    conf.write_text(json.dumps(spec(local(19,10),local(19,12))))
    readiness={
        "schema_version":"empire.lead_smart.launch_readiness.v1",
        "mode":"READY","launch_ready":True,"call_cta_enabled":True,
        "execution_authority":"LIVE_TRAFFIC","buyer_window_open_now":True,
        "gates":{
            "legal_release_verified":True,
            "recording_notice_and_retention_verified":True,
            "pilot_stop_verified":True,
            "operating_hours_verified":True,
            "caller_id_pass_through_verified":False,
            "tracking_verified":True,"zip_targeting_verified":True,
            "routing_runtime_verified":False,
            "buyer_landing_page_approved":True,
            "landing_publication_authorized":True,
            "founder_live_traffic_authorized":True,
        },
        "pilot_admission_substitutions":[
            "caller_id_pass_through_verified","routing_runtime_verified"],
        "buyer_attested_supervised_route":True,
        "buyer_route_attestation_ref":"gmail:1a145122e620d481",
        "independent_route_proven":False,"revenue_verified":False,
        "operating_hours":{"evaluated_at":checked.isoformat()},
    }
    assert site_handoff_available(
        "60601",config_path=conf,ledger_path=led,
        readiness=readiness,eligible_zip=True,now=checked)
    for bad in (
        {**readiness,"buyer_attested_supervised_route":False},
        {**readiness,"buyer_route_attestation_ref":"untrusted"},
        {**readiness,"pilot_admission_substitutions":[
            "legal_release_verified","routing_runtime_verified"]},
        {**readiness,"gates":{**readiness["gates"],"recording_notice_and_retention_verified":False}},
        {**readiness,"gates":{**readiness["gates"],"legal_release_verified":False}},
    ):
        assert not site_handoff_available(
            "60601",config_path=conf,ledger_path=led,
            readiness=bad,eligible_zip=True,now=checked)


def test_reviewer_accepts_published_consent_protocol_not_unsigned_claims(tmp_path):
    from empire_os.lead_smart_site_handoff import site_handoff_available
    checked=local(19,10,25)
    conf=tmp_path/"approved_control.json"; ledger=tmp_path/"site_handoffs.json"
    conf.write_text(json.dumps(spec(local(19,10),local(19,12))))
    gates={
        "legal_release_verified":False,
        "recording_notice_and_retention_verified":False,
        "pilot_stop_verified":True,"operating_hours_verified":True,
        "caller_id_pass_through_verified":False,"routing_runtime_verified":False,
        "tracking_verified":True,"zip_targeting_verified":True,
        "buyer_landing_page_approved":True,"landing_publication_authorized":True,
        "founder_live_traffic_authorized":True,
    }
    proof={
        "schema_version":"empire.lead_smart.launch_readiness.v1",
        "mode":"READY","launch_ready":True,"call_cta_enabled":True,
        "execution_authority":"LIVE_TRAFFIC",
        "buyer_window_open_now":True,"gates":gates,
        "pilot_admission_substitutions":[
            "caller_id_pass_through_verified","legal_release_verified",
            "recording_notice_and_retention_verified","routing_runtime_verified",
        ],
        "buyer_attested_supervised_route":True,
        "buyer_route_attestation_ref":"gmail:1a145122e620d481",
        "independent_route_proven":False,"revenue_verified":False,
        "consumer_notice_process_operational":True,
        "independent_legal_clearance_certified":False,
        "buyer_recording_admin_independently_verified":False,
        "operating_hours":{"evaluated_at":checked.isoformat()},
    }
    assert site_handoff_available("60601",config_path=conf,ledger_path=ledger,
                    readiness=proof,eligible_zip=True,now=checked)
    for tampered in [
        {**proof,"consumer_notice_process_operational":False},
        {**proof,"buyer_route_attestation_ref":"wrong-source"},
        {**proof,"pilot_admission_substitutions":["legal_release_verified"]},
        {**proof,"buyer_recording_admin_independently_verified":True},
    ]:
        assert not site_handoff_available("60601",config_path=conf,ledger_path=ledger,
                    readiness=tampered,eligible_zip=True,now=checked)

def test_lock_wait_past_supervised_window_never_reserves_a_handoff(tmp_path, monkeypatch):
    """Closing time is checked again AFTER obtaining the permit lock."""
    from datetime import timedelta
    import empire_os.lead_smart_site_handoff as handoff

    start = local(21, 9)
    end = local(21, 9, 15)
    before = end - timedelta(seconds=1)
    conf = tmp_path / "approved_control.json"
    ledger = tmp_path / "site_handoffs.json"
    control = spec(start, end)
    control["full_campaign_scope_revoked"] = True
    conf.write_text(json.dumps(control))
    ready = {
        "schema_version": "empire.lead_smart.launch_readiness.v1",
        "mode": "READY", "launch_ready": True, "call_cta_enabled": True,
        "execution_authority": "LIVE_TRAFFIC", "buyer_window_open_now": True,
        "gates": {"preflight_passed": True},
        "operating_hours": {"evaluated_at": before.isoformat()},
    }

    class ControlledDatetime(datetime):
        current = before

        @classmethod
        def now(cls, tz=None):
            return cls.current if tz is not None else cls.current.replace(tzinfo=None)

    real_lock = handoff.fcntl.flock

    def advance_while_waiting(fd, operation):
        if operation == handoff.fcntl.LOCK_EX:
            ControlledDatetime.current = end + timedelta(seconds=1)
        return real_lock(fd, operation)

    monkeypatch.setattr(handoff, "datetime", ControlledDatetime)
    monkeypatch.setattr(handoff.fcntl, "flock", advance_while_waiting)
    with pytest.raises(HandoffHeld):
        handoff.reserve_site_handoff(
            "60601", config_path=conf, ledger_path=ledger,
            readiness=ready, eligible_zip=True,
        )
    assert not ledger.exists()
