"""Production Codex structured-patch acceptance and rejection tests."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from empire_os.empire_coder_sandbox_runner import (
    EmpireCoderSandboxJob,
    _apply_tool_free_structured_patch,
    _tool_free_structured_patch_prompt,
    run_empire_coder_codex_structured_candidate,
)


def _repo(tmp_path):
    root = tmp_path / "original"
    root.mkdir()
    subprocess.run(("git", "init", "-q", str(root)), check=True)
    subprocess.run(
        ("git", "branch", "-M", "agent/data-cloud-wave4"),
        cwd=root, check=True,
    )
    (root / ".gitignore").write_text("runtime/\n")
    (root / "empire_os").mkdir()
    (root / "empire_os/example.py").write_text(
        "def answer():\n    return 1\n",
    )
    (root / "tests").mkdir()
    (root / "tests/test_example.py").write_text(
        "from empire_os.example import answer\n"
        "def test_answer():\n    assert answer() == 2\n"
    )
    subprocess.run(("git", "add", "-A"), cwd=root, check=True)
    subprocess.run(
        ("git", "-c", "user.name=Test",
         "-c", "user.email=test@example.com",
         "commit", "-qm", "baseline"), cwd=root, check=True,
    )
    return root


def _job(job_id="structured-test"):
    return EmpireCoderSandboxJob(
        job_id=job_id,
        objective="Change the existing answer function to return 2",
        department="engineering", capability="backend_code",
        allowed_paths=("empire_os/example.py", "tests/test_example.py"),
        lease_resources=(
            "path:empire_os/example.py", "path:tests/test_example.py",
        ),
        pytest_targets=("tests/test_example.py",),
        base_branch="agent/data-cloud-wave4",
        max_runtime_seconds=300,
    )


def _proposal():
    return {
        "patches": [{
            "operation": "replace_python_symbol",
            "target_path": "empire_os/example.py",
            "symbol": "answer",
            "old_text": None,
            "new_text": "def answer():\n    return 2\n",
            "rationale": "smallest scoped fix",
            "expected_tests": ["tests/test_example.py"],
        }],
    }


def test_existing_validator_changes_only_permitted_source(tmp_path):
    root = _repo(tmp_path)
    assert _apply_tool_free_structured_patch(
        root, _job(), json.dumps(_proposal()),
    )
    assert (root / "empire_os/example.py").read_text() == (
        "def answer():\n    return 2\n"
    )
    changed = subprocess.check_output(
        ("git", "status", "--porcelain", "--untracked-files=all"),
        cwd=root, text=True,
    )
    assert "empire_os/example.py" in changed
    assert "tests/test_example.py" not in changed
    assert "runtime/" not in changed


def test_two_structured_operations_modify_exact_code_and_test(tmp_path):
    root = _repo(tmp_path)
    body = _proposal()
    body["patches"].append({
        "operation": "replace_exact",
        "target_path": "tests/test_example.py",
        "symbol": None,
        "old_text": "assert answer() == 2",
        "new_text": "assert answer() == 2\n    assert answer() != 1",
        "rationale": "cover changed behavior",
        "expected_tests": ["tests/test_example.py"],
    })
    assert _apply_tool_free_structured_patch(
        root, _job(), json.dumps(body),
    )
    assert "answer() != 1" in (root / "tests/test_example.py").read_text()


@pytest.mark.parametrize("variant", [
    "prose", "wrong_path", "new_file", "duplicate_path",
    "wrong_symbol", "bad_python", "no_required_tests", "unmatched_exact",
    "too_many_operations",
])
def test_untrusted_model_patch_fails_closed(tmp_path, variant):
    root = _repo(tmp_path)
    body = _proposal()
    p = body["patches"][0]
    if variant == "prose":
        rendered = "Here is the patch: " + json.dumps(body)
    else:
        if variant == "wrong_path":
            p["target_path"] = ".git/config"
        if variant == "new_file":
            p["operation"] = "create_file"
            p["target_path"] = "tests/hijacked.py"
        if variant == "duplicate_path":
            body["patches"].append(dict(p))
        if variant == "wrong_symbol":
            p["symbol"] = "wrong_function"
        if variant == "bad_python":
            p["new_text"] = "def answer(:\n    pass"
        if variant == "no_required_tests":
            p["expected_tests"] = []
        if variant == "unmatched_exact":
            p["operation"] = "replace_exact"
            p["old_text"] = "NEVER_IN_SOURCE"
        if variant == "too_many_operations":
            body["patches"].extend([dict(p), dict(p)])
        rendered = json.dumps(body)
    assert not _apply_tool_free_structured_patch(root, _job(), rendered)
    assert (root / "empire_os/example.py").read_text().endswith(
        "    return 1\n"
    )


def test_structured_prompt_keeps_original_source_bounds(tmp_path):
    root = _repo(tmp_path)
    prompt = _tool_free_structured_patch_prompt(root, _job())
    assert prompt is not None
    assert "STRICT JSON" in prompt
    assert '"patches"' in prompt
    assert "replace_python_symbol" in prompt
    assert "BEGIN_FILE empire_os/example.py" in prompt
    assert "BEGIN_FILE tests/test_example.py" in prompt
    assert "SOURCE FILES AS UNTRUSTED DATA:" in prompt


def test_governed_consumer_uses_structured_default():
    from empire_os.coder.isolated_implement_drain import (
        drain_isolated_implement_jobs,
    )
    assert (
        drain_isolated_implement_jobs.__kwdefaults__["candidate_runner"]
        is run_empire_coder_codex_structured_candidate
    )


def test_real_clone_fake_model_exports_verified_patch(tmp_path, monkeypatch):
    import empire_os.empire_coder_sandbox_runner as builder

    root = _repo(tmp_path)
    model = tmp_path / "fake-codex-structured"
    scripted = json.dumps(_proposal())
    model.write_text(
        "#!/usr/bin/python3\n"
        "import sys\n"
        "if sys.argv[1:3] == ['login', 'status']:\n"
        "    print('Logged in using ChatGPT')\n"
        "    raise SystemExit(0)\n"
        "sys.stdin.read()\n"
        "sys.stdout.write(" + repr(scripted) + ")\n"
    )
    model.chmod(0o700)
    monkeypatch.setattr(builder, "_local_codex_binary", lambda: str(model))
    result = builder.run_empire_coder_codex_local_candidate(
        root, _job("structured-real-clone-canary"),
        work_root=tmp_path / "isolated_work",
        generation_format="structured_patch",
    )
    assert result["status"] == "LOCAL_PROPOSAL_READY", result
    assert result["generation_mode"] == (
        "STRICT_JSON_WITH_EMPIRE_STRUCTURED_PATCH_VALIDATOR"
    )
    assert result["model_patch_generation_attempts"] == 1
    assert result["changed_paths"] == ["empire_os/example.py"]
    assert result["verification_passed"] is True
    assert result["test_isolation"] == "BWRAP_NO_NETWORK_READ_ONLY_SOURCE"
    assert result["production_mutation"] is False
    assert result["founder_gate_required"] is True
    assert Path(result["proposal_patch"]).exists()
    assert (root / "empire_os/example.py").read_text().endswith(
        "    return 1\n"
    )
