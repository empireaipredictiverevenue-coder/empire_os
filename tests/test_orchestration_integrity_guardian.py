"""Independent executive governance: no false completion, no service-chain growth."""
from datetime import datetime, timezone
import json
from empire_os.orchestration_integrity_guardian import (
    MAX_EXISTING_DROPINS, MAX_EXISTING_POST_HOOKS,
    assess, observe_queue, run_guardian,
)
NOW = datetime(2026,11,14,22,45,tzinfo=timezone.utc)

def service():
    return {"available":True, "post_hook_count":57, "drop_in_count":42, "sub_state":"dead"}

def queue(**changes):
    v = {"available":True,"unresolved_count":1,"blocked_or_failed_count":1,
         "stage_only_done_not_implementation_count":1,
         "unowned_exceptions":0,"malformed_work_items":0,"owner_incidents":[]}
    v.update(changes)
    return v

def source(**changes):
    return {"generated_at":NOW.isoformat(),**changes}

def test_existing_debt_remains_visible_not_successful():
    r=assess(queue(),service(),source(),source(),now=NOW)
    assert r["status"]=="DEGRADED"
    assert r["release_gate"]=="NO_NEW_VIOLATION"
    assert {"EXISTING_SERIAL_HOOK_DEBT","UNRESOLVED_EXECUTIVE_EXCEPTIONS",
            "STAGE_DONE_IS_NOT_CUSTOMER_DELIVERY"} <= {x["code"] for x in r["findings"]}

def test_growth_and_false_completion_reject_release():
    service_grown={**service(),"post_hook_count":MAX_EXISTING_POST_HOOKS+1,
                   "drop_in_count":MAX_EXISTING_DROPINS+1}
    r=assess(queue(),service_grown,
             source(customer_delivery_verified=True),
             source(plan_success_claimed=True,evaluation_state="BLOCKED",
                    result_evidence_refs=[]),now=NOW)
    assert r["release_gate"]=="REJECT"
    assert {"ARCHITECTURE_HOOK_GROWTH","FALSE_CUSTOMER_DELIVERY_CLAIM",
            "FALSE_PLAN_SUCCESS_CLAIM"} <= {x["code"] for x in r["findings"]}

def test_missing_or_stale_evidence_and_unowned_work_reject():
    r=assess(queue(unowned_exceptions=2),service(),None,None,now=NOW)
    assert r["status"]=="CRITICAL"
    assert r["release_gate"]=="REJECT"
    r=assess(queue(),service(),{"generated_at":"2026-11-10T12:00:00+00:00"},
             source(),now=NOW)
    assert "STALE_DISPATCH" in {x["code"] for x in r["findings"]}

def test_real_stage_only_done_not_customer_implementation(tmp_path):
    done=tmp_path/"runtime/departments/work/done"
    blocked=tmp_path/"runtime/departments/work/blocked"
    done.mkdir(parents=True)
    blocked.mkdir(parents=True)
    for status in ("ready", "running", "review", "failed"):
        (tmp_path/"runtime/departments/work"/status).mkdir()
    (done/"w1.json").write_text(json.dumps({
        "status":"DONE","id":"w1","target_component":"empire_coder",
        "result":{"implementation_performed":False}
    }))
    (blocked/"w2.json").write_text(json.dumps({
        "status":"BLOCKED","id":"w2","target_component":"predictive_intelligence",
        "error":"insufficient_verified_outcome_cohort",
        "department_keys":["data_quant"],
    }))
    q=observe_queue(tmp_path)
    assert q["counts"]["done"]==1
    assert q["stage_only_done_not_implementation_count"]==1
    assert q["blocked_or_failed_count"]==1
    assert q["owner_incidents"][0]["departments"]=="data_quant"

def test_readonly_report_writes_no_queue_files(tmp_path):
    for key in ("runtime/astra/department_dispatch_latest.json",
                "runtime/astra/executive_evaluation_latest.json"):
        p=tmp_path/key;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(source()))
    r=run_guardian(tmp_path,now=NOW,service=service())
    assert r["mode"]=="OBSERVE"
    assert r["production_mutation"] is False
    assert r["execution_authority"]=="none"
    p=tmp_path/"runtime/orchestration_integrity/latest.json"
    assert json.loads(p.read_text())["schema_version"]==r["schema_version"]
    assert not (tmp_path/"runtime/departments/work").exists()
    assert r["release_gate"] == "REJECT"  # no invented healthy empty queue


def test_reliability_health_reflects_independent_guardian(monkeypatch, tmp_path):
    from datetime import datetime, timezone
    from empire_os import reliability_agent as reliability
    from empire_os import orchestration_integrity_guardian as guardian

    now = datetime(2026, 11, 14, 23, 0, tzinfo=timezone.utc)
    root = tmp_path.resolve()
    monkeypatch.setattr(reliability, "ROOT", root)
    monkeypatch.setattr(reliability, "STATE_PATH", root / "runtime/reliability_agent/state.json")
    monkeypatch.setattr(reliability, "LATEST_PATH", root / "runtime/reliability_agent/latest.json")
    monkeypatch.setattr(reliability, "DATA_CLOUD_LATEST_PATH", root / "runtime/data_cloud/health_latest.json")
    monkeypatch.setattr(reliability, "plan_actions", lambda _observation: [])
    observation = reliability.ReliabilityObservation(
        observed_at=now.isoformat(),
        supabase_egress_contained=False,
        supabase_guard_state="healthy",
        recovery_snapshot_exists=True,
        recovery_seed_count=1,
        recovery_snapshot_age_seconds=10,
        recovery_heartbeat_exists=True,
        recovery_heartbeat_age_seconds=10,
        recovery_heartbeat_state="HEALTHY",
    )
    monkeypatch.setattr(reliability, "observe", lambda *_args, **_kwargs: observation)

    def guardian_result(status, release_gate="NO_NEW_VIOLATION"):
        monkeypatch.setattr(guardian, "run_guardian", lambda *_args, **_kwargs: {
            "status": status,
            "release_gate": release_gate,
            "finding_count": 4 if status == "CRITICAL" else 0,
        })
        return reliability.run_cycle(root, now=now)

    critical = guardian_result("CRITICAL")
    assert critical["status"] == "DEGRADED"
    assert critical["orchestration_integrity_guardian"]["release_gate"] == "NO_NEW_VIOLATION"
    assert guardian_result("HEALTHY")["status"] == "HEALTHY"
    assert guardian_result("HEALTHY", "REJECT")["status"] == "DEGRADED"

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("audit failed")
    monkeypatch.setattr(guardian, "run_guardian", unavailable)
    unavailable_report = reliability.run_cycle(root, now=now)
    assert unavailable_report["status"] == "DEGRADED"
    assert unavailable_report["orchestration_integrity_guardian"]["status"] == "AUDIT_UNAVAILABLE"
