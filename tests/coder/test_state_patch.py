import os

import pytest

from empire_os.coder.models import TaskPhase, TaskStatus
from empire_os.coder.patch import PatchEngine, PatchError
from empire_os.coder.state import LocalTaskStore, compact_task_context


def workspace(tmp_path):
    (tmp_path / ".git").mkdir()
    return tmp_path


def test_task_state_survives_reload_and_is_private(tmp_path):
    root = workspace(tmp_path)
    runtime = root / "runtime"
    store = LocalTaskStore(root, runtime)
    task = store.create("Improve Empire Coder retrieval", blueprint_path="docs/BLUEPRINT_V6.md")
    task.plan = ["inspect", "patch", "verify"]
    task.phase = TaskPhase.SEARCH_REPO
    task.status = TaskStatus.RUNNING
    task.unresolved_issues.append("need import graph")
    store.save(task)
    restored = store.load(task.id)
    assert restored.objective == task.objective
    assert restored.phase is TaskPhase.SEARCH_REPO
    assert restored.unresolved_issues == ["need import graph"]
    assert compact_task_context(restored)["objective"] == task.objective
    path = runtime / "tasks" / f"{task.id}.json"
    assert os.stat(path).st_mode & 0o777 == 0o600


def test_patch_requires_read_and_supports_rollback(tmp_path):
    root = workspace(tmp_path)
    target = root / "sample.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")
    engine = PatchEngine(root, runtime_root=root / "runtime")
    with pytest.raises(PatchError, match="read-before-write"):
        engine.replace_exact("task_1", "sample.py", "1", "2")
    assert engine.read("sample.py") == "VALUE = 1\n"
    result = engine.replace_exact("task_1", "sample.py", "VALUE = 1", "VALUE = 2")
    assert result["before_sha256"] != result["after_sha256"]
    assert target.read_text() == "VALUE = 2\n"
    restored = engine.rollback("task_1")
    assert "sample.py" in restored
    assert target.read_text() == "VALUE = 1\n"


def test_create_file_rolls_back_to_absent(tmp_path):
    root = workspace(tmp_path)
    engine = PatchEngine(root, runtime_root=root / "runtime")
    engine.create_file("task_2", "new_module.py", "X = 1\n")
    assert (root / "new_module.py").exists()
    engine.rollback("task_2")
    assert not (root / "new_module.py").exists()


def test_proposal_state_survives_compaction(tmp_path):
    root = workspace(tmp_path)
    store = LocalTaskStore(root, root / "runtime")
    task = store.create("Polish coder output", blueprint_path="docs/BLUEPRINT_V6.md")
    store.save_proposal(task.id, {
        "task_id": task.id,
        "provider": "ollama",
        "model": "qwen3-coder:30b",
        "stage": "REFINED",
        "draft": "draft",
        "critique": "critique",
        "refined": "better",
        "revision_count": 1,
        "actionable": True,
    })
    latest = store.latest_proposal(task.id)
    assert latest["stage"] == "REFINED"
    assert latest["revision_count"] == 1
    assert latest["actionable"] is True
    proposal_dir = root / "runtime" / "proposals" / task.id
    assert proposal_dir.is_dir()
    assert all((p.stat().st_mode & 0o777) == 0o600 for p in proposal_dir.glob("*.json"))
