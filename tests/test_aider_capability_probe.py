from pathlib import Path

import empire_os.aider_capability_probe as probe_module
from empire_os.aider_capability_probe import (
    MARKER_PATH,
    MARKER_TEXT,
    probe_aider_mutation,
)


def test_aider_probe_records_exact_bounded_mutation(
    tmp_path,
    monkeypatch,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    clone_holder = {}

    def fake_run(argv, *, cwd, timeout=180):
        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        if argv[:2] == ["git", "clone"]:
            clone = Path(argv[-1])
            clone.mkdir(parents=True)
            (clone / ".git").mkdir()
            clone_holder["path"] = clone
        return Result()

    def fake_mutation(workspace, request):
        marker = Path(workspace) / MARKER_PATH
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(MARKER_TEXT, encoding="utf-8")
        return {
            "status": "EDITED",
            "changed_paths": [MARKER_PATH],
            "execution_authority": "none",
        }

    recorded = {}

    monkeypatch.setattr(probe_module, "_run", fake_run)
    monkeypatch.setattr(
        probe_module,
        "run_aider_mutation",
        fake_mutation,
    )
    monkeypatch.setattr(
        probe_module,
        "record_builder_capability",
        lambda worker, capability, **kwargs: recorded.update({
            "worker": worker,
            "capability": capability,
            **kwargs,
        }),
    )

    result = probe_aider_mutation(
        repo,
        work_root=tmp_path / "work",
    )

    assert result.ok is True
    assert result.reason == "aider_mutation_ready"
    assert result.changed_paths == (MARKER_PATH,)
    assert result.production_mutation is False
    assert result.production_push is False
    assert recorded["worker"] == "empire_coder"
    assert recorded["capability"] == "aider_mutation"
    assert recorded["ready"] is True


def test_aider_probe_fails_when_extra_path_changes(
    tmp_path,
    monkeypatch,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    def fake_run(argv, *, cwd, timeout=180):
        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        if argv[:2] == ["git", "clone"]:
            clone = Path(argv[-1])
            clone.mkdir(parents=True)
            (clone / ".git").mkdir()
        return Result()

    def fake_mutation(workspace, request):
        marker = Path(workspace) / MARKER_PATH
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(MARKER_TEXT, encoding="utf-8")
        return {
            "status": "PATH_POLICY_FAILED",
            "reason": "changed_path_outside_allowlist",
            "changed_paths": [
                MARKER_PATH,
                "empire_os/unexpected.py",
            ],
        }

    recorded = {}
    monkeypatch.setattr(probe_module, "_run", fake_run)
    monkeypatch.setattr(
        probe_module,
        "run_aider_mutation",
        fake_mutation,
    )
    monkeypatch.setattr(
        probe_module,
        "record_builder_capability",
        lambda worker, capability, **kwargs: recorded.update({
            "worker": worker,
            "capability": capability,
            **kwargs,
        }),
    )

    result = probe_aider_mutation(
        repo,
        work_root=tmp_path / "work",
    )

    assert result.ok is False
    assert result.production_mutation is False
    assert recorded["ready"] is False
