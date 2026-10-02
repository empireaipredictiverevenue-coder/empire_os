from types import SimpleNamespace

from empire_os.coder.audit import AuditTrail
from empire_os.coder.jobs import JobKind, JobStatus, LocalJobQueue
from empire_os.coder.memory import ContextMemory
from empire_os.coder.plan_delegation import (
    delegate_oversized_plans,
    reconcile_delegated_plans,
)
from empire_os.coder.router import ModelProfile
from empire_os.coder.state import LocalTaskStore


def _workspace(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".git").mkdir()
    runtime = root / "runtime" / "coder"
    return root, runtime


def test_complex_plan_delegates_to_hermes_observe_only(monkeypatch, tmp_path):
    root, runtime = _workspace(tmp_path)
    store = LocalTaskStore(root, runtime_root=runtime)
    task = store.create(
        "Review database architecture and production migration safety",
        blueprint_path="docs/BLUEPRINT_V6.md",
    )
    queue = LocalJobQueue(root, runtime_root=runtime)
    job = queue.enqueue(task_id=task.id, kind=JobKind.PLAN, priority=100)

    fake_coder = SimpleNamespace(
        store=store,
        router=SimpleNamespace(profiles=(
            ModelProfile(
                "llama_cpp", "qwen2.5-coder:1.5b",
                capability=1, cost_tier=0, local=True,
                roles=("planner",),
            ),
        )),
    )
    monkeypatch.setattr(
        "empire_os.coder.plan_delegation.EmpireCoder",
        lambda *a, **k: fake_coder,
    )
    captured = {}
    def dispatch(root_arg, request):
        captured["request"] = request
        return {"status":"QUEUED","worker":"hermes"}
    monkeypatch.setattr(
        "empire_os.coder.plan_delegation.dispatch_execution_request",
        dispatch,
    )

    result = delegate_oversized_plans(root, runtime_root=runtime, max_jobs=1)

    assert result["delegated_count"] == 1
    delegated = queue.get(job.id)
    assert delegated.status is JobStatus.DELEGATED
    req = captured["request"]
    assert req.authority == "observe"
    assert req.capability == "backend_code"
    assert req.allowed_paths == ()
    assert req.lease_resources == ()
    assert "PLAN ONLY" in req.objective


def test_simple_plan_stays_local(monkeypatch, tmp_path):
    root, runtime = _workspace(tmp_path)
    store = LocalTaskStore(root, runtime_root=runtime)
    task = store.create("Explain current state", blueprint_path="docs/BLUEPRINT_V6.md")
    queue = LocalJobQueue(root, runtime_root=runtime)
    job = queue.enqueue(task_id=task.id, kind=JobKind.PLAN)
    fake_coder = SimpleNamespace(
        store=store,
        router=SimpleNamespace(profiles=(
            ModelProfile(
                "llama_cpp", "qwen2.5-coder:1.5b",
                capability=1, cost_tier=0, local=True,
                roles=("planner",),
            ),
        )),
    )
    monkeypatch.setattr(
        "empire_os.coder.plan_delegation.EmpireCoder",
        lambda *a, **k: fake_coder,
    )
    monkeypatch.setattr(
        "empire_os.coder.plan_delegation.dispatch_execution_request",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must stay local")),
    )

    result = delegate_oversized_plans(root, runtime_root=runtime, max_jobs=1)
    assert result["delegated_count"] == 0
    assert result["skipped_local_count"] == 1
    assert queue.get(job.id).status is JobStatus.PENDING


