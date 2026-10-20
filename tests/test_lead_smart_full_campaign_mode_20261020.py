"""Full-campaign mode is recurring and explicitly limited, not a 15-minute pilot."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json
import pytest
from empire_os.lead_smart_site_handoff import (
    CAMPAIGN, NUMBER, SCHEMA, HandoffHeld,
    _control, reserve_site_handoff, site_handoff_available,
    verified_site_handoff_control,
)
from empire_os.lead_smart_launch_readiness import _supervised_buyer_confirmation

CHICAGO=ZoneInfo("America/Chicago")
def local(day,hour=9,minute=0):
    return datetime(2026,10,day,hour,minute,tzinfo=CHICAGO).astimezone(timezone.utc)

def campaign(daily=2,total=6):
    return {
        "schema_version":SCHEMA,"mode":"FULL_CAMPAIGN",
        "campaign_id":CAMPAIGN,"tracking_number":NUMBER,
        "enabled":True,"starts_at":local(20,8).isoformat(),
        "ends_at":local(27,8).isoformat(),
        "buyer_live_authorization_ref":"gmail:1a1551ac7204ff8a",
        "traffic_source":"EMPIRE_FIRST_PARTY_ORGANIC",
        "founder_authority_ref":
            "docs/evidence/lead_smart_full_campaign_founder_directive_20261020.json",
        "monitoring_owner":"Founder launch operator",
        "stop_method":"atomic_site_handoff_gate",
        "max_site_handoffs":total,"max_daily_site_handoffs":daily,
    }

def readiness(now):
    return {
        "schema_version":"empire.lead_smart.launch_readiness.v1",
        "mode":"READY","launch_ready":True,"call_cta_enabled":True,
        "execution_authority":"LIVE_TRAFFIC","buyer_window_open_now":True,
        "gates":{"site_disclosure":True},
        "operating_hours":{"evaluated_at":now.isoformat()},
    }

def test_campaign_mode_supports_normal_weekday_and_weekend_hours():
    c=campaign()
    assert _control(c,local(20,8,30))
    assert _control(c,local(20,17,59))
    assert _control(c,local(24,10,15)) # Saturday
    for now in (local(20,7,59),local(20,18),local(24,9,59),
                local(24,16),local(27,9)):
        with pytest.raises(HandoffHeld):
            _control(c,now)

@pytest.mark.parametrize("field,bad",[
    ("buyer_live_authorization_ref","unknown"),
    ("founder_authority_ref","docs/evidence/lead_smart_founder_launch_intent_20261011.json"),
    ("traffic_source","PAID_SEARCH"),
    ("max_daily_site_handoffs",0),
    ("max_daily_site_handoffs",1001),
    ("max_daily_site_handoffs",True),
])
def test_full_campaign_rejects_bad_provenance_or_limits(field,bad):
    c=campaign();c[field]=bad
    with pytest.raises(HandoffHeld):
        _control(c,local(20,9))

def test_campaign_rejects_more_than_14_days():
    c=campaign()
    c["ends_at"]=datetime(2026,11,5,10,tzinfo=CHICAGO).astimezone(timezone.utc).isoformat()
    with pytest.raises(HandoffHeld):
        _control(c,local(20,9))

def test_daily_counter_resets_without_erasing_total(tmp_path):
    conf=tmp_path/"approved_control.json"
    led=tmp_path/"site_handoffs.json"
    conf.write_text(json.dumps(campaign(daily=2,total=5)))
    def available(moment):
        return site_handoff_available("60601",config_path=conf,ledger_path=led,
            readiness=readiness(moment),eligible_zip=True,now=moment)
    def reserve(moment):
        return reserve_site_handoff("60601",config_path=conf,ledger_path=led,
            readiness=readiness(moment),eligible_zip=True,now=moment)
    a=local(20,9)
    assert available(a)
    for _ in range(2):assert reserve(a)=="tel:"+NUMBER
    assert not available(a)
    with pytest.raises(HandoffHeld):reserve(a)
    b=local(21,9)
    assert available(b)
    for _ in range(2):reserve(b)
    assert not available(b)
    assert available(local(22,9))
    reserve(local(22,9))
    state=json.loads(led.read_text())
    assert state["site_handoffs"]==5
    assert state["daily_site_handoffs"]==1
    assert state["local_day"]=="2026-10-22"
    assert not available(local(22,9))
    assert not available(local(23,9))

def test_unknown_ledger_fields_fail_closed(tmp_path):
    c=campaign()
    p=tmp_path/"control";p.write_text(json.dumps(c))
    led=tmp_path/"ledger"
    now=local(20,9)
    window,_=_control(c,now)
    led.write_text(json.dumps({"schema_version":"empire.lead_smart.site_handoff_ledger.v1",
       "window":window,"site_handoffs":1}))
    assert not verified_site_handoff_control(config_path=p,ledger_path=led,now=now)
    assert not site_handoff_available("60601",config_path=p,ledger_path=led,
        readiness=readiness(now),eligible_zip=True,now=now)

def test_full_campaign_buyer_written_go_ahead_is_sufficient_for_scoped_attestation():
    c=campaign()
    r={
        "mode":"FULL_CAMPAIGN",
        "buyer":"Lead Smart","campaign_id":CAMPAIGN,"tracking_number":NUMBER,
        "source_ref":"gmail:1a145122e620d481",
        "buyer_live_authorization_ref":c["buyer_live_authorization_ref"],
        "founder_authority_ref":c["founder_authority_ref"],
        "buyer_confirmed_direct_route":True,
        "buyer_confirmed_original_ani":True,
        "founder_witnessed_voice_connection":True,
        "independently_proven_admin_api":False,
        "starts_at":c["starts_at"],"ends_at":c["ends_at"],
    }
    assert _supervised_buyer_confirmation(r,local(20,9))
    assert _supervised_buyer_confirmation(r,local(24,11))
    assert not _supervised_buyer_confirmation({**r,"buyer_live_authorization_ref":"fake"},local(20,9))
    assert not _supervised_buyer_confirmation(r,local(20,19))
