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