def test_successful_hermes_plan_reconciles_then_retires_context(monkeypatch, tmp_path):
    root, runtime = _workspace(tmp_path)
    store = LocalTaskStore(root, runtime_root=runtime)
    audit = AuditTrail(runtime)
    memory = ContextMemory(store, audit)
    task = store.create(
        "Review database architecture",
        blueprint_path="docs/BLUEPRINT_V6.md",
    )
    memory.refresh(task.id, trigger="seed")
    queue = LocalJobQueue(root, runtime_root=runtime)
    job = queue.enqueue(task_id=task.id, kind=JobKind.PLAN)
    queue.delegate_pending(
        job.id,
        delegation={"worker":"hermes","request_id":f"coder-plan-{job.id}"},
    )
    monkeypatch.setattr(
        "empire_os.coder.plan_delegation.fetch_control_refs",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "empire_os.coder.plan_delegation.control_path_exists",
        lambda *a, **k: True,
    )
    monkeypatch.setattr(
        "empire_os.coder.plan_delegation.read_control_json",
        lambda *a, **k: {
            "status":"COMPLETED_NO_CHANGES",
            "hermes":{
                "model":"openrouter/example",
                "output_tail":"1. Inspect owner. 2. Add focused tests. 3. Verify.",
            },
        },
    )

    result = reconcile_delegated_plans(root, runtime_root=runtime)

    assert result["reconciled_count"] == 1
    terminal = queue.get(job.id)
    assert terminal.status is JobStatus.COMPLETED
    proposal = store.latest_proposal(task.id)
    assert proposal["provider"] == "hermes_control"
    assert proposal["actionable"] is False
    assert "focused tests" in proposal["refined"]
    assert not (runtime / "context" / f"{task.id}.json").exists()
    assert (runtime / "context_retired" / f"{task.id}.json").exists()


def test_local_planner_environment_loads_only_allowlisted_keys(monkeypatch, tmp_path):
    from empire_os.coder import plan_delegation as module
    root, _ = _workspace(tmp_path)
    (root / ".env.empire_coder").write_text(
        "EMPIRE_CODER_LLAMA_CPP_ENABLED=true\n"
        "EMPIRE_CODER_LLAMA_CPP_CAPABILITY=2\n"
        "SECRET_SHOULD_NOT_LOAD=nope\n"
    )
    monkeypatch.delenv("EMPIRE_CODER_LLAMA_CPP_ENABLED", raising=False)
    monkeypatch.delenv("EMPIRE_CODER_LLAMA_CPP_CAPABILITY", raising=False)
    monkeypatch.delenv("SECRET_SHOULD_NOT_LOAD", raising=False)
    module._load_local_planner_environment(root)
    assert __import__('os').environ["EMPIRE_CODER_LLAMA_CPP_ENABLED"] == "true"
    assert __import__('os').environ["EMPIRE_CODER_LLAMA_CPP_CAPABILITY"] == "2"
    assert "SECRET_SHOULD_NOT_LOAD" not in __import__('os').environ


def test_unreadable_legacy_task_does_not_block_next_delegatable_job(monkeypatch, tmp_path):
    root, runtime = _workspace(tmp_path)
    store = LocalTaskStore(root, runtime_root=runtime)
    bad = store.create("Review database architecture old", blueprint_path="docs/BLUEPRINT_V6.md")
    good = store.create("Review database architecture current", blueprint_path="docs/BLUEPRINT_V6.md")
    queue = LocalJobQueue(root, runtime_root=runtime)
    bad_job = queue.enqueue(task_id=bad.id, kind=JobKind.PLAN, priority=100)
    good_job = queue.enqueue(task_id=good.id, kind=JobKind.PLAN, priority=99)
    real_load = store.load
    def load(task_id):
        if task_id == bad.id:
            raise PermissionError("legacy root-owned task")
        return real_load(task_id)
    fake_store = SimpleNamespace(load=load)
    fake_coder = SimpleNamespace(
        store=fake_store,
        router=SimpleNamespace(profiles=(
            ModelProfile(
                "llama_cpp", "qwen2.5-coder:1.5b",
                capability=1, cost_tier=0, local=True,
                roles=("planner",),
            ),
        )),
    )
    monkeypatch.setattr(
        "empire_os.coder.plan_delegation.EmpireCoder",
        lambda *a, **k: fake_coder,
    )
    monkeypatch.setattr(
        "empire_os.coder.plan_delegation.dispatch_execution_request",
        lambda *a, **k: {"status":"QUEUED","worker":"hermes"},
    )
    result = delegate_oversized_plans(root, runtime_root=runtime, max_jobs=1)
    assert result["blocked_count"] == 1
    assert result["blocked"][0]["job_id"] == bad_job.id
    assert queue.get(bad_job.id).status is JobStatus.PENDING
    assert queue.get(good_job.id).status is JobStatus.DELEGATED
