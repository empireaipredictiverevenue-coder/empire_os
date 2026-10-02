import json
from pathlib import Path

import pytest

from empire_os.coder.audit import AuditTrail
from empire_os.coder.jobs import JobKind, JobStatus, LocalJobQueue
from empire_os.coder.memory import ContextMemory
from empire_os.coder.models import CoderTask
from empire_os.coder.state import LocalTaskStore
from empire_os.coder.worker import CoderTaskWorker


class FakeCoder:
    def __init__(self, memory, *, result=None, error=None):
        self.memory = memory
        self._result = result or {"ok": True}
        self._error = error

    def load_task(self, task_id):
        return self.memory.store.load(task_id)


class Worker(CoderTaskWorker):
    def _process(self, job):
        if getattr(self.coder, "_error", None):
            raise self.coder._error
        return dict(self.coder._result)


def setup_runtime(tmp_path: Path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    import subprocess
    subprocess.run(["git", "init", "-q", str(workspace)], check=True)
    runtime = workspace / "runtime" / "coder"
    store = LocalTaskStore(workspace, runtime_root=runtime)
    audit = AuditTrail(runtime)
    memory = ContextMemory(store, audit)
    task = store.create(
        "Do one bounded thing",
        blueprint_path="docs/BLUEPRINT_V6.md",
    )
    memory.refresh(task.id, trigger="test_seed")
    queue = LocalJobQueue(workspace, runtime_root=runtime)
    return workspace, runtime, store, audit, memory, task, queue


def test_completed_job_is_persisted_before_context_retirement(tmp_path):
    _, runtime, _, audit, memory, task, queue = setup_runtime(tmp_path)
    job = queue.enqueue(task_id=task.id, kind=JobKind.PLAN)
    worker = Worker(FakeCoder(memory), queue, context_memory=memory)

    terminal = worker.run_once()

    assert terminal.status is JobStatus.COMPLETED
    persisted = queue.get(job.id)
    assert persisted.status is JobStatus.COMPLETED
    assert not (runtime / "context" / f"{task.id}.json").exists()
    tombstone = json.loads((runtime / "context_retired" / f"{task.id}.json").read_text())
    assert tombstone["job_id"] == job.id
    assert tombstone["terminal_state"] == "COMPLETED"
    assert tombstone["full_context_removed"] is True
    assert any(row["event"] == "context_retired" for row in audit.read_task(task.id))


def test_non_transient_failure_retires_context_after_failed_record(tmp_path):
    _, runtime, _, _, memory, task, queue = setup_runtime(tmp_path)
    job = queue.enqueue(task_id=task.id, kind=JobKind.PLAN)
    worker = Worker(FakeCoder(memory, error=ValueError("boom")), queue, context_memory=memory)

    terminal = worker.run_once()

    assert terminal.status is JobStatus.FAILED
    assert queue.get(job.id).status is JobStatus.FAILED
    assert not (runtime / "context" / f"{task.id}.json").exists()
    tombstone = json.loads((runtime / "context_retired" / f"{task.id}.json").read_text())
    assert tombstone["terminal_state"] == "FAILED"


def test_transient_retry_preserves_context(tmp_path):
    _, runtime, _, _, memory, task, queue = setup_runtime(tmp_path)
    job = queue.enqueue(task_id=task.id, kind=JobKind.PLAN)
    worker = Worker(FakeCoder(memory, error=TimeoutError("temporary timeout")), queue, max_attempts=3, context_memory=memory)

    pending = worker.run_once()

    assert pending.status is JobStatus.PENDING
    assert (runtime / "context" / f"{task.id}.json").exists()
    assert not (runtime / "context_retired" / f"{task.id}.json").exists()


def test_retired_context_can_be_rebuilt_fresh_from_durable_task_state(tmp_path):
    _, runtime, _, _, memory, task, _ = setup_runtime(tmp_path)
    first = memory.load(task.id)
    assert first["version"] == 1
    memory.retire(task.id, terminal_state="COMPLETED", job_id="job-one")

    rebuilt = memory.refresh(task.id, trigger="next_stage")

    assert rebuilt["version"] == 1
    assert rebuilt["trigger"] == "next_stage"
    assert rebuilt["task"]["task_id"] == task.id
    assert (runtime / "context" / f"{task.id}.json").exists()
    assert (runtime / "context_retired" / f"{task.id}.json").exists()
