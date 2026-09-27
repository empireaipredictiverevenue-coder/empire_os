from empire_os.coder.orchestrator import EmpireCoder


def make_repo(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/BLUEPRINT_V6.md").write_text(
        "# Blueprint\nEmpire Coder stays OBSERVE.\n"
    )
    pkg = tmp_path / "empire_os"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "sample.py").write_text("def value():\n    return 1\n")
    return tmp_path


def test_context_refreshes_after_significant_actions(tmp_path):
    root = make_repo(tmp_path)
    coder = EmpireCoder(root)
    task = coder.create_task("Improve sample safely")
    first = coder.memory.load(task.id)
    assert first is not None
    assert first["version"] >= 1

    pack = coder.build_context(task.id, terms=["value"], symbols=["value"])
    second = coder.memory.load(task.id)
    assert second["version"] > first["version"]
    assert second["trigger"] == "context_ready"
    assert pack.task_state["version"] == second["version"]

    coder.read_for_patch(task.id, "empire_os/sample.py")
    third = coder.memory.load(task.id)
    assert third["version"] > second["version"]
    assert third["trigger"] == "file_read_for_patch"


def test_context_is_bounded_and_keeps_latest_proposal(tmp_path):
    root = make_repo(tmp_path)
    coder = EmpireCoder(root)
    task = coder.create_task("Long running coder task")

    for index in range(60):
        coder.audit.record(
            task_id=task.id,
            event=f"event_{index}",
            data={"path": f"file_{index}.py", "ignored": "x" * 10000},
        )
    coder.store.save_proposal(task.id, {
        "provider": "ollama",
        "model": "qwen3-coder:30b",
        "stage": "REFINED",
        "revision_count": 2,
        "actionable": False,
        "refined": "r" * 10000,
    })
    snapshot = coder._sync_context(task.id, "test_compaction")

    assert len(snapshot["recent_events"]) <= 24
    assert len(snapshot["latest_proposal"]["refined"]) == 4000
    assert snapshot["latest_proposal"]["model"] == "qwen3-coder:30b"


def test_restarted_coder_recovers_context_without_chat_history(tmp_path):
    root = make_repo(tmp_path)
    coder = EmpireCoder(root)
    task = coder.create_task("Recover me")
    coder.build_context(task.id, terms=["value"])

    before = coder.memory.load(task.id)
    restarted = EmpireCoder(root)
    restored_task = restarted.load_task(task.id)
    after = restarted.memory.load(task.id)

    assert restored_task.objective == "Recover me"
    assert after["version"] == before["version"]
    assert after["task"]["phase"] == before["task"]["phase"]


def test_model_context_uses_latest_recovery_snapshot(tmp_path):
    root = make_repo(tmp_path)
    coder = EmpireCoder(root)
    task = coder.create_task("Use fresh context")
    pack = coder.build_context(task.id, terms=["value"])
    version = pack.task_state["version"]

    coder.read_for_patch(task.id, "empire_os/sample.py")
    fresh = coder._fresh_context_pack(
        task.id,
        pack,
        trigger="unit_test_before_model",
    )

    assert fresh.task_state["version"] > version
    assert fresh.task_state["trigger"] == "unit_test_before_model"
    assert fresh.task_state["task"]["objective"] == "Use fresh context"
    assert "plan_steps" not in fresh.task_state["task"]


def test_model_view_is_smaller_than_durable_recovery_snapshot(tmp_path):
    import json

    root = make_repo(tmp_path)
    coder = EmpireCoder(root)
    task = coder.create_task("Keep durable memory rich but model context lean")

    for index in range(30):
        coder.audit.record(
            task_id=task.id,
            event=f"event_{index}",
            data={"path": f"file_{index}.py"},
        )
    coder.store.save_proposal(task.id, {
        "provider": "ollama",
        "model": "qwen3-coder:30b",
        "stage": "REFINED",
        "revision_count": 1,
        "actionable": True,
        "refined": "x" * 4000,
    })
    full = coder._sync_context(task.id, "model_view_test")
    lean = coder.memory.model_view(task.id)

    assert lean["version"] == full["version"]
    assert lean["task"]["objective"] == task.objective
    assert len(lean["recent_events"]) <= 8
    assert len(lean["latest_proposal"]["refined"]) <= 800
    assert "plan_steps" not in lean["task"]
    assert len(json.dumps(lean)) < len(json.dumps(full))
