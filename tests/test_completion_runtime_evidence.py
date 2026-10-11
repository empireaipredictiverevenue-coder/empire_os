"""One-shot operational readback, immutable task memory, zero closure authority."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from pathlib import Path
import json
import subprocess

import pytest
from empire_os.completion_runtime_evidence import (
    TASKS, RuntimeObservationError, observe_existing_runtime,
)
from empire_os.completion_task_memory import (
    AttemptMemoryError,load_attempt_memory,record_attempt,preflight_task,task_key,
)
from empire_os.completion_reconciliation import refresh_completion_reconciliation
from empire_os.completion_task_monitor import build_completion_task_monitor
from empire_os.master_execution_ledger import parse_checklist

NOW=datetime(2026,10,11,20,30,tzinfo=timezone.utc)
SECTION="Opportunity Radar / Factory"
NAMES=list(TASKS)
ROUTER_TIME=(NOW-timedelta(seconds=80)).isoformat()
ASTRA_TIME=(NOW-timedelta(seconds=20)).isoformat()
DAILY_TIME=(NOW-timedelta(seconds=30)).isoformat()


def put(root,name,data):
    path=root/"runtime"/name
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data))
    return path


def fixture(root):
    router={
        "schema_version":"empire.opportunity_evidence_routes.v1",
        "generated_at":ROUTER_TIME,"mode":"OBSERVE",
        "execution_authority":"none",
        "automatic_external_execution_allowed":False,
        "opportunity_count":1,
        "stage_counts":{"QUALIFY":1},
        "history":{
            "schema_version":"empire.opportunity_evidence_history.v1",
            "generated_at":ROUTER_TIME,
            "mode":"OBSERVE","execution_authority":"none",
            "automatic_external_execution_allowed":False,
            "commercial_stage_independently_verified":False,
            "previous_stage_never_promoted":True,
            "active_identity_count":1,
            "new_identity_count":0,
            "stage_transition_count_this_cycle":0,
        }
    }
    astra={
        "schema_version":"empire.astra.executive.v2",
        "generated_at":ASTRA_TIME,
        "execution_authority":"none",
        "commercial_authority":"none",
        "external_execution_performed":False,
        "validated_opportunity_count":0,
        "validated_workstream_ranking":{
            "schema_version":"empire.astra.validated_workstream_ranking.v1",
            "status":"RANKED_FROM_CURRENT_DERIVED_VALIDATION",
            "mode":"OBSERVE","execution_authority":"none",
            "commercial_authority":"none",
            "automatic_external_execution_allowed":False,
            "source_validation_is_not_buyer_acceptance":True,
            "validated_opportunity_count":0,
        }
    }
    daily={
        "schema_version":"empire.daily_results.v1",
        "generated_at":DAILY_TIME,
        "execution_authority":"none",
        "opportunity_daily":{
            "schema_version":"empire.daily_results.opportunity_activity.v1",
            "mode":"OBSERVE","execution_authority":"none",
            "external_execution_performed":False,
            "forecast_as_realized_revenue":False,
            "coverage":"LATEST_COMPLETED_CYCLE_ONLY_NOT_DAILY_TOTAL",
            "advanced":{"commercial_promotion_verified":False},
            "proved":{
                "status":"CANONICAL_OUTCOME_EVENT_FEED_NOT_BOUND",
                "verified_commercial_outcomes_today":None
            },
        },
    }
    founder={
        "opportunity_radar":{
            "lifecycle_evidence":{
                "schema_version":"empire.founder_radar_lifecycle_evidence.v1",
                "status":"CURRENT_DERIVED_HISTORY_OBSERVED",
                "history_verified_for_cycle":True,
                "router_opportunity_count":1,
                "router_stage_counts":{"QUALIFY":1},
                "router_observed_at":ROUTER_TIME,
                "new_identity_count_latest_cycle":0,
                "derived_stage_transitions_latest_cycle":0,
                "execution_authority":"none",
                "commercial_validation_verified":False,
                "outreach_authorized":False,
            }
        }
    }
    for name,data in (
        ("opportunity_factory/evidence_routes_latest.json",router),
        ("astra/executive_latest.json",astra),
        ("daily_results/latest.json",daily),
    ):put(root,name,data)
    api={
        "/v1/founder-dashboard/overview":founder,
        "/v1/founder-daily-results/latest":daily,
    }
    return router,astra,daily,api


def observe(root,task,api):
    return observe_existing_runtime(
        root,task,now=NOW,fetch_local=lambda p:api[p],
    )


def test_three_existing_sources_valid_and_no_unapproved_side_effects(tmp_path):
    _,_,_,api=fixture(tmp_path)
    before={str(x):x.read_bytes() for x in (tmp_path/"runtime").rglob("*") if x.is_file()}
    for task in NAMES:
        o=observe(tmp_path,task,api)
        assert o["status"]=="RUNTIME_OBSERVED"
        assert o["task"]==task
        assert o["checklist_closure_verified"] is False
        assert o["independent_customer_revenue_verified"] is False
        assert o["execution_authority"]=="none"
        assert len(o["evidence_refs"])>=2
        assert all(x.startswith(("runtime:","verification:")) for x in o["evidence_refs"])
    assert before=={str(x):x.read_bytes() for x in (tmp_path/"runtime").rglob("*") if x.is_file()}


@pytest.mark.parametrize("bad",[
    ("router","history",None),
    ("router","automatic_external_execution_allowed",True),
    ("router","generated_at","2026-10-10T20:01:00+00:00"),
    ("router","opportunity_count",True),
    ("astra","commercial_authority","send"),
    ("astra","validated_opportunity_count",True),
    ("astra","generated_at","2026-10-11T18:01:00+00:00"),
])
def test_astra_stale_spoofed_or_unsafe_proof_fails(bad,tmp_path):
    router,astra,_,api=fixture(tmp_path)
    source,field,value=bad
    path=("opportunity_factory/evidence_routes_latest.json"
          if source=="router" else "astra/executive_latest.json")
    entry=router if source=="router" else astra
    entry[field]=value
    put(tmp_path,path,entry)
    with pytest.raises(RuntimeObservationError):
        observe(tmp_path,NAMES[0],api)


@pytest.mark.parametrize(("field","value"),[
    ("history_verified_for_cycle",False),
    ("router_opportunity_count",7),
    ("router_observed_at","2026-10-10T00:00:00+00:00"),
    ("new_identity_count_latest_cycle",100),
    ("outreach_authorized",True),
    ("commercial_validation_verified",True),
    ("status","CURRENT_ROUTER_WITHOUT_HISTORY"),
    ("execution_authority","live"),
])
def test_founder_api_mismatch_never_becomes_runtime_evidence(field,value,tmp_path):
    _,_,_,api=fixture(tmp_path)
    api["/v1/founder-dashboard/overview"]["opportunity_radar"]["lifecycle_evidence"][field]=value
    with pytest.raises(RuntimeObservationError, match="resident_founder"):
        observe(tmp_path,NAMES[1],api)


@pytest.mark.parametrize(("field","value"),[
    ("forecast_as_realized_revenue",True),
    ("coverage","WHOLE_DAY"),
    ("execution_authority","send"),
    ("external_execution_performed",True),
])
def test_daily_unsafe_or_uncertain_proof_cannot_advance(field,value,tmp_path):
    _,_,daily,api=fixture(tmp_path)
    daily["opportunity_daily"][field]=value
    put(tmp_path,"daily_results/latest.json",daily)
    with pytest.raises(RuntimeObservationError):
        observe(tmp_path,NAMES[2],api)


def test_daily_report_api_not_exact_snapshot_must_fail(tmp_path):
    _,_,daily,api=fixture(tmp_path)
    api["/v1/founder-daily-results/latest"]=deepcopy(daily)
    api["/v1/founder-daily-results/latest"]["generated_at"]="2026-10-11T20:00:00+00:00"
    with pytest.raises(RuntimeObservationError,match="snapshot_mismatch"):
        observe(tmp_path,NAMES[2],api)


def test_unknown_task_or_failed_loopback_holds(tmp_path):
    fixture(tmp_path)
    with pytest.raises(RuntimeObservationError,match="no_existing"):
        observe_existing_runtime(tmp_path,"Other task",now=NOW)
    with pytest.raises(KeyError):
        observe_existing_runtime(
            tmp_path,NAMES[1],now=NOW,fetch_local=lambda p:{}[p]
        )


def git_fixture(root):
    (root/"docs").mkdir(parents=True,exist_ok=True)
    text="# Master\n## "+SECTION+"\n"+"".join("- [ ] "+x+"\n" for x in NAMES)
    (root/"docs/MASTER_REMAINING_CHECKLIST.md").write_text(text)
    subprocess.run(["git","init","-q"],cwd=root,check=True)
    (root/"README.md").write_text("For tests only\n")
    subprocess.run(["git","add","README.md"],cwd=root,check=True)
    subprocess.run(["git","-c","user.name=Test","-c","user.email=test@example.invalid",
                    "commit","-qm","baseline"],cwd=root,check=True)
    return subprocess.check_output(["git","rev-parse","--short=12","HEAD"],cwd=root,text=True).strip()


def code_receipts(root,sha):
    ids={}
    for name in NAMES:
        receipt=record_attempt(
            root,section=SECTION,item=name,owner="market_intelligence",
            attempt_state="CODE_VERIFIED_NOT_LIVE",
            commit=sha,
            evidence_refs=[
                f"commit:{sha}","pytest:42_passed",
                "feature_branch:feature/bounded_verified_code",
            ],now=NOW,
        )
        ids[name]=receipt["attempt_id"]
    return ids


def fake_evidence(root,task,now=None):
    return {
        "evidence_refs":["runtime:router_sha256_"+"c"*64,
                         "verification:founder_http200_sha256_"+"d"*64],
        "source_hashes":{"router":"c"*64},
        "metrics":{"observed_opportunities":1},
    }


def record_observed(root,name,sha,previous,now=NOW+timedelta(seconds=1)):
    proof=fake_evidence(root,name,now=now)
    return record_attempt(
        root,section=SECTION,item=name,owner="market_intelligence",
        attempt_state="RUNTIME_OBSERVED_PENDING_FORMAL_CLOSURE",
        reopens=previous,commit=sha,
        evidence_refs=[f"commit:{sha}",*proof["evidence_refs"]],
        now=now,
    )


def test_observed_runtime_receipt_is_immutable_and_does_not_close(tmp_path,monkeypatch):
    import empire_os.completion_runtime_evidence as evidence
    monkeypatch.setattr(evidence,"observe_existing_runtime",fake_evidence)
    sha=git_fixture(tmp_path)
    original=code_receipts(tmp_path,sha)
    event=record_observed(tmp_path,NAMES[1],sha,original[NAMES[1]])
    assert event["created"] is True
    memo=load_attempt_memory(tmp_path,now=NOW)
    assert memo["status"]=="AVAILABLE"
    assert memo["event_count"]==4
    assert memo["held_task_count"]==3
    key=task_key(SECTION,NAMES[1])
    assert memo["latest_by_task"][key]["attempt_state"]=="RUNTIME_OBSERVED_PENDING_FORMAL_CLOSURE"
    verdict=preflight_task(memo,section=SECTION,item=NAMES[1])
    assert verdict["decision"]=="HOLD"
    assert verdict["reason"]=="RUNTIME_OBSERVED_PENDING_FORMAL_CLOSURE"
    assert event["checkpoint_ref"].startswith("runtime/execution_plane/completion_checkpoints/task_memory_")
    packet=json.loads((tmp_path/event["checkpoint_ref"]).read_text())
    assert packet["stage"]=="TASK_MEMORY_EVENT"
    assert packet["live_verified"] is False
    assert packet["founder_approval_inferred"] is False
    assert packet["external_action_performed"] is False
    from empire_os.completion_closure_reconciler import _checkpoint_bindings
    assert _checkpoint_bindings(tmp_path)==({},{},{})


def test_runtime_receipt_requires_exact_prior_tested_commit(tmp_path,monkeypatch):
    import empire_os.completion_runtime_evidence as evidence
    monkeypatch.setattr(evidence,"observe_existing_runtime",fake_evidence)
    sha=git_fixture(tmp_path)
    original=code_receipts(tmp_path,sha)
    with pytest.raises(AttemptMemoryError,match="prior verified feature"):
        record_observed(tmp_path,NAMES[0],sha,"attempt_"+"0"*24)
    with pytest.raises(AttemptMemoryError,match="prior verified feature"):
        record_observed(tmp_path,NAMES[0],"a"*12,original[NAMES[0]])
    prior=original[NAMES[0]]
    with pytest.raises(AttemptMemoryError,match="source evidence mismatched"):
        record_attempt(
            tmp_path,section=SECTION,item=NAMES[0],
            owner="market_intelligence",
            attempt_state="RUNTIME_OBSERVED_PENDING_FORMAL_CLOSURE",
            reopens=prior,commit=sha,evidence_refs=[
                f"commit:{sha}",
                "runtime:router_sha256_"+"f"*64,
                "verification:founder_http200_sha256_"+"d"*64,
            ],now=NOW+timedelta(seconds=1),
        )


def test_runtime_receipt_same_time_as_prior_is_held_before_write(tmp_path,monkeypatch):
    import empire_os.completion_runtime_evidence as evidence
    monkeypatch.setattr(evidence,"observe_existing_runtime",fake_evidence)
    sha=git_fixture(tmp_path)
    original=code_receipts(tmp_path,sha)
    with pytest.raises(AttemptMemoryError,match="prior verified feature"):
        record_observed(tmp_path,NAMES[0],sha,original[NAMES[0]],now=NOW)
    assert load_attempt_memory(tmp_path,now=NOW)["event_count"]==3


def test_second_runtime_observation_does_not_resubmit_code_or_plan(tmp_path,monkeypatch):
    import empire_os.completion_runtime_evidence as evidence
    monkeypatch.setattr(evidence,"observe_existing_runtime",fake_evidence)
    sha=git_fixture(tmp_path)
    original=code_receipts(tmp_path,sha)
    record_observed(tmp_path,NAMES[0],sha,original[NAMES[0]])
    with pytest.raises(AttemptMemoryError,match="prior verified feature"):
        record_observed(tmp_path,NAMES[0],sha,original[NAMES[0]])


def test_tampered_runtime_receipt_chain_holds_all_new_dispatch(tmp_path,monkeypatch):
    import empire_os.completion_runtime_evidence as evidence
    monkeypatch.setattr(evidence,"observe_existing_runtime",fake_evidence)
    sha=git_fixture(tmp_path)
    original=code_receipts(tmp_path,sha)
    event=record_observed(tmp_path,NAMES[1],sha,original[NAMES[1]])
    file=tmp_path/event["checkpoint_ref"]
    packet=json.loads(file.read_text())
    packet["reopens"]="attempt_"+"f"*24
    file.write_text(json.dumps(packet))
    state=load_attempt_memory(tmp_path,now=NOW)
    assert state["status"]=="MEMORY_INVALID_HOLD"


def test_reconciliation_recognises_observed_runtime_without_fake_done(tmp_path,monkeypatch):
    import empire_os.completion_runtime_evidence as evidence
    from empire_os.completion_board_dispatcher import _live_rows
    monkeypatch.setattr(evidence,"observe_existing_runtime",fake_evidence)
    sha=git_fixture(tmp_path)
    original=code_receipts(tmp_path,sha)
    record_observed(tmp_path,NAMES[0],sha,original[NAMES[0]])
    rows,_,_=_live_rows(tmp_path/"docs/MASTER_REMAINING_CHECKLIST.md")
    packets=[]
    for row in rows:
        packets.append({
            "item_ids":[row["id"]],
            "checklist_lines":[row["line"]],
            "department":"market_intelligence",
            "execution_class":"safe_internal",
            "verification_contract_ready":True,
        })
    dest=tmp_path/"runtime/execution_plane/business_completion_dispatch_latest.json"
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps({
        "canonical_total_count":3,"canonical_done_count":0,
        "source_pending_count":3,"packets":packets,
    }))
    output=refresh_completion_reconciliation(tmp_path,now=NOW+timedelta(seconds=1))
    assert output["status"]=="AVAILABLE"
    assert output["verified_done_count"]==0
    assert output["automatic_checklist_mutation_allowed"] is False
    assert output["state_counts"]=={
        "RUNTIME_OBSERVED_PENDING_FORMAL_CLOSURE":1,
        "CODE_COMPLETE_NOT_LIVE":2,
    }
    monitor=build_completion_task_monitor(
        parse_checklist(tmp_path/"docs/MASTER_REMAINING_CHECKLIST.md"),
        output, now=NOW+timedelta(seconds=2),
    )
    assert monitor["state_counts"]["RUNTIME_OBSERVED_PENDING_FORMAL_CLOSURE"]==1
    row=next(r for r in monitor["items"] if r["task"]==NAMES[0])
    assert "do not rebuild" in row["next_evidence_step"]
    assert row["commercial_outcome_verified"] is False
    assert monitor["execution_authority"]=="none"



def test_one_shot_capture_records_three_and_never_replays(tmp_path,monkeypatch):
    import empire_os.completion_runtime_evidence as evidence
    import scripts.capture_existing_runtime_evidence as capture
    monkeypatch.setattr(evidence,"observe_existing_runtime",fake_evidence)
    monkeypatch.setattr(capture,"observe_existing_runtime",
                        lambda root,task:fake_evidence(root,task))
    sha=git_fixture(tmp_path)
    code_receipts(tmp_path,sha)
    preview=capture.capture_existing_runtime(tmp_path,apply=False)
    assert preview["status"]=="OBSERVATION_PREVIEW"
    assert all(row["status"]=="VERIFIED_READ_ONLY" for row in preview["items"])
    assert load_attempt_memory(tmp_path,now=datetime.now(timezone.utc))["event_count"]==3
    first=capture.capture_existing_runtime(tmp_path,apply=True)
    assert all(row["status"]=="CAPTURED" for row in first["items"])
    assert first["checklist_status_changes"]==0
    assert first["automatic_closure"] is False
    state=load_attempt_memory(tmp_path,now=datetime.now(timezone.utc))
    assert state["event_count"]==6
    assert state["held_task_count"]==3
    again=capture.capture_existing_runtime(tmp_path,apply=True)
    assert all(row["status"]=="ALREADY_CAPTURED_NO_REPLAY" for row in again["items"])
    assert load_attempt_memory(tmp_path,now=datetime.now(timezone.utc))["event_count"]==6
    assert all(x.status=="PENDING" for x in parse_checklist(
        tmp_path/"docs/MASTER_REMAINING_CHECKLIST.md"
    ))
