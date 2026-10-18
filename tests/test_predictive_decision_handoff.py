"""The handoff only *observes* existing department work; no production mutation."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from empire_os.department_work_queue import DepartmentWorkQueue
from empire_os.predictive_decision_handoff import (
    MAX_SOURCE_AGE,
    PLAN_ID,
    build_predictive_decision_handoff,
)

NOW = datetime(2026, 10, 18, 17, 0, tzinfo=timezone.utc)
TASK_ID = "buyer-" + "a" * 20


def _task(**overrides):
    task = {
        "task_id": TASK_ID,
        "source": "canonical_revenue_command_queue",
        "department": "sales_research",
        "recommended_action": "verify_decision_maker",
        "lane": "INTERNAL_PREPARATION",
        "can_prepare_internal_work": True,
        "can_execute": False,
        "execution_authority": "none",
        "founder_gate_required": False,
        "waiting_external": False,
        "source_freshness": "FRESH",
        "evidence_refs": ["business_entity:entity-a", "prospect:prospect-a"],
    }
    task.update(overrides)
    return task


def _decision(items=None, **overrides):
    data = {
        "schema_version": "empire.predictive_decision_control.v1",
        "status": "REVIEW_READY",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "outbound_authorized": False,
        "payment_authorized": False,
        "database_mutation_authorized": False,
        "task_dispatch_performed": False,
        "generated_at": NOW.isoformat(),
        "sources": {
            "buyer_next_best_action": "FRESH",
            "revenue_command_queue": "TRUSTED",
        },
        "items": [_task()] if items is None else items,
        "truncated_count": 0,
    }
    data.update(overrides)
    return data


def _run(root, data=None):
    return build_predictive_decision_handoff(
        _decision() if data is None else data, root, as_of=NOW,
    )


def test_default_creates_no_queue_files_or_directories(tmp_path):
    out = _run(tmp_path)
    assert out["status"] == "REVIEW_READY"
    assert out["ready_for_review_count"] == 1
    assert out["existing_work_count"] == 0
    assert out["work_dispatched"] is False
    assert out["queue_mutated"] is False
    assert not (tmp_path / "runtime").exists()

    candidate = out["candidates"][0]
    assert candidate["current_work_status"] == "NOT_QUEUED"
    step = candidate["work_step"]
    assert step["auto_dispatch_eligible"] is False
    assert step["authority"] == "observe"
    assert step["department_keys"] == ["sales_revenue"]
    assert step["target_component"] == "identity_enrichment"
    assert candidate["enqueuing_authorized"] is False
    assert candidate["safe_to_auto_dispatch"] is False
    assert candidate["work_id"] == DepartmentWorkQueue.deterministic_id(
        PLAN_ID, TASK_ID
    )


def test_existing_work_detected_no_duplicate_writes(tmp_path):
    first = _run(tmp_path)
    step = first["candidates"][0]["work_step"]
    queue = DepartmentWorkQueue(tmp_path)
    item, created = queue.enqueue_step(plan_id=PLAN_ID, step=step)
    assert created is True
    file = tmp_path / "runtime/departments/work/ready" / (item.id + ".json")
    before = file.read_bytes()

    second = _run(tmp_path)
    assert second["existing_work_count"] == 1
    assert second["ready_for_review_count"] == 0
    assert second["candidates"][0]["current_work_status"] == "ALREADY_IN_QUEUE"
    assert second["candidates"][0]["queue_observation_reason"] == "existing_work_ready"
    assert file.read_bytes() == before


def test_failed_and_blocked_tasks_are_held_not_retried(tmp_path):
    first = _run(tmp_path)
    step = first["candidates"][0]["work_step"]
    queue = DepartmentWorkQueue(tmp_path)
    item, _ = queue.enqueue_step(plan_id=PLAN_ID, step=step)
    claimed = queue.claim_next(worker_id="test")
    assert claimed is not None
    queue.block(claimed, "review_has_blocker")
    out = _run(tmp_path)
    assert out["held_count"] == 1
    assert out["candidates"][0]["current_work_status"] == "ESCALATE_HOLD"
    assert not any((tmp_path / "runtime/departments/work/ready").glob("*.json"))


def test_done_is_not_treated_as_payment_or_realized_outcome(tmp_path):
    first = _run(tmp_path)
    step = first["candidates"][0]["work_step"]
    queue = DepartmentWorkQueue(tmp_path)
    queue.enqueue_step(plan_id=PLAN_ID, step=step)
    claimed = queue.claim_next(worker_id="test")
    assert claimed is not None
    queue.complete(claimed, {"notes": "research performed"},
                   evidence_refs=("review:test",), execution_completed=False)
    out = _run(tmp_path)
    packet = out["candidates"][0]
    assert packet["current_work_status"] == "COMPLETED_REVIEW_REQUIRED"
    assert packet["commercial_outcome_verified"] is False
    assert out["revenue_recognized"] is False
    assert out["work_dispatched"] is False


@pytest.mark.parametrize("change", [
    {"can_execute": True},
    {"execution_authority": "internal_write"},
    {"can_prepare_internal_work": False},
    {"source_freshness": "STALE"},
    {"founder_gate_required": True},
    {"waiting_external": True},
    {"department": "outbound"},
    {"source": "agent_imagination"},
    {"evidence_refs": []},
    {"task_id": "bad../id"},
    {"recommended_action": "send_1000_emails"},
])
def test_candidate_security_violations_hold_and_never_enqueue(tmp_path, change):
    out = _run(tmp_path, _decision(items=[_task(**change)]))
    assert out["ready_for_review_count"] == 0
    assert out["candidates"][0]["status"] == "EVIDENCE_HOLD"
    assert not (tmp_path / "runtime").exists()


@pytest.mark.parametrize("change", [
    {"execution_authority": "internal_write"},
    {"task_dispatch_performed": True},
    {"payment_authorized": True},
    {"database_mutation_authorized": True},
    {"mode": "LIVE"},
    {"status": "EVIDENCE_HOLD"},
    {"schema_version": "other"},
    {"truncated_count": 1},
    {"generated_at": (NOW - MAX_SOURCE_AGE - timedelta(seconds=1)).isoformat()},
    {"generated_at": (NOW + timedelta(seconds=1)).isoformat()},
    {"sources": {"buyer_next_best_action": "STALE", "revenue_command_queue": "TRUSTED"}},
])
def test_envelope_or_source_untrusted_all_candidates_held(tmp_path, change):
    out = _run(tmp_path, _decision(**change))
    assert out["status"] == "EVIDENCE_HOLD"
    assert out["candidate_count"] == 0
    assert not (tmp_path / "runtime").exists()


def test_executive_review_and_founder_gate_never_become_work_proposals(tmp_path):
    out = _run(tmp_path, _decision(items=[
        _task(lane="FOUNDER_DECISION", can_prepare_internal_work=False),
        _task(lane="INTERNAL_REVIEW", source="validated_astra_executive_observer"),
    ]))
    assert out["candidate_count"] == 0
    assert out["status"] == "NO_ELIGIBLE_INTERNAL_WORK"


def test_duplicate_decision_identity_blocks_entire_batch(tmp_path):
    out = _run(tmp_path, _decision(items=[_task(), _task()]))
    assert out["status"] == "EVIDENCE_HOLD"
    assert out["candidate_count"] == 0


def test_symlink_existing_work_file_is_untrusted(tmp_path):
    first = _run(tmp_path)
    path = (tmp_path / "runtime/departments/work/ready" /
            (first["candidates"][0]["work_id"] + ".json"))
    path.parent.mkdir(parents=True)
    external = tmp_path / "external.json"
    external.write_text('{"unsafe": true}')
    path.symlink_to(external)
    out = _run(tmp_path)
    assert out["held_count"] == 1
    assert out["candidates"][0]["current_work_status"] == "UNTRUSTED_HELD"
    assert external.read_text() == '{"unsafe": true}'


def test_corrupt_existing_queue_record_is_held(tmp_path):
    first = _run(tmp_path)
    path = (tmp_path / "runtime/departments/work/ready" /
            (first["candidates"][0]["work_id"] + ".json"))
    path.parent.mkdir(parents=True)
    path.write_text("{badjson")
    out = _run(tmp_path)
    assert out["held_count"] == 1
    assert out["candidates"][0]["current_work_status"] == "UNTRUSTED_HELD"


def test_same_work_in_two_states_is_conflict_held(tmp_path):
    first = _run(tmp_path)
    step = first["candidates"][0]["work_step"]
    queue = DepartmentWorkQueue(tmp_path)
    work, _ = queue.enqueue_step(plan_id=PLAN_ID, step=step)
    from_path = tmp_path / "runtime/departments/work/ready" / (work.id + ".json")
    to_path = tmp_path / "runtime/departments/work/running" / (work.id + ".json")
    copy = json.loads(from_path.read_text())
    copy["status"] = "RUNNING"
    to_path.write_text(json.dumps(copy))
    out = _run(tmp_path)
    assert out["held_count"] == 1
    assert out["candidates"][0]["current_work_status"] == "CONFLICT_HELD"


def test_timezone_aware_clock_required(tmp_path):
    with pytest.raises(ValueError):
        build_predictive_decision_handoff(_decision(), tmp_path,
                                          as_of=datetime(2026, 10, 18))


def test_redirected_queue_directory_does_not_get_traversed(tmp_path):
    external = tmp_path / "external_queue"
    external.mkdir()
    queue_base = tmp_path / "runtime/departments"
    queue_base.mkdir(parents=True)
    (queue_base / "work").symlink_to(external, target_is_directory=True)
    out = _run(tmp_path)
    assert out["held_count"] == 1
    assert out["candidates"][0]["current_work_status"] == "UNTRUSTED_HELD"


def test_redirected_queue_state_lane_does_not_get_traversed(tmp_path):
    external = tmp_path / "external_lane"
    external.mkdir()
    root = tmp_path / "runtime/departments/work"
    root.mkdir(parents=True)
    (root / "ready").symlink_to(external, target_is_directory=True)
    out = _run(tmp_path)
    assert out["held_count"] == 1
    assert out["candidates"][0]["current_work_status"] == "UNTRUSTED_HELD"
