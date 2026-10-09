from datetime import date, datetime, timezone
import json
from pathlib import Path

import pytest

import scripts.materialize_company_routed_buyer_review as existing
import scripts.refresh_contractor_revenue_review as contractor
from empire_os.storm_contractor_review import build_contractor_review

ROOT = Path(__file__).resolve().parents[1]


def test_existing_authorized_runner_reuses_one_db_history_read(monkeypatch, tmp_path, capsys):
    src = tmp_path / "buyer.json"
    out = tmp_path / "buyer-output.json"
    src.write_text(json.dumps({"row": {"company_domain": "sample.example.com"}}))
    monkeypatch.setattr(existing, "SOURCE", src)
    monkeypatch.setattr(existing, "OUTPUT", out)
    calls = {"db":0, "contractor":0}
    def read_history():
        calls["db"] += 1
        return set(), {"maxexteriors.com"}, {"person@spcroofs.com"}
    def buyer_review(*args, **kwargs):
        return {
            "schema_version": "empire.company-routed-buyer-review.v1",
            "candidate_count": 0, "review_ready_count": 0,
            "ambiguous_person_count": 0, "no_same_domain_person_count": 0,
            "prior_contact_history_count": 0, "suppressed_route_count": 0,
            "items": [], "outbound_authorized": False,
        }
    def reviewer(*, as_of, now):
        calls["contractor"] += 1
        assert isinstance(as_of, date)
        return {
            "schema":"empire.revenue_strike.contractor_founder_review.v1",
            "mode":"OBSERVE", "as_of":as_of.isoformat(),
            "summary":{"historical_contractor_companies":2,"approved_outbound_count":0,"verified_payments":0},
            "packets":[
                {"company_domain":"maxexteriors.com", "review_tasks":[],
                 "outbound_authorized":False, "founder_review_ready":False},
                {"company_domain":"spcroofs.com", "review_tasks":[],
                 "outbound_authorized":False, "founder_review_ready":False},
            ], "outbound_authorized": False,
            "contract_sent": False, "execution_authority":"none",
        }
    monkeypatch.setattr(existing, "_canonical_contact_history", read_history)
    monkeypatch.setattr(existing, "build_company_routed_review_queue", buyer_review)
    monkeypatch.setattr(contractor, "run", reviewer)
    contractor_output = tmp_path / "contractor-output.json"
    monkeypatch.setattr(contractor, "OUTPUT", contractor_output)
    assert existing.main() == 0
    assert calls == {"db":1, "contractor":1}
    buyer = json.loads(out.read_text())
    assert buyer["history_guard_ok"] is True
    packet = json.loads(contractor_output.read_text())
    assert packet["canonical_domain_history_observed"] is True
    assert packet["summary"]["prior_outbound_domain_review_holds"] == 1
    assert packet["summary"]["suppressed_domain_contact_holds"] == 1
    assert packet["canonical_domain_history_read_at"]
    assert packet["packets"][0]["contact_history_state"] == "PRIOR_OUTBOUND_DOMAIN_REVIEW_HOLD"
    assert packet["packets"][1]["contact_history_state"] == "SUPPRESSED_DOMAIN_CONTACT_HOLD"
    assert all(p["recipient_level_suppression_verified"] is False for p in packet["packets"])
    assert all(p["outbound_authorized"] is False for p in packet["packets"])
    assert contractor_output.stat().st_mode & 0o777 == 0o600
    result=json.loads(capsys.readouterr().out)
    assert result["contractor_history_state"] == "CANONICAL_DOMAIN_HISTORY_OBSERVED"
    assert result["contractor_named_recipients_cleared"] == 0
    assert result["contractor_outbound_authorized"] is False
    assert "person@" not in str(result)


def test_existing_runner_fails_closed_if_no_authorized_db(monkeypatch,tmp_path,capsys):
    src=tmp_path/"source.json"; src.write_text("{}")
    out=tmp_path/"buyer-review.json"
    monkeypatch.setattr(existing,"SOURCE",src)
    monkeypatch.setattr(existing,"OUTPUT",out)
    def fail_db():
        raise RuntimeError("NO_OWNED_READER")
    monkeypatch.setattr(existing,"_canonical_contact_history",fail_db)
    def must_not_run(**kwargs):
        raise AssertionError("Must not construct contractor review if DB not authenticated")
    monkeypatch.setattr(existing,"refresh_existing_contractor_history",must_not_run)
    assert existing.main()==0
    assert json.loads(out.read_text())["history_guard_ok"] is False
    result=json.loads(capsys.readouterr().out)
    assert result["contractor_history_state"]=="BLOCKED_CANONICAL_HISTORY_UNAVAILABLE"
    assert result["contractor_named_recipients_cleared"]==0


def test_existing_runner_does_not_promote_if_contractor_dossier_invalid(monkeypatch,tmp_path,capsys):
    src=tmp_path/"source.json"; src.write_text("{}")
    out=tmp_path/"buyer-review.json"
    monkeypatch.setattr(existing,"SOURCE",src)
    monkeypatch.setattr(existing,"OUTPUT",out)
    monkeypatch.setattr(existing,"_canonical_contact_history",lambda:(set(),set(),set()))
    monkeypatch.setattr(existing,"build_company_routed_review_queue",lambda *args,**kwargs:{
        "candidate_count":0,"review_ready_count":0,"ambiguous_person_count":0,
        "no_same_domain_person_count":0,"prior_contact_history_count":0,
        "suppressed_route_count":0,"outbound_authorized":False,
    })
    def fail_bridge(**kwargs): raise ValueError("BAD_CONTRACTOR_EVIDENCE")
    monkeypatch.setattr(existing,"refresh_existing_contractor_history",fail_bridge)
    assert existing.main()==0
    assert json.loads(out.read_text())["history_guard_ok"] is True
    result=json.loads(capsys.readouterr().out)
    assert result["contractor_history_state"]=="BLOCKED_ValueError"
    assert result["contractor_outbound_authorized"] is False


def test_writer_refuses_outbound_authority(monkeypatch,tmp_path):
    monkeypatch.setattr(contractor,"OUTPUT",tmp_path/"contractor.json")
    for key in ("outbound_authorized","contract_sent"):
        row={"schema":"empire.revenue_strike.contractor_founder_review.v1",
             "mode":"OBSERVE","outbound_authorized":False,"contract_sent":False,
             "execution_authority":"none"}
        row[key]=True
        with pytest.raises(ValueError,match="UNSAFE"):
            contractor.write_review_snapshot(row)
    assert not (tmp_path/"contractor.json").exists()


def test_writer_refuses_symlink_target(monkeypatch,tmp_path):
    target=tmp_path/"secret.json";target.write_text("preserve")
    sym=tmp_path/"contractor.json";sym.symlink_to(target)
    monkeypatch.setattr(contractor,"OUTPUT",sym)
    row={"schema":"empire.revenue_strike.contractor_founder_review.v1",
         "mode":"OBSERVE","outbound_authorized":False,"contract_sent":False,
         "execution_authority":"none"}
    with pytest.raises(ValueError,match="LOCATION"):
        contractor.write_review_snapshot(row)
    assert target.read_text()=="preserve"
