"""Campaign same-lane proof. Never promote unproved or fabricated controls."""
import json
import os
from pathlib import Path
import subprocess
import sys

from tests.test_runtime_promotion_isolation import BINDINGS, LANES
ROOT = Path(__file__).resolve().parents[1]
SOURCE_RUNTIME = Path("/srv/empire_os")


def sandbox(tmp_path,mutate):
    proof_path=LANES["campaigns"][1]
    for rel in (BINDINGS,proof_path):
        destination=tmp_path/rel
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes((SOURCE_RUNTIME/rel).read_bytes())
    bindings=tmp_path/BINDINGS
    proof=tmp_path/proof_path
    data=json.loads(bindings.read_text())
    observed=json.loads(proof.read_text())
    # Fixture, not production: force three original unverified slots so
    # this test stays deterministic after a successful live promotion.
    for lane in data["lanes"]:
        if lane.get("lane")=="campaigns":
            for name in ("evidence_lineage","canonical_identity","quarantine"):
                lane["controls"][name]["status"]="UNVERIFIED"
    mutate(data,observed)
    bindings.write_text(json.dumps(data))
    proof.write_text(json.dumps(observed))
    prior=bindings.read_bytes()
    src=(ROOT/"scripts/promote_campaign_runtime_bindings.py").read_text()
    assert src.count('ROOT = Path("/srv/empire_os")')==1
    script=tmp_path/"promote_campaign_runtime_bindings_test.py"
    script.write_text(src.replace('ROOT = Path("/srv/empire_os")',
         f"ROOT = Path({str(tmp_path)!r})"))
    result=subprocess.run([sys.executable,str(script)],cwd=tmp_path,
       env={**os.environ,"PYTHONPATH":str(ROOT)},capture_output=True,
       text=True,timeout=15)
    return result,prior,bindings.read_bytes()


def test_real_observer_proof_promotes_existing_campaign_slots_no_conversation_copy(tmp_path):
    def remove_verified_conversation_templates(binding,observer):
        for lane in binding["lanes"]:
            if lane["lane"]=="conversations_replies":
                for item in lane["controls"].values():
                    item["status"]="UNVERIFIED"
        assert observer["status"]=="VERIFIED_RUNTIME"
    result,before,after=sandbox(tmp_path,remove_verified_conversation_templates)
    assert result.returncode==0,result.stdout+result.stderr
    old=json.loads(before)
    new=json.loads(after)
    assert old["authority"]==new["authority"]=="OBSERVE"
    past=next(l["controls"] for l in old["lanes"] if l["lane"]=="campaigns")
    current=next(l["controls"] for l in new["lanes"] if l["lane"]=="campaigns")
    assert set(past)==set(current)
    for name in ("evidence_lineage","canonical_identity","quarantine"):
        assert past[name]["status"]=="UNVERIFIED"
        assert current[name]["status"]=="VERIFIED_RUNTIME"
        assert current[name]["confidence"]==past[name]["confidence"]
        assert current[name]["lane"]=="campaigns"
        assert "conversation" not in current[name].get("reason","").lower()
    assert next(l for l in old["lanes"] if l["lane"]=="conversations_replies")==next(
        l for l in new["lanes"] if l["lane"]=="conversations_replies")
    assert "CANONICAL_BINDING_WRITE: PASS" in result.stdout


def test_missing_same_lane_control_cannot_be_invented(tmp_path):
    def missing(binding,observer):
        for lane in binding["lanes"]:
            if lane["lane"]=="campaigns":
                lane["controls"].pop("evidence_lineage")
    result,before,after=sandbox(tmp_path,missing)
    assert result.returncode!=0
    assert "existing canonical campaign slot absent" in result.stderr+result.stdout
    assert before==after


def test_unverified_observer_proof_cannot_promote(tmp_path):
    def malformed(binding,observer):
        observer["status"]="HOLD"
    result,before,after=sandbox(tmp_path,malformed)
    assert result.returncode!=0
    assert before==after


def test_lifted_authority_cannot_promote(tmp_path):
    def malicious(binding,observer):
        observer["outbound"]=True
    result,before,after=sandbox(tmp_path,malicious)
    assert result.returncode!=0
    assert before==after
