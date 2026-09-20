import os
import time
from types import SimpleNamespace

from empire_os.coder.jobs import (
    JobKind,
    JobStatus,
    LocalJobQueue,
)
from empire_os.coder.models import ToolDecision
from empire_os.coder.worker import CoderTaskWorker


def workspace(tmp_path):
    (tmp_path / ".git").mkdir()
    return tmp_path


def test_queue_enqueue_claim_complete_and_reload(tmp_path):
    root = workspace(tmp_path)
    queue = LocalJobQueue(root)
    job = queue.enqueue(
        task_id="coder_task_1",
        kind=JobKind.PLAN,
        payload={"terms": ["coder"]},
    )
    assert job.status is JobStatus.PENDING
    claimed = queue.claim_next()
    assert claimed.id == job.id
    assert claimed.status is JobStatus.RUNNING
    assert claimed.attempts == 1

    completed = queue.complete(
        claimed,
        {"proposal_persisted": True},
    )
    assert completed.status is JobStatus.COMPLETED
    restored = queue.get(job.id)
    assert restored.status is JobStatus.COMPLETED
    assert restored.result["proposal_persisted"] is True


def test_stale_running_job_is_recovered_without_losing_attempt_count(tmp_path):
    root = workspace(tmp_path)
    queue = LocalJobQueue(root)
    job = queue.enqueue(
        task_id="coder_task_2",
        kind=JobKind.NEXT_COMMAND,
    )
    claimed = queue.claim_next()
    path = queue.running / f"{claimed.id}.json"
    old = time.time() - 7200
    os.utime(path, (old, old))

    recovered = queue.recover_stale(
        stale_seconds=60,
        max_attempts=3,
    )
    assert recovered == [job.id]
    restored = queue.get(job.id)
    assert restored.status is JobStatus.PENDING
    assert restored.attempts == 1


class FakeCoder:
    def __init__(self):
        self.calls = []

    def load_task(self, task_id):
        self.calls.append(("load_task", task_id))
        return SimpleNamespace(id=task_id)

    def build_context(self, task_id, **kwargs):
        self.calls.append(("build_context", task_id, kwargs))
        return SimpleNamespace()

    def planner_model_draft(self, task_id, instruction, context, **kwargs):
        self.calls.append(("plan", task_id, instruction, kwargs))
        return SimpleNamespace(
            stage=SimpleNamespace(value="DRAFT"),
            candidate_drafts=["plan a"],
            revision_count=0,
        )

    def propose_next_command(self, task_id, objective, context):
        self.calls.append(("next_command", task_id, objective))
        return SimpleNamespace(
            candidate_texts=["git status", "git diff --check"],
            argv=("git", "diff", "--check"),
            decision=ToolDecision.ALLOW,
            eligible=True,
        )

    def propose_structured_patch(self, task_id, objective, context):
        self.calls.append(("structured_patch", task_id, objective))
        return SimpleNamespace(
            eligible=True,
            validation=SimpleNamespace(
                reasons=(),
                warnings=(),
            ),
            proposal=SimpleNamespace(
                target_path="empire_os/example.py",
                operation=SimpleNamespace(value="create_file"),
                expected_tests=("tests/test_example.py",),
            ),
        )

    def apply_structured_patch(self, task_id, candidate):
        self.calls.append(("apply_structured_patch", task_id))
        return {"path": candidate.proposal.target_path}

    def impacted_tests(self, changed_files):
        self.calls.append(("impacted_tests", tuple(changed_files)))
        return ("tests/test_example.py",)

    def verify(self, task_id, *, changed_files, commands):
        self.calls.append(
            ("verify", task_id, tuple(changed_files), tuple(commands))
        )
        return SimpleNamespace(
            as_dict=lambda: {
                "verdict": "PASS",
                "checks": [],
                "reasons": [],
                "warnings": [],
            }
        )


def test_worker_processes_plan_without_patch_or_command_execution(tmp_path):
    root = workspace(tmp_path)
    queue = LocalJobQueue(root)
    coder = FakeCoder()
    worker = CoderTaskWorker(coder, queue)
    job = queue.enqueue(
        task_id="coder_task_3",
        kind=JobKind.PLAN,
        payload={
            "terms": ["Empire Coder"],
            "symbols": ["EmpireCoder"],
            "budget_chars": 24000,
        },
    )

    result = worker.run_once()
    assert result.id == job.id
    assert result.status is JobStatus.COMPLETED
    assert result.result["candidate_count"] == 1
    assert result.result["actionable_patch"] is False
    context_call = next(call for call in coder.calls if call[0] == "build_context")
    assert context_call[2]["budget_chars"] == 4500
    plan_call = next(call for call in coder.calls if call[0] == "plan")
    assert plan_call[3]["max_output_chars"] == 450
    assert not any(call[0] == "run_tool" for call in coder.calls)


def test_worker_next_command_returns_proposal_but_does_not_execute(tmp_path):
    root = workspace(tmp_path)
    queue = LocalJobQueue(root)
    coder = FakeCoder()
    worker = CoderTaskWorker(coder, queue)
    job = queue.enqueue(
        task_id="coder_task_4",
        kind=JobKind.NEXT_COMMAND,
    )

    result = worker.run_once()
    assert result.id == job.id
    assert result.status is JobStatus.COMPLETED
    assert result.result["eligible"] is True
    assert result.result["executed"] is False
    assert result.result["argv"] == ["git", "diff", "--check"]


def test_worker_implement_applies_one_validated_patch_and_verifies(tmp_path):
    root = workspace(tmp_path)
    queue = LocalJobQueue(root)
    coder = FakeCoder()
    worker = CoderTaskWorker(coder, queue)
    job = queue.enqueue(
        task_id="coder_task_5",
        kind=JobKind.IMPLEMENT,
        payload={
            "terms": ["buyer_allocation"],
            "budget_chars": 12000,
        },
    )

    result = worker.run_once()

    assert result.id == job.id
    assert result.status is JobStatus.COMPLETED
    assert result.result["applied"] is True
    assert result.result["target_path"] == "empire_os/example.py"
    assert result.result["candidate_commit_required"] is True
    assert result.result["production_mutation"] is False
    context_call = next(
        call for call in coder.calls
        if call[0] == "build_context"
    )
    assert context_call[2]["budget_chars"] == 8000
    assert any(
        call[0] == "apply_structured_patch"
        for call in coder.calls
    )
    verify_call = next(
        call for call in coder.calls
        if call[0] == "verify"
    )
    assert verify_call[3] == (
        ("pytest", "-q", "tests/test_example.py"),
    )


def test_finish_returns_recovered_pending_job_instead_of_raising(tmp_path):
    root = workspace(tmp_path)
    queue = LocalJobQueue(root)
    job = queue.enqueue(
        task_id="coder_task_6",
        kind=JobKind.IMPLEMENT,
    )
    claimed = queue.claim_next()
    running_path = queue.running / f"{claimed.id}.json"
    old = time.time() - 7200
    os.utime(running_path, (old, old))
    queue.recover_stale(stale_seconds=60, max_attempts=3)

    recovered = queue.fail(claimed, "late worker failure")

    assert recovered.status is JobStatus.PENDING
    assert queue.get(job.id).status is JobStatus.PENDING
