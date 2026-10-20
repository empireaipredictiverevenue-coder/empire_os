"""Guarded root Ringba scheduling must never call provider outside active campaign."""
from datetime import datetime,timezone
import json
from pathlib import Path
from scripts import refresh_lead_smart_ringba_if_campaign_active_20261020 as mod

NOW=datetime(2026,10,20,15,0,tzinfo=timezone.utc)
def record(enabled=True):
    return {"schema_version":"empire.lead_smart.site_handoff_control.v1",
            "campaign_id":mod.CAMPAIGN,"tracking_number":mod.NUMBER,
            "enabled":enabled,"mode":"FULL_CAMPAIGN",
            "buyer_live_authorization_ref":mod.SOURCE,
            "traffic_source":"EMPIRE_FIRST_PARTY_ORGANIC",
            "ends_at":"2026-10-27T13:00:00+00:00"}

def setup(tmp_path,monkeypatch,value):
    p=tmp_path/"control.json";p.write_text(json.dumps(value))
    monkeypatch.setattr(mod.os,"geteuid",lambda:0)
    return p

def test_live_refresh_uses_restricted_provider_only(tmp_path,monkeypatch):
    p=setup(tmp_path,monkeypatch,record())
    calls=[]
    def refresh(*,apply):
        calls.append(apply)
        return {"status":"TRACKING_FRESH_NO_CALL_AUTHORITY","tracking_verification_refreshed":True}
    r=mod.run(path=p,now=NOW,refresher=refresh)
    assert r["status"]=="TRACKING_REFRESHED"
    assert calls==[True]
    assert r["credential_exposed"] is False

def test_disabled_or_expired_never_contacts_provider(tmp_path,monkeypatch):
    for value,clock in ((record(False),NOW),
                        (record(),datetime(2026,10,27,15,tzinfo=timezone.utc)),
                        ({**record(),"campaign_id":"other"},NOW),
                        ({**record(),"traffic_source":"PAID_SEARCH"},NOW)):
        p=setup(tmp_path,monkeypatch,value)
        def failure(*,apply):
            raise AssertionError("provider should not be contacted")
        assert mod.run(path=p,now=clock,refresher=failure)["status"]=="INACTIVE_NO_PROVIDER_REQUEST"

def test_untrusted_or_unprivileged_stops(tmp_path,monkeypatch):
    p=setup(tmp_path,monkeypatch,record())
    monkeypatch.setattr(mod.os,"geteuid",lambda:1000)
    assert mod.run(path=p,now=NOW)["status"]=="HOLD_RESTRICTED_ROOT_ONLY"
    monkeypatch.setattr(mod.os,"geteuid",lambda:0)
    p.write_text("not-json")
    assert mod.run(path=p,now=NOW)["status"]=="HOLD_UNTRUSTED_CONTROL"

def test_provider_failure_does_not_claim_freshness(tmp_path,monkeypatch):
    p=setup(tmp_path,monkeypatch,record())
    result=mod.run(path=p,now=NOW,refresher=lambda *,apply:{"status":"HOLD_PROVIDER_OR_SOURCE_UNVERIFIED"})
    assert result["status"]=="PROVIDER_REFRESH_UNVERIFIED"
