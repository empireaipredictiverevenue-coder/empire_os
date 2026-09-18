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

    def polished_model_output(self, task_id, instruction, context, **kwargs):
        self.calls.append(("plan", task_id, instruction))
        return SimpleNamespace(
            stage=SimpleNamespace(value="REFINED"),
            candidate_drafts=["plan a", "plan b"],
            revision_count=1,
        )

    def propose_next_command(self, task_id, objective, context):
        self.calls.append(("next_command", task_id, objective))
        return SimpleNamespace(
            candidate_texts=["git status", "git diff --check"],
            argv=("git", "diff", "--check"),
            decision=ToolDecision.ALLOW,
            eligible=True,
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
            "budget_chars": 8000,
        },
    )

    result = worker.run_once()
    assert result.id == job.id
    assert result.status is JobStatus.COMPLETED
    assert result.result["candidate_count"] == 2
    assert result.result["actionable_patch"] is False
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
