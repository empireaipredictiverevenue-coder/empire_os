"""The one-hit Ringba diagnosis consumes privileged config without leaking it."""
from types import SimpleNamespace
import json
import pytest

from scripts import probe_lead_smart_ringba_root_readonly as mod
from empire_os import lead_smart_ringba_api_observer as api
from empire_os import lead_smart_ringba_tracking_observer as tracking
from empire_os import lead_smart_ringba_routing_observer as routing

class Config:
    def __init__(self,body,*,mode=0o100600,uid=0,gid=0,symlink=False):
        self.body=body
        self.mode=mode
        self.uid=uid
        self.gid=gid
        self.symlink=symlink
    def is_symlink(self):return self.symlink
    def stat(self):
        return SimpleNamespace(st_mode=self.mode,st_uid=self.uid,
                               st_gid=self.gid,st_size=len(self.body))
    def read_text(self,encoding):return self.body

def test_root_owned_config_accepts_only_known_literals():
    conf=mod.read_root_config(Config(
        "export RINGBA_API_TOKEN='redacted_test_secret'\n"
        "RINGBA_ACCOUNT_ID=RAtest\n",
    ),euid=0)
    assert conf["RINGBA_API_TOKEN"]=="redacted_test_secret"
    assert conf["RINGBA_ACCOUNT_ID"]=="RAtest"

@pytest.mark.parametrize("conf",[
    Config("RINGBA_API_TOKEN=secret",mode=0o100644),
    Config("RINGBA_API_TOKEN=secret",uid=1000),
    Config("RINGBA_API_TOKEN=secret",gid=1000),
    Config("RINGBA_API_TOKEN=secret",symlink=True),
    Config("RINGBA_API_TOKEN=$(whoami)"),
    Config("RINGBA_API_TOKEN=secret\nCUSTOM=value\n"),
    Config("RINGBA_API_TOKEN=secret\nRINGBA_API_TOKEN=other\n"),
    Config("RINGBA_ACCOUNT_ID=RAtest"),
])
def test_any_unsafe_or_unsupported_root_config_fails_closed(conf):
    with pytest.raises(mod.RingbaPreflightHold):
        mod.read_root_config(conf,euid=0)

def test_unprivileged_reader_must_not_read_protected_file():
    with pytest.raises(mod.RingbaPreflightHold,match="PRIVILEGED"):
        mod.read_root_config(Config("RINGBA_API_TOKEN=secret"),euid=1000)

def test_account_selected_once_then_three_read_only_evidence_calls():
    steps=[]
    def accounts(token):
        steps.append("account")
        assert token=="hidden_token_123"
        return ["RAtest"]
    def choose(ids,hint):
        assert ids==["RAtest"] and hint=="RAtest"
        return "RAtest"
    def logs(**kw):
        steps.append("calllogs")
        return {"results":[]},{"api_role":"affiliate"}
    def log_builder(**kw):
        return {
            "schema_version":api.SCHEMA_VERSION,
            "exact_campaign_and_number_match_count":0,
        }
    def track(**kw):
        steps.append("tracking")
        return {
            "schema_version":tracking.SCHEMA_VERSION,
            "provider_binding_verified":True,
        }
    def routes(**kw):
        steps.append("routing")
        return {
            "schema_version":routing.SCHEMA_VERSION,
            "call_routes_endpoint":{"status":403,"accessible":False},
            "route_visibility":{"scope":"FORBIDDEN_NO_ROUTE_ABSENCE_INFERENCE"},
        }
    r=mod.run_once(
        "hidden_token_123","RAtest",discover_accounts=accounts,
        choose_account=choose,fetch_logs=logs,build_logs=log_builder,
        tracking_observer=track,routing_observer=routes,
    )
    assert steps==["account","calllogs","tracking","routing"]
    assert r["routing_evidence"]["call_routes_http_status"]==403
    assert r["status"]=="OBSERVATION_COMPLETE_LAUNCH_HELD"
    assert not r["routing_evidence"]["buyer_route_live_proven"]
    assert r["tracking_evidence"]["provider_number_campaign_binding"]
    assert r["launch_authorized"] is False
    assert r["execution_authority"]=="NONE"
    assert not r["test_call_performed"]
    assert "hidden_token_123" not in json.dumps(r)
    assert "RAtest" not in json.dumps(r)

def test_partial_provider_failure_is_sanitised_and_no_approval():
    def failed(**kw):
        raise ValueError("Authorization Token abc123 secret_account_id RA123")
    r=mod.run_once(
        "abc123","RA123",
        discover_accounts=lambda token:["RA123"],
        choose_account=lambda ids,hint:"RA123",
        fetch_logs=failed,
        tracking_observer=failed,
        routing_observer=failed,
    )
    assert r["status"]=="PROVIDER_EVIDENCE_INCOMPLETE"
    assert r["call_log_evidence"]["status"]=="UNVERIFIED"
    assert r["routing_evidence"]["status"]=="UNVERIFIED"
    assert not r["launch_authorized"]
    assert "abc123" not in json.dumps(r)
    assert "RA123" not in json.dumps(r)
    assert "secret_account_id" not in json.dumps(r)

def test_ambiguous_account_scope_fail_closed_without_any_probes():
    r=mod.run_once(
        "notprinted",None,
        discover_accounts=lambda token:["RAone","RAtwo"],
        choose_account=lambda ids,hint:(_ for _ in ()).throw(ValueError("ambiguous")),
        fetch_logs=lambda **kw: (_ for _ in ()).throw(AssertionError("no probes")),
    )
    assert r["status"]=="ACCOUNT_SCOPE_UNVERIFIED"
    assert r["execution_authority"]=="NONE"
