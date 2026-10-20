"""Bounded one-hit tracking freshness: no buyer route, call or funds authority."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest

from scripts import refresh_lead_smart_ringba_tracking_root_once_20261019 as mod
from tests.test_lead_smart_tracking_verification import observation

NOW=datetime(2026,10,19,13,40,tzinfo=timezone.utc)

def sample():
    fields={key:None for key in mod.SOURCE_KEYS}
    fields.update(observation(
        observed_at=(NOW-timedelta(seconds=2)).isoformat(),
        raw_provider_payload_persisted=False,
        api_token_persisted=False,
        account_id_persisted=False,
        commercial_activation=False,
        revenue_recognized=False,
    ))
    return fields

def simulated(tmp_path, monkeypatch, data=None):
    data=sample() if data is None else data
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod.os,"geteuid",lambda:0)
    a=tmp_path/"tracking_observation/latest.json"
    b=tmp_path/"tracking_verification/latest.json"
    for p in (a,b):
        p.parent.mkdir()
        p.write_text('{"prior":"evidence"}\n')
    steps=[]
    def creds():
        steps.append("credential")
        return {"RINGBA_API_TOKEN":"secret_token_redacted","RINGBA_ACCOUNT_ID":"RAtest"}
    def accounts(token):
        assert token=="secret_token_redacted"
        steps.append("account")
        return ["RAtest"]
    def choose(ids,hint):
        assert ids==["RAtest"] and hint=="RAtest"
        return hint
    def observer(**args):
        assert args=={"token":"secret_token_redacted","account_id":"RAtest"}
        steps.append("tracking")
        return data
    def invoke(apply):
        return mod.refresh(
            apply=apply, observer=observer, credential_reader=creds,
            accounts_reader=accounts,account_chooser=choose,
            current_root=tmp_path, observed_at=NOW,
            observation_path=a, verification_path=b,
        )
    return a,b,steps,invoke

def test_bounded_source_promotes_only_tracking_verification():
    source,proof=mod.checked_payloads(sample(),now=NOW)
    data=json.loads(proof)
    assert data["source_sha256"]==hashlib.sha256(source).hexdigest()
    assert data["tracking_verified"] is True
    assert data["routing_verified"] is False
    assert data["routing_enabled"] is False
    assert data["traffic_enabled"] is False
    assert data["execution_authority"]=="NONE"

@pytest.mark.parametrize("field,value",[
    ("provider_binding_verified",False),
    ("tracking_verification_candidate",False),
    ("api_token_persisted",True),
    ("account_id_persisted",True),
    ("raw_provider_payload_persisted",True),
    ("traffic_enabled",True),
    ("routing_enabled",True),
    ("commercial_activation",True),
    ("revenue_recognized",True),
    ("execution_authority","LIVE_TRAFFIC"),
    ("schema_version","wrong"),
    ("campaign_id","wrong"),
    ("tracking_number","+11111111111"),
    ("direct_campaign_binding",False),
    ("observed_at","2026-10-12T13:40:00+00:00"),
    ("credentials", "secret_token_must_not_persist"),
])
def test_untrusted_tracking_never_creates_verification(field,value):
    bad=sample()
    bad[field]=value
    with pytest.raises(ValueError):
        mod.checked_payloads(bad,now=NOW)

def test_dry_run_reads_provider_once_without_writes(tmp_path,monkeypatch):
    a,b,steps,invoke=simulated(tmp_path,monkeypatch)
    before=(a.read_bytes(),b.read_bytes())
    d=invoke(False)
    assert d["status"]=="FRESH_TRACKING_OBSERVABLE_NO_WRITES"
    assert d["tracking_verification_refreshed"] is False
    assert (a.read_bytes(),b.read_bytes())==before
    assert steps==["credential","account","tracking"]
    assert "secret" not in json.dumps(d)
    assert "RAtest" not in json.dumps(d)

def test_apply_refreshes_only_two_existing_tracking_files(tmp_path,monkeypatch):
    a,b,steps,invoke=simulated(tmp_path,monkeypatch)
    d=invoke(True)
    assert d["status"]=="TRACKING_FRESH_NO_CALL_AUTHORITY"
    assert d["tracked_campaign_binding_verified"] is True
    assert d["tracking_verification_refreshed"] is True
    assert d["buyer_route_independently_verified"] is False
    assert d["buyer_leg_connected"] is False
    assert d["traffic_enabled"] is False
    assert d["call_admission_authorized"] is False
    assert d["credentials_persisted"] is False
    assert steps==["credential","account","tracking"]
    assert json.loads(b.read_bytes())["source_sha256"]==hashlib.sha256(a.read_bytes()).hexdigest()
    assert "secret" not in a.read_text()+b.read_text()
    assert "RAtest" not in a.read_text()+b.read_text()
    assert sorted(x.name for x in a.parent.iterdir())==["latest.json"]
    assert sorted(x.name for x in b.parent.iterdir())==["latest.json"]

def test_missing_or_symlinked_snapshot_stops_before_credentials(tmp_path,monkeypatch):
    a,b,steps,invoke=simulated(tmp_path,monkeypatch)
    a.unlink()
    a.symlink_to(tmp_path/"unrelated.txt")
    d=invoke(True)
    assert d["status"]=="HOLD_PROVIDER_OR_SOURCE_UNVERIFIED"
    assert steps==[]
    assert not b.read_text().find('"prior"') == -1

def test_nonroot_never_reads_secret(tmp_path,monkeypatch):
    a,b,steps,invoke=simulated(tmp_path,monkeypatch)
    monkeypatch.setattr(mod.os,"geteuid",lambda:1000)
    d=invoke(True)
    assert d["status"]=="HOLD_ROOT_OR_CANONICAL_CWD_REQUIRED"
    assert steps==[]
