import json
import subprocess

import empire_os.execution_plane_promptfoo as module
from empire_os.execution_plane_promptfoo import (
    run_pending_promptfoo,
    run_promptfoo_request,
)


def write_request(root, request_id="ai-1"):
    patch = (
        root
        / "runtime/execution_plane/candidate_patches"
        / f"{request_id}.patch"
    )
    patch.parent.mkdir(parents=True, exist_ok=True)
    patch.write_text("diff --git a/x b/x\n", encoding="utf-8")
    path = (
        root
        / "runtime/execution_plane/promptfoo_requests"
        / f"{request_id}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema_version": "empire.execution-plane-promptfoo-request.v1",
        "request_id": request_id,
        "candidate_ref": "pi/job-ai-1",
        "candidate_patch_path": str(
            patch.relative_to(root)
        ),
        "config": "evals/empire_core_policy/promptfooconfig.yaml",
        "required": True,
        "production_promotion_allowed": False,
        "execution_authority": "none",
    }), encoding="utf-8")
    return path


def test_promptfoo_pass_is_persisted_but_never_auto_promoted(
    tmp_path,
    monkeypatch,
):
    request = write_request(tmp_path)
    binary = tmp_path / "promptfoo"
    binary.write_text("", encoding="utf-8")
    monkeypatch.setattr(module, "PROMPTFOO_BIN", binary)

    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            0,
            stdout="6 passed",
            stderr="",
        ),
    )
    result = run_promptfoo_request(tmp_path, request)

    assert result["status"] == "PASSED"
    assert result["passed"] is True
    assert result["production_promotion_allowed"] is False
    assert result["execution_authority"] == "none"


def test_promptfoo_failure_is_persisted(tmp_path, monkeypatch):
    request = write_request(tmp_path, "ai-2")
    binary = tmp_path / "promptfoo"
    binary.write_text("", encoding="utf-8")
    monkeypatch.setattr(module, "PROMPTFOO_BIN", binary)
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            1,
            stdout="5 passed, 1 failed",
            stderr="",
        ),
    )
    result = run_promptfoo_request(tmp_path, request)
    assert result["status"] == "FAILED"
    assert result["passed"] is False


def test_pending_worker_skips_completed_requests(tmp_path, monkeypatch):
    write_request(tmp_path, "ai-3")
    binary = tmp_path / "promptfoo"
    binary.write_text("", encoding="utf-8")
    monkeypatch.setattr(module, "PROMPTFOO_BIN", binary)
    calls = []

    def fake_run(*args, **kwargs):
        calls.append(1)
        return subprocess.CompletedProcess(args[0], 0, stdout="ok", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    first = run_pending_promptfoo(tmp_path)
    second = run_pending_promptfoo(tmp_path)

    assert first["processed_count"] == 1
    assert second["processed_count"] == 0
    assert len(calls) == 1



def test_request_rejects_patch_outside_runtime(tmp_path, monkeypatch):
    request = write_request(tmp_path, "ai-4")
    raw = json.loads(request.read_text(encoding="utf-8"))
    outside = tmp_path / "outside.patch"
    outside.write_text("x", encoding="utf-8")
    raw["candidate_patch_path"] = "outside.patch"
    request.write_text(json.dumps(raw), encoding="utf-8")
    binary = tmp_path / "promptfoo"
    binary.write_text("", encoding="utf-8")
    monkeypatch.setattr(module, "PROMPTFOO_BIN", binary)

    import pytest
    with pytest.raises(ValueError, match="candidate patch"):
        run_promptfoo_request(tmp_path, request)
