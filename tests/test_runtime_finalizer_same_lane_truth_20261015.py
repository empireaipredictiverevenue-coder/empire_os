"""A global finalizer cannot borrow conversation templates or promote stale proofs."""
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
FINALIZER=ROOT/"scripts/finalize_runtime_control_bindings.py"
CONTROLS={
    "action_authority","canonical_identity","conflict_detection",
    "duplicate_detection","entity_classification","evidence_lineage",
    "freshness","input_quality","outcome_linkage","output_quality","quarantine",
}
PROOFS={
    "campaign_runtime":"runtime/campaigns_control/campaign_runtime_observer_latest.json",
    "campaign_outcomes":"runtime/campaigns_control/campaign_measured_outcome_latest.json",
    "agent_tasks":"runtime/agent_tasks_control/agent_tasks_runtime_observer_latest.json",
    "opportunities_runtime":"runtime/opportunities_control/opportunities_runtime_observer_latest.json",
    "opportunities_final":"runtime/opportunities_control/opportunities_final_controls_latest.json",
    "opportunities_quarantine":"runtime/opportunities_control/opportunity_quarantine_latest.json",
}
BASE="runtime/control_plane/runtime_control_bindings_latest.json"
NOW=lambda:datetime.now(timezone.utc).isoformat()


def slot(lane,control,verified=False):
    return {
        "lane":lane,"control":control,
        "status":"VERIFIED_RUNTIME" if verified else "UNVERIFIED",
        "artifact_paths":[],"active_units":[],"matched_keys":[],
        "reason":"Original own-lane evidence pending",
        "confidence":0.31,"action_authority_granted":False,
    }


def proof(lane,verified=(),**values):
    return {
        "lane":lane,"mode":"OBSERVE","status":"VERIFIED_RUNTIME",
        "generated_at":NOW(),"runtime_verified_controls":list(verified),
        "outbound":False,"db_write":False,"action_authority_granted":False,
        "campaign_state_mutated":False,**values,
    }


def fixture(tmp_path,mutate=lambda b,p:None):
    bindings={
        "authority":"OBSERVE",
        "lanes":[{"lane":lane,"controls":{
            c:slot(lane,c,verified=(
                lane=="agent_tasks"
                or (c in ("freshness","action_authority") and lane in ("campaigns","opportunities"))
            )) for c in sorted(CONTROLS)}}
            for lane in ("conversations_replies","campaigns","agent_tasks","opportunities")],
    }
    # The independent Conversations & Replies lane is intentionally 0/11.
    p={
        "campaign_runtime":proof("campaigns",CONTROLS-{"freshness","output_quality","outcome_linkage"}),
        "campaign_outcomes":proof("campaigns",["output_quality"],
                                   output_quality_proved=True,
                                   outcome_linkage_proved=False,
                                   exact_outcome_match_count=0),
        "agent_tasks":proof("agent_tasks",CONTROLS-{"action_authority","freshness"},task_count=7),
        "opportunities_runtime":proof(
            "opportunities",
            ["canonical_identity","duplicate_detection","input_quality",
             "evidence_lineage","conflict_detection","output_quality"],
            opportunity_count=5),
        "opportunities_final":proof("opportunities",["entity_classification","outcome_linkage"],
                                   entity_classification_proved=True,
                                   outcome_linkage_proved=True,
                                   exact_outcome_match_count=2),
        "opportunities_quarantine":proof("opportunities",["quarantine"],
                                          control_active=True,evaluated_count=5),
    }
    mutate(bindings,p)
    canonical=tmp_path/BASE
    canonical.parent.mkdir(parents=True)
    canonical.write_text(json.dumps(bindings))
    for name,rel in PROOFS.items():
        path=tmp_path/rel
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(p[name]))
    before=canonical.read_bytes()
    script=tmp_path/"run_finalizer_test.py"
    script.write_text(FINALIZER.read_text().replace(
        'ROOT = Path("/srv/empire_os")',f'ROOT = Path({str(tmp_path)!r})'))
    result=subprocess.run([sys.executable,str(script)],cwd=tmp_path,
                          env={**os.environ,"PYTHONPATH":str(ROOT)},
                          capture_output=True,text=True,timeout=12)
    after=canonical.read_bytes()
    return result,before,after


def test_targets_promote_with_conversation_lane_completely_unverified(tmp_path):
    r,before,after=fixture(tmp_path)
    assert r.returncode==0,r.stdout+r.stderr
    old=json.loads(before);new=json.loads(after)
    original=next(x for x in old["lanes"] if x["lane"]=="conversations_replies")
    current=next(x for x in new["lanes"] if x["lane"]=="conversations_replies")
    assert original==current
    for lane in ("campaigns","agent_tasks","opportunities"):
        c=next(x["controls"] for x in new["lanes"] if x["lane"]==lane)
        for name,entry in c.items():
            assert entry["confidence"]==0.31
            assert entry["action_authority_granted"] is False
            assert entry["lane"]==lane
            assert entry["control"]==name
            if lane=="campaigns" and name=="outcome_linkage":
                assert entry["status"]=="UNVERIFIED"
            else:
                assert entry["status"]=="VERIFIED_RUNTIME"
    assert "OPPORTUNITIES_CANONICAL:" in r.stdout
    audit=tmp_path/"runtime/control_plane/runtime_control_binding_writes.jsonl"
    assert audit.exists()


def test_stale_opportunity_proof_fails_without_any_binding_write(tmp_path):
    def mutate(b,p):
        p["opportunities_runtime"]["generated_at"]="2026-10-07T21:16:49+00:00"
    r,before,after=fixture(tmp_path,mutate)
    assert r.returncode!=0
    assert "opportunities_runtime source proof stale or untrusted" in r.stdout+r.stderr
    assert after==before


def test_unverified_target_slot_cannot_be_invented(tmp_path):
    def mutate(b,p):
        lane=next(x for x in b["lanes"] if x["lane"]=="opportunities")
        lane["controls"].pop("evidence_lineage")
    r,before,after=fixture(tmp_path,mutate)
    assert r.returncode!=0
    assert after==before


def test_wrong_lane_control_not_promoted(tmp_path):
    def mutate(b,p):
        lane=next(x for x in b["lanes"] if x["lane"]=="opportunities")
        lane["controls"]["evidence_lineage"]["lane"]="conversations_replies"
    r,before,after=fixture(tmp_path,mutate)
    assert r.returncode!=0
    assert "invalid same-lane canonical slot" in r.stdout+r.stderr
    assert after==before


def test_consequential_outbound_source_rejected_before_write(tmp_path):
    def mutate(b,p):
        p["opportunities_final"]["outbound"]=True
    r,before,after=fixture(tmp_path,mutate)
    assert r.returncode!=0
    assert after==before


def test_no_fake_opportunity_outcome_or_quarantine_evidence(tmp_path):
    def mutate(b,p):
        p["opportunities_final"]["outcome_linkage_proved"]=False
        p["opportunities_quarantine"]["status"]="INCOMPLETE_RUNTIME_EVALUATION"
    r,before,after=fixture(tmp_path,mutate)
    assert r.returncode!=0
    assert "global finalizer evidence mismatch" in r.stdout+r.stderr
    assert after==before
