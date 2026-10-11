"""Shared completion attempt memory: durable holds, never inferred DONE."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import pytest

from empire_os.completion_board_dispatcher import dispatch_completion_board
from empire_os.completion_task_memory import (
    AttemptMemoryError, load_attempt_memory, preflight_task,
    record_attempt, task_key,
)
from empire_os.department_work_queue import DepartmentWorkQueue

NOW = datetime.now(timezone.utc).replace(microsecond=0)
SECTION = "Opportunity Radar / Factory"
RADAR = "Expose full Radar / research / blockers / opportunity lifecycle in Founder Console"
SENSOR = "Wire remaining Sensor Mesh domains -> Opportunity Radar"
OTEL = "OTEL/Langfuse trace events for queue -> route -> lease -> worker -> verify -> proposal -> live result"


def make_root(tmp_path, *, rows=(RADAR, SENSOR, OTEL)):
    d = tmp_path / "docs"
    d.mkdir(exist_ok=True)
    body = "# Master\n## " + SECTION + "\n"
    body += "".join("- [ ] " + item + "\n" for item in rows)
    (d / "MASTER_REMAINING_CHECKLIST.md").write_text(body)
    p = subprocess.run(["git", "init", "-q"], cwd=tmp_path, capture_output=True)
    assert p.returncode == 0
    (tmp_path / "README.md").write_text("test only\n")
    p = subprocess.run(
        ["git", "add", "README.md"], cwd=tmp_path, capture_output=True)
    assert p.returncode == 0
    p = subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "commit", "-q", "-m", "baseline"], cwd=tmp_path, capture_output=True)
    assert p.returncode == 0
    sha = subprocess.check_output(
        ["git", "rev-parse", "--short=12", "HEAD"], cwd=tmp_path, text=True).strip()
    return tmp_path, sha


def record_code(root, sha, item=RADAR):
    return record_attempt(
        root, section=SECTION, item=item, owner="market_intelligence",
        attempt_state="CODE_VERIFIED_NOT_LIVE", commit=sha,
        evidence_refs=[
            f"commit:{sha}", "pytest:257_passed",
            "feature_branch:feature/founder-radar-lifecycle-surface-20261011",
        ], now=NOW)


def record_blocked(root, item=SENSOR, blocker="hermes_zero_cost_model_unavailable"):
    return record_attempt(
        root, section=SECTION, item=item, owner="engineering",
        attempt_state="PROVIDER_CAPACITY_BLOCKED", blocker=blocker,
        evidence_refs=[
            "hermes_result:completion-20261011-sensor-radar-read-bridge-v1",
        ], now=NOW)


def test_line_shift_preserves_semantic_task_key_and_memory_hold(tmp_path):
    root, sha = make_root(tmp_path)
    attempt = record_code(root, sha)
    (root / "docs/MASTER_REMAINING_CHECKLIST.md").write_text(
        "# Extra\n\n# Master\n## " + SECTION + "\n"
        + "- [ ] " + RADAR + "\n- [ ] " + SENSOR + "\n- [ ] " + OTEL + "\n"
    )
    snapshot = load_attempt_memory(root, now=NOW)
    verdict = preflight_task(snapshot, section=SECTION, item=RADAR)
    assert verdict["decision"] == "HOLD"
    assert verdict["reason"] == "CODE_VERIFIED_NOT_LIVE"
    assert verdict["last_attempt_id"] == attempt["attempt_id"]
    assert task_key(SECTION, RADAR) != task_key(SECTION, SENSOR)


def test_memory_checkpoint_is_exclusive_and_idempotent(tmp_path):
    root, sha = make_root(tmp_path)
    first = record_code(root, sha)
    second = record_code(root, sha)
    assert first["created"] is True
    assert second["created"] is False
    assert first["attempt_id"] == second["attempt_id"]
    p = root / first["checkpoint_ref"]
    assert p.stat().st_mode & 0o777 == 0o600
    receipt = json.loads(p.read_text())
    assert receipt["stage"] == "TASK_MEMORY_EVENT"
    assert receipt["state"] == "OBSERVED"
    assert receipt["live_verified"] is False
    assert receipt["founder_approval_inferred"] is False
    assert receipt["execution_authority"] == "none"
    assert receipt["external_action_performed"] is False
    assert receipt["checklist_source_sha256"] == sha256(
        (root / "docs/MASTER_REMAINING_CHECKLIST.md").read_bytes()
    ).hexdigest()


def test_code_claim_requires_real_registered_git_commit_and_test_evidence(tmp_path):
    root, sha = make_root(tmp_path)
    with pytest.raises(AttemptMemoryError, match="commit"):
        record_attempt(
            root, section=SECTION, item=RADAR,
            owner="market_intelligence",
            attempt_state="CODE_VERIFIED_NOT_LIVE",
            commit="a" * 40,
            evidence_refs=["pytest:257_passed", "feature_branch:feature/radar"],
            now=NOW,
        )
    with pytest.raises(AttemptMemoryError, match="tests"):
        record_attempt(
            root, section=SECTION, item=RADAR,
            owner="market_intelligence",
            attempt_state="CODE_VERIFIED_NOT_LIVE",
            commit=sha,
            evidence_refs=["commit:" + sha],
            now=NOW,
        )


def test_unknown_or_done_checklist_item_cannot_acquire_false_attempt(tmp_path):
    root, sha = make_root(tmp_path)
    with pytest.raises(AttemptMemoryError, match="exact unique"):
        record_code(root, sha, item="not in checklist")
    src=root/"docs/MASTER_REMAINING_CHECKLIST.md"
    src.write_text(src.read_text().replace("- [ ] " + RADAR, "- [x] " + RADAR))
    with pytest.raises(AttemptMemoryError, match="exact unique"):
        record_code(root, sha)


@pytest.mark.parametrize("invalid", [
    "https://external-collector.example/test",
    "runtime:passwords",
    "source:api_key",
    "pytest:test@personal.example",
    "pytest:ok\ninjected",
])
def test_evidence_reference_never_stores_secrets_or_untrusted_url(tmp_path,invalid):
    root, _ = make_root(tmp_path)
    with pytest.raises(AttemptMemoryError, match="evidence"):
        record_attempt(
            root, section=SECTION, item=SENSOR,
            owner="engineering", attempt_state="PROVIDER_CAPACITY_BLOCKED",
            blocker="hermes_zero_cost_model_unavailable",
            evidence_refs=[invalid, "hermes_result:test"], now=NOW,
        )


def test_historical_provider_failure_holds_without_claiming_task_done(tmp_path):
    root,_=make_root(tmp_path)
    record_blocked(root)
    snapshot=load_attempt_memory(root,now=NOW)
    result=preflight_task(snapshot,section=SECTION,item=SENSOR)
    assert result["decision"]=="HOLD"
    assert result["reason"]=="PROVIDER_CAPACITY_BLOCKED"
    assert result["blocker"]=="hermes_zero_cost_model_unavailable"
    assert snapshot["held_task_count"]==1
    assert preflight_task(snapshot,section=SECTION,item=RADAR)["decision"]=="NEW_EVIDENCE_REQUIRED"


def test_dispatch_skips_only_held_tasks_and_keeps_master_pending(tmp_path):
    root,sha=make_root(tmp_path)
    record_code(root,sha)
    record_blocked(root)
    result=dispatch_completion_board(root,now=NOW)
    assert result["status"]=="AVAILABLE"
    assert result["source_pending_count"]==3
    assert result["memory_event_count"]==2
    assert result["memory_held_task_count"]==2
    assert result["queued_packet_count"]==1
    assert result["canonical_done_count"]==0
    packet=result["packets"][0]
    assert packet["held_item_ids"] and len(packet["held_item_ids"])==2
    queue=DepartmentWorkQueue(root)
    work=queue._load(queue._find_path(packet["work_id"]))
    assert len(work.intelligence_request["item_ids"])==1
    assert len(work.intelligence_request["held_item_ids"])==2
    assert "OTEL/Langfuse" in work.rationale
    assert RADAR not in work.rationale
    assert SENSOR not in work.rationale
    again=dispatch_completion_board(root,now=NOW)
    assert again["queued_packet_count"]==0
    assert again["existing_packet_count"]==1
    assert len(list(queue.ready.glob("*.json")))==1


def test_fully_held_packet_never_creates_a_plan_or_fake_completion(tmp_path):
    root,sha=make_root(tmp_path,rows=(RADAR,))
    record_code(root,sha)
    result=dispatch_completion_board(root,now=NOW)
    assert result["source_pending_count"]==1
    assert result["memory_held_task_count"]==1
    assert result["memory_held_packet_count"]==1
    assert result["queued_packet_count"]==0
    assert result["packets"][0]["action"]=="HOLD_PRIOR_ATTEMPT"
    assert result["packets"][0]["work_id"] is None
    assert DepartmentWorkQueue(root).counts()["ready"]==0
    assert "- [ ] " + RADAR in (root/"docs/MASTER_REMAINING_CHECKLIST.md").read_text()


def test_corrupt_memory_blocks_every_new_completion_dispatch(tmp_path):
    root,_=make_root(tmp_path)
    p=root/"runtime/execution_plane/completion_checkpoints/task_memory_corrupt.json"
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text('{"status":"DONE","stage":"LIVE_VERIFY_DONE"}')
    state=load_attempt_memory(root,now=NOW)
    assert state["status"]=="MEMORY_INVALID_HOLD"
    result=dispatch_completion_board(root,now=NOW)
    assert result["status"]=="MEMORY_INVALID_HOLD"
    assert result["queued_packet_count"]==0
    assert DepartmentWorkQueue(root).counts()["ready"]==0


def test_resolution_cannot_bypass_prior_evidence_or_be_reused(tmp_path):
    root,_=make_root(tmp_path,rows=(SENSOR,))
    block=record_blocked(root)
    with pytest.raises(AttemptMemoryError, match="latest held"):
        record_attempt(
            root,section=SECTION,item=SENSOR,owner="engineering",
            attempt_state="RESOLVED_WITH_NEW_EVIDENCE",
            reopens="attempt_"+"0"*24,evidence_refs=["model_probe:healthy"],
            now=NOW+timedelta(seconds=3),
        )
    unlock=record_attempt(
        root,section=SECTION,item=SENSOR,owner="engineering",
        attempt_state="RESOLVED_WITH_NEW_EVIDENCE",
        reopens=block["attempt_id"],
        evidence_refs=["model_probe:healthy"],
        now=NOW+timedelta(seconds=3),
    )
    assert unlock["created"]
    verdict=preflight_task(load_attempt_memory(root,now=NOW+timedelta(seconds=5)),
                           section=SECTION,item=SENSOR)
    assert verdict["decision"]=="REVIEW_NEW_EVIDENCE"
    assert verdict["reason"]=="RESOLVED_WITH_NEW_EVIDENCE"


def test_no_memory_records_means_original_dispatch_is_unchanged(tmp_path):
    root,_=make_root(tmp_path)
    result=dispatch_completion_board(root,now=NOW)
    assert result["memory_event_count"]==0
    assert result["memory_held_task_count"]==0
    assert result["source_pending_count"]==3
    assert result["queued_packet_count"]>0
    assert result["consequential_actions_dispatched"] is False



def test_direct_governed_hermes_request_reuses_attempt_memory_without_publishing(
    tmp_path, monkeypatch,
):
    from empire_os.execution_plane_dispatcher import (
        ExecutionRequest, dispatch_execution_request,
    )
    import empire_os.execution_plane_dispatcher as dispatcher
    root, sha=make_root(tmp_path, rows=(RADAR,))
    record_code(root, sha)
    source_line=3
    old_id="check_"+sha256(f"{source_line}|{SECTION}|{RADAR}".encode()).hexdigest()[:16]
    called=[]
    monkeypatch.setattr(
        dispatcher, "publish_control_job",
        lambda *a,**k: called.append(True),
    )
    req=ExecutionRequest(
        request_id="radar-repeat-by-second-agent",
        capability="backend_code", department="market_intelligence",
        objective="Implement Radar again",
        authority="internal_write",
        base_branch="agent/data-cloud-wave4",
        source_ref=f"checklist:{old_id}:line_{source_line}",
        allowed_paths=("empire_os/founder_dashboard.py",),
        lease_resources=("path:empire_os/founder_dashboard.py",),
    )
    out=dispatch_execution_request(root,req)
    assert out["status"]=="HELD_BY_ATTEMPT_MEMORY"
    assert out["reason"]=="CODE_VERIFIED_NOT_LIVE"
    assert out["worker"] is None
    assert out["production_deploy"] is False
    assert called==[]


def test_stable_task_key_guards_direct_dispatch_after_checklist_line_shift(tmp_path):
    from empire_os.completion_task_memory import preflight_checklist_source
    root,sha=make_root(tmp_path,rows=(RADAR,))
    record_code(root,sha)
    new=(root/"docs/MASTER_REMAINING_CHECKLIST.md")
    new.write_text("# Padding\n\n"+new.read_text())
    prior="check_"+sha256(f"3|{SECTION}|{RADAR}".encode()).hexdigest()[:16]
    legacy=preflight_checklist_source(root,f"checklist:{prior}:line_3",now=NOW)
    assert legacy["decision"]=="HOLD"
    assert legacy["reason"]=="stale_or_unbound_checklist_task"
    stable=preflight_checklist_source(
        root,f"checklist:{task_key(SECTION,RADAR)}:line_3",now=NOW,
    )
    assert stable["decision"]=="HOLD"
    assert stable["reason"]=="CODE_VERIFIED_NOT_LIVE"


def test_stale_ready_department_packet_blocked_before_model_call(tmp_path,monkeypatch):
    from empire_os.department_worker import run_one_department_work
    import empire_os.department_worker as worker
    from empire_os.completion_board_dispatcher import _live_rows

    root,sha=make_root(tmp_path,rows=(RADAR,))
    rows,_,_=_live_rows(root/"docs/MASTER_REMAINING_CHECKLIST.md")
    r=rows[0]
    queue=DepartmentWorkQueue(root)
    packet={
        "step_id":"repeat_prior_completed_founder_radar",
        "goal_key":"converge_master_remaining_checklist",
        "department_keys":["market_intelligence"],
        "target_component":"empire_coder",
        "action":"completion_review_then_implement_or_verify",
        "authority":"observe",
        "intelligence_request":{
            "item_ids":[r["id"]],"checklist_lines":[r["line"]],
        },
        "rationale":"Plan the work (should not reach model)",
    }
    item,created=queue.enqueue_step(
        plan_id="completion_board_live_v3",
        step=packet,
    )
    assert created
    record_code(root,sha)
    monkeypatch.setattr(worker,"EmpireCoder",lambda *a,**k:pytest.fail("MODEL_CALLED"))
    result=run_one_department_work(root)
    assert result["state"]=="BLOCKED"
    assert result["blocker"]=="completion_task_memory_or_source_hold"
    assert result["memory_preflight"]["decision"]=="HOLD"
    assert queue.counts()["blocked"]==1
    assert queue.counts()["done"]==0


def test_reconciliation_shows_memory_holds_as_unfinished(tmp_path):
    from empire_os.completion_reconciliation import refresh_completion_reconciliation
    root,sha=make_root(tmp_path)
    record_code(root,sha)
    record_blocked(root)
    dispatch=dispatch_completion_board(root,now=NOW)
    result=refresh_completion_reconciliation(root,now=NOW)
    assert result["status"]=="AVAILABLE"
    assert result["verified_done_count"]==0
    assert result["automatic_checklist_mutation_allowed"] is False
    assert result["attempt_memory_held_task_count"]==2
    items={row["checklist_line"]:row for row in result["items"]}
    assert len(items)==3
    assert items[3]["state"]=="CODE_COMPLETE_NOT_LIVE"
    assert items[3]["attempt_memory_commit"]==sha
    assert items[4]["state"]=="BUILDER_PROVIDER_BLOCKED"
    assert items[5]["state"] not in ("VERIFIED_DONE","CODE_COMPLETE_NOT_LIVE")
    assert all(row["checklist_mutation_performed"] is False for row in result["items"])


def test_memory_record_does_not_create_commercial_closure_checkpoint(tmp_path):
    from empire_os.completion_closure_reconciler import _checkpoint_bindings
    root,sha=make_root(tmp_path,rows=(RADAR,))
    record_code(root,sha)
    by_id,by_line,by_item=_checkpoint_bindings(root)
    assert not by_id and not by_line and not by_item


def test_simultaneous_writers_publish_exactly_one_complete_receipt(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    root,sha=make_root(tmp_path,rows=(RADAR,))
    with ThreadPoolExecutor(max_workers=5) as pool:
        results=list(pool.map(lambda _:record_code(root,sha),range(5)))
    assert sum(r["created"] is True for r in results)==1
    snapshot=load_attempt_memory(root,now=NOW)
    assert snapshot["status"]=="AVAILABLE"
    assert snapshot["event_count"]==1


def test_resolved_evidence_must_be_reviewed_before_another_builder_run(tmp_path,monkeypatch):
    from empire_os.execution_plane_dispatcher import ExecutionRequest,dispatch_execution_request
    import empire_os.execution_plane_dispatcher as dispatcher
    root,_=make_root(tmp_path,rows=(SENSOR,))
    blocked=record_blocked(root)
    record_attempt(
        root,section=SECTION,item=SENSOR,owner="engineering",
        attempt_state="RESOLVED_WITH_NEW_EVIDENCE",
        reopens=blocked["attempt_id"],
        evidence_refs=["model_probe:healthy"],now=NOW+timedelta(seconds=1),
    )
    # Artificially advanced clock avoids future receipt rejection.
    import empire_os.completion_task_memory as cm
    real=cm.preflight_checklist_source
    monkeypatch.setattr(
        dispatcher, "preflight_checklist_source",
        lambda root,ref:real(root,ref,now=NOW+timedelta(seconds=2)),
    )
    called=[]
    monkeypatch.setattr(dispatcher,"publish_control_job",
                        lambda *a,**k:called.append(True))
    rows=__import__("empire_os.completion_board_dispatcher",
        fromlist=["_live_rows"])._live_rows(
            root/"docs/MASTER_REMAINING_CHECKLIST.md"
        )[0]
    r=rows[0]
    result=dispatch_execution_request(
        root,
        ExecutionRequest(
            request_id="cannot_auto_retry",capability="backend_code",
            department="engineering",objective="Retry prior failure",
            authority="internal_write",source_ref=f"checklist:{r['id']}:line_{r['line']}",
            allowed_paths=("empire_os/opportunity_radar.py",),
            lease_resources=("path:empire_os/opportunity_radar.py",),
        ),
    )
    assert result["status"]=="HELD_BY_ATTEMPT_MEMORY"
    assert result["reason"]=="new_evidence_requires_independent_review"
    assert called==[]



def test_memory_checkpoint_even_forged_live_cannot_close_checklist(tmp_path):
    from empire_os.completion_closure_reconciler import (
        reconcile_completion_closure,
    )
    root,sha=make_root(tmp_path,rows=(RADAR,))
    receipt=record_code(root,sha)
    p=root/receipt["checkpoint_ref"]
    data=json.loads(p.read_text())
    # Corrupt memory must never masquerade as the closure stage.
    data.update({
        "stage":"LIVE_VERIFY_DONE", "state":"DONE","live_verified":True,
        "checklist_lines":[3], "checklist_items":[RADAR],
    })
    p.write_text(json.dumps(data))
    v=root/"runtime/coder/jobs/completed/verified.json"
    v.parent.mkdir(parents=True,exist_ok=True)
    v.write_text(json.dumps({
        "id":"verification",
        "kind":"VERIFY","status":"COMPLETED",
        "payload":{"completion_checklist_lines":[3]},
        "result":{"verification":{"verdict":"PASS"}},
    }))
    out=reconcile_completion_closure(root,apply=False,now=NOW)
    assert out["applied_closure_count"]==0
    assert out["eligible_exact_closure_count"]==0
    assert "- [ ] "+RADAR in (root/"docs/MASTER_REMAINING_CHECKLIST.md").read_text()


def test_inspection_cli_report_is_read_only_and_fails_closed_on_corruption(tmp_path):
    from scripts.inspect_completion_task_memory import report
    root,sha=make_root(tmp_path)
    record_code(root,sha)
    before={str(p):p.read_bytes() for p in root.rglob("*.json")}
    output=report(root)
    assert output["status"]=="AVAILABLE"
    assert output["held_pending_task_count"]==1
    assert output["canonical_pending_count"]==3
    assert output["items"][0]["state"]=="CODE_VERIFIED_NOT_LIVE"
    assert output["checklist_mutation_performed"] is False
    assert before=={str(p):p.read_bytes() for p in root.rglob("*.json")}
    forged=root/"runtime/execution_plane/completion_checkpoints/task_memory_bad.json"
    forged.write_text("{}")
    assert report(root)["status"]=="MEMORY_INVALID_HOLD"
