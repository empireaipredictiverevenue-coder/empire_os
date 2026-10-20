"""Complete, redacted, no-write Exchange supply triage."""
from copy import deepcopy
from datetime import datetime,timezone
import json
import os
import subprocess
import sys

from empire_os.exchange_inventory_owner_triage_v1 import (
    review_exchange_inventory_for_owner,redacted_founder_summary,
)
from tests.exchange_snapshot_fixture_20261020 import fixture,NOW


def triage_source():
    d=fixture()
    d["inventory"][0]["reason"]="market_identity_missing"
    d["inventory"][1]["reason"]="no_eligible_buyer_capacity"
    d["inventory"][2]["state"]="blocked_missing_evidence"
    d["inventory"][2]["reason"]="missing_active_identity_link"
    d["inventory"][3]["state"]="blocked_missing_evidence"
    d["inventory"][3]["reason"]="missing_active_identity_link"
    d["inventory_state_counts"]={"blocked_missing_evidence":3,"overflow_no_capacity":1}
    d["allocated_count"]=0
    d["allocation_candidate_count"]=0
    d["blocked_missing_evidence_count"]=3
    d["buyer_seats"][0]["seat_state"]="blocked_missing_evidence"
    d["seat_state_counts"]={"blocked_missing_evidence":1}
    return d


def test_complete_per_row_worklist_is_not_qualification():
    s=triage_source()
    x=review_exchange_inventory_for_owner(s,now=NOW)
    assert x["state"]=="ALL_SELECTED_RECORDS_TRIAGED_NOT_COMMERCIAL_VERIFIED"
    assert x["records_reviewed"]==4
    assert x["unique_prospects_checked"]==4
    assert len(x["owner_tasks"])==4
    assert x["blocker_counts"]=={"IDENTITY_MARKET":1,"IDENTITY_LINK":2,"BUYER_CAPACITY":1}
    assert x["buyer_seat_records_reviewed"]==1
    assert x["leads_verified_sellable"]==0
    assert x["verified_buyer_capacity"]==0
    assert x["authorized_outbound"] is False
    assert x["crm_writes"] is False
    for task in x["owner_tasks"]:
        assert task["independent_identity_verified"] is False
        assert task["buyer_capacity_verified"] is False
        assert task["consent_and_transfer_rights_verified"] is False
    public=json.dumps(redacted_founder_summary(x))
    assert "canonical_prospect_id_private" not in public
    assert "prospect-synthetic" not in public
    assert "task_id" not in public


def test_missing_evidence_and_ambiguous_capacity_are_holds():
    cases=(
        ("duplicate",lambda d:d["inventory"][0].update(
            prospect_id=d["inventory"][1]["prospect_id"])),
        ("forged_ready",lambda d:d["inventory"][1].update(
            state="allocation_candidate",reason="approved")),
        ("unknown_reason",lambda d:d["inventory"][1].update(reason="fraud_verified")),
        ("active_seat",lambda d:d["buyer_seats"][0].update(seat_state="active_capacity")),
        ("count_drift",lambda d:d.update(inventory_count=300)),
        ("bad_capacity_route",lambda d:d["inventory"][1].update(corridor_key=None)),
    )
    for name,change in cases:
        s=triage_source()
        change(s)
        x=review_exchange_inventory_for_owner(s,now=NOW)
        assert x["state"]=="HOLD",name
        assert x["records_reviewed"]==0
        assert x["authorized_outbound"] is False


def test_stale_source_and_foreign_backend_not_release():
    s=triage_source()
    assert review_exchange_inventory_for_owner(
        s,now=datetime(2026,10,22,tzinfo=timezone.utc))["state"]=="HOLD"
    s["canonical_backend"]="supabase"
    assert review_exchange_inventory_for_owner(s,now=NOW)["state"]=="HOLD"


def test_private_0600_cli_no_ids_in_stdout(tmp_path):
    s=triage_source()
    s["observed_at"]=datetime.now(timezone.utc).isoformat()
    p=tmp_path/"snapshot.json"
    p.write_text(json.dumps(s))
    out=tmp_path/"owner_triage.json"
    cmd=[sys.executable,"-B","-m",
         "scripts.review_exchange_inventory_all_selected_20261020",
         "--read-only","--snapshot",str(p),
         "--write-owner-local","--owner-output",str(out)]
    r=subprocess.run(cmd,text=True,capture_output=True,check=False,timeout=20,
                     env={**os.environ,"PYTHONPATH":str(__import__("pathlib").Path(__file__).resolve().parents[1])})
    assert r.returncode==0,r.stderr
    summary=json.loads(r.stdout)
    assert summary["records_reviewed"]==4
    assert "prospect-synthetic" not in r.stdout
    assert out.exists()
    assert out.stat().st_mode & 0o777==0o600
    private=json.loads(out.read_text())
    assert len(private["owner_tasks"])==4
    assert private["records_reviewed"]==4
