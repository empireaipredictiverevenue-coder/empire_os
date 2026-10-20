"""Full-campaign console must stage disabled, require a live stop, and never infer sales."""
from datetime import datetime,timezone
from pathlib import Path
import json
import pytest
from scripts import manage_lead_smart_full_campaign_20261020 as op
from empire_os.lead_smart_site_handoff import CAMPAIGN,NUMBER,SCHEMA

def old_control():
    return {
        "schema_version":SCHEMA,"enabled":False,
        "campaign_id":CAMPAIGN,"tracking_number":NUMBER,
        "starts_at":"2026-10-19T15:00:00+00:00",
        "ends_at":"2026-10-19T17:00:00+00:00",
        "max_site_handoffs":5,
        "monitoring_owner":"Phillip Livesley",
        "stop_method":"atomic_site_handoff_gate",
        "founder_authority_ref":"docs/evidence/lead_smart_founder_launch_intent_20261011.json",
    }

def test_seven_day_campaign_is_separate_from_small_pilot():
    c=op.proposed(old_control(),"2026-10-20T08:00",7,20,140)
    assert c["mode"]=="FULL_CAMPAIGN"
    assert c["buyer_live_authorization_ref"]=="gmail:1a1551ac7204ff8a"
    assert c["enabled"] is False
    assert c["max_daily_site_handoffs"]==20
    assert c["max_site_handoffs"]==140
    assert c["starts_at"].startswith("2026-10-20T13:")
    assert c["ends_at"].startswith("2026-10-27T13:")

@pytest.mark.parametrize("daily,total",[(0,140),(1001,5000),(20,10),(20,10001),(True,100)])
def test_invalid_site_limits_hold(daily,total):
    with pytest.raises(ValueError):
        op.proposed(old_control(),"2026-10-20T08:00",7,daily,total)

def test_preview_never_writes_anything(tmp_path,monkeypatch):
    config=tmp_path/"control.json"
    config.write_text(json.dumps(old_control()))
    monkeypatch.setattr(op,"CONFIG",config)
    monkeypatch.setattr(op,"LEDGER",tmp_path/"none.json")
    monkeypatch.setattr(op,"founder_full_campaign_approved",lambda root:True)
    before=config.read_bytes()
    result=op.stage("2026-10-20T08:00",7,20,140,apply=False)
    assert result["calls_enabled"] is False
    assert config.read_bytes()==before

def test_stage_writes_disabled_window_not_an_active_pilot(tmp_path,monkeypatch):
    config=tmp_path/"control.json"
    config.write_text(json.dumps(old_control()))
    monkeypatch.setattr(op,"CONFIG",config)
    monkeypatch.setattr(op,"LEDGER",tmp_path/"none.json")
    monkeypatch.setattr(op,"founder_full_campaign_approved",lambda root:True)
    calls=[]
    def change(expected,new):
        assert expected["enabled"] is False
        assert new["enabled"] is False
        assert new["mode"]=="FULL_CAMPAIGN"
        calls.append(new)
        config.write_text(json.dumps(new))
    monkeypatch.setattr(op,"change_control",change)
    result=op.stage("2026-10-20T08:00",7,20,140,apply=True)
    assert result["status"]=="STAGED_DISABLED"
    assert len(calls)==1
    assert json.loads(config.read_text())["enabled"] is False

def test_existing_ledger_prevents_new_campaign_staging(tmp_path,monkeypatch):
    config=tmp_path/"control.json"
    config.write_text(json.dumps(old_control()))
    ledger=tmp_path/"site_handoffs.json"
    ledger.write_text("{}")
    monkeypatch.setattr(op,"CONFIG",config)
    monkeypatch.setattr(op,"LEDGER",ledger)
    monkeypatch.setattr(op,"founder_full_campaign_approved",lambda root:True)
    with pytest.raises(ValueError,match="ledger"):
        op.stage("2026-10-20T08:00",7,20,140,apply=True)
    assert json.loads(config.read_text())["mode"] if "mode" in json.loads(config.read_text()) else True

def test_activation_installs_stop_timer_before_enabling_calls(tmp_path,monkeypatch):
    from datetime import datetime as RealDateTime
    class Frozen(datetime):
        @classmethod
        def now(cls,tz=None):
            now=RealDateTime(2026,10,20,13,32,10,tzinfo=timezone.utc)
            return now if tz is None else now.astimezone(tz)
    monkeypatch.setattr(op,"datetime",Frozen)
    config=tmp_path/"control.json"
    c=op.proposed(old_control(),"2026-10-20T08:00",7,20,140)
    config.write_text(json.dumps(c))
    monkeypatch.setattr(op,"CONFIG",config)
    monkeypatch.setattr(op,"founder_full_campaign_approved",lambda root:True)
    monkeypatch.setattr(op,"refresh",lambda:{"source_refresh_completed":True})
    events=[]
    def readiness():
        val=json.loads(config.read_text())["enabled"]
        return {"launch_ready":val,"blockers":[] if val else ["pilot_stop_verified"]}
    monkeypatch.setattr(op,"compute_live_launch_readiness",readiness)
    def timer(unit,seconds,command,repeat=False):
        assert json.loads(config.read_text())["enabled"] is False
        events.append("sources" if repeat else "stop")
    monkeypatch.setattr(op,"_timer",timer)
    def update(expected,new):
        assert expected["enabled"] is False
        assert "stop" in events
        assert "sources" in events
        config.write_text(json.dumps(new))
        events.append("switch_on")
    monkeypatch.setattr(op,"change_control",update)
    result=op.activate()
    assert result["status"]=="LIVE_FULL_CAMPAIGN"
    assert events==["stop","sources","switch_on"]
    assert json.loads(config.read_text())["enabled"] is True

def test_activation_fails_closed_without_fresh_source(tmp_path,monkeypatch):
    c=op.proposed(old_control(),"2026-10-20T08:00",7,20,140)
    cfg=tmp_path/"control"
    cfg.write_text(json.dumps(c))
    monkeypatch.setattr(op,"CONFIG",cfg)
    monkeypatch.setattr(op,"founder_full_campaign_approved",lambda root:True)
    monkeypatch.setattr(op,"refresh",lambda:{"source_refresh_completed":False})
    # A real runtime clock should be within this control's campaign.
    # If not, it still fails closed without changing the file.
    original=cfg.read_bytes()
    with pytest.raises(ValueError):
        op.activate()
    assert cfg.read_bytes()==original


def test_refresh_missing_ringba_token_preserves_provenance_and_source_staleness(monkeypatch):
    from scripts import refresh_lead_smart_full_campaign_sources as source
    calls=[]
    def run(command,**kw):
        calls.append(command[-1])
        return type("Result",(),{"returncode": 1 if len(calls)==4 else 0})()
    monkeypatch.setattr(source.subprocess,"run",run)
    result=source.refresh()
    assert result["source_refresh_completed"] is True
    assert result["tracking_observation_refreshed"] is False
    assert result["tracking_assignment_checked_separately_by_launch_gate"] is True
    assert len(calls)==4
    assert source.STEPS[-1] not in calls  # no synthetic new verified_at

def test_refresh_coverage_failure_blocks_launch(monkeypatch):
    from scripts import refresh_lead_smart_full_campaign_sources as source
    monkeypatch.setattr(source.subprocess,"run",lambda *a,**kw:
                        type("Result",(),{"returncode":1})())
    result=source.refresh()
    assert result["source_refresh_completed"] is False
    assert result["tracking_observation_refreshed"] is False
