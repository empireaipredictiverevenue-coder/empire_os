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

def test_pilot_accepts_weekday_ten_to_noon_only():
    start, end = local(12, 10), local(12, 12)
    control=spec(start,end)
    result=_control(control,local(12, 10, 45))
    assert result[1]==end

@pytest.mark.parametrize("start,end,checked",[
    ((12,8,0),(12,10,0),(12,9,0)),  # general hours, outside pilot
    ((12,9,30),(12,11,30),(12,10,30)), # starts before 10
    ((12,11,0),(12,13,0),(12,11,30)), # extends beyond noon
    ((17,10,0),(17,12,0),(17,11,0)), # Saturday, still buyer-general hours
    ((18,10,0),(18,12,0),(18,11,0)), # Sunday
])
def test_control_denies_outside_narrow_pilot_even_if_buyer_general_hours_allow(
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
