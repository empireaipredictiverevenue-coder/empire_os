from pathlib import Path

from empire_os.department_work_queue import (
    DepartmentWorkQueue,
    DepartmentWorkStatus,
)
from empire_os.astra_department_dispatch import dispatch_executive_plan


def step(**overrides):
    row = {
        "step_id": "exec_step_abc",
        "goal_key": "complete_opportunity_evidence",
        "department_keys": ["data_quant"],
        "target_component": "predictive_intelligence",
        "action": "resolve_quant_input:probability_success",
        "authority": "observe",
        "auto_dispatch_eligible": True,
        "founder_gate_required": False,
        "intelligence_request": {
            "task": "quantitative",
            "model_pinned": False,
        },
        "memory_query": {
            "retrieval_only": True,
        },
        "evidence_refs": ["quant_missing:probability_success"],
        "success_condition": "probability remains unknown or is evidenced",
        "rationale": "missing Quant input",
    }
    row.update(overrides)
    return row


def test_queue_is_durable_deduplicated_and_atomically_claimed(tmp_path):
    queue = DepartmentWorkQueue(tmp_path)
    first, created = queue.enqueue_step(
        plan_id="astra_plan_one",
        step=step(),
        priority=90,
    )
    second, created_again = queue.enqueue_step(
        plan_id="astra_plan_one",
        step=step(),
        priority=90,
    )
    assert created is True
    assert created_again is False
    assert first.id == second.id
    assert queue.counts()["ready"] == 1

    claimed = queue.claim_next(worker_id="worker:test")
    assert claimed is not None
    assert claimed.status is DepartmentWorkStatus.RUNNING
    assert claimed.worker_id == "worker:test"
    assert queue.claim_next(worker_id="worker:other") is None

    done = queue.complete(
        claimed,
        {"ok": True},
        evidence_refs=("result:1",),
    )
    assert done.status is DepartmentWorkStatus.DONE
    assert done.result_evidence_refs == ("result:1",)
    assert queue.counts()["done"] == 1


def test_dispatch_only_enqueues_safe_owned_steps(tmp_path):
    path = tmp_path / "runtime/astra/executive_latest.json"
    path.parent.mkdir(parents=True)
    import json
    path.write_text(json.dumps({
        "plan_id": "astra_plan_one",
        "plan": [
            step(),
            step(
                step_id="exec_step_gate",
                target_component="capital_allocator",
                department_keys=["finance_capital"],
                authority="founder_gate",
                auto_dispatch_eligible=False,
                founder_gate_required=True,
            ),
            step(
                step_id="exec_step_unowned",
                department_keys=[],
            ),
        ],
    }))

    result = dispatch_executive_plan(tmp_path)
    assert result["queued_count"] == 1
    assert result["authority_blocked_count"] == 1
    assert result["unowned_count"] == 1
    assert result["external_execution_performed"] is False
    assert result["execution_authority"] == "none"

    second = dispatch_executive_plan(tmp_path)
    assert second["queued_count"] == 0
    assert second["existing_count"] == 1
