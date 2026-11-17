"""Codex candidate test boundary: original trusted OS tests vs model-owned tests.

No model-produced content is ever executed in the host preflight.
"""
from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from empire_os.empire_coder_sandbox_runner import (
    TRUSTED_NAMESPACE_TESTS,
    _candidate_test_command,
    _trusted_namespace_function_hashes,
    _trusted_namespace_preflight,
    _verify_trusted_namespace_funcs_unchanged,
)


def _get_test_source() -> str:
    source_root = Path(__file__).resolve().parents[2]
    return (source_root / "tests/coder/test_isolated_implement_drain.py").read_text()


def test_namespace_exception_exact_existing_test_functions_only():
    path = "tests/coder/test_isolated_implement_drain.py"
    names = TRUSTED_NAMESPACE_TESTS[path]
    hashes = _trusted_namespace_function_hashes(_get_test_source(), test_names=names)
    assert hashes is not None and len(hashes) == 3
    assert all(len(value) == 64 for value in hashes.values())
    altered = _get_test_source().replace(
        "def test_dirty_local_source_blocks_candidate_model_before_inference",
        "def test_dirty_local_source_blocks_candidate_model_before_inference_else",
    )
    assert _trusted_namespace_function_hashes(
        altered, test_names=names,
    ) is None


def test_unrelated_suite_has_no_os_namespace_bypass(tmp_path):
    assert _trusted_namespace_preflight(
        clone=tmp_path, python=Path("/usr/bin/python3"),
        targets=("tests/test_safe.py",), time_budget=65,
    ) == {}
    args = _candidate_test_command(
        clone=tmp_path, python=Path("/usr/bin/python3"),
        targets=("tests/test_safe.py",), trusted_baseline={},
    )
    if args is not None:
        assert "--deselect" not in args


def test_pristine_baseline_passes_and_mutated_candidate_cannot_bypass(tmp_path):
    source_root = Path(__file__).resolve().parents[2]
    clone = tmp_path / "baseline"
    subprocess.run(
        ("git", "clone", "--quiet", "--no-hardlinks", "--single-branch",
         "--branch", "agent/data-cloud-wave4", str(source_root), str(clone)),
        check=True, capture_output=True, timeout=90,
    )
    target = "tests/coder/test_isolated_implement_drain.py"
    base = _trusted_namespace_preflight(
        clone=clone, python=source_root / ".venv/bin/python",
        targets=(target,), time_budget=80,
    )
    assert base is not None
    assert base["mode"] == "TRUSTED_BASELINE_NO_NEW_PRIVS"
    assert base["baseline_test_count"] == 3
    assert _verify_trusted_namespace_funcs_unchanged(clone, base)

    argv = _candidate_test_command(
        clone=clone, python=source_root / ".venv/bin/python",
        targets=(target,), trusted_baseline=base,
    )
    assert argv is not None
    assert "--unshare-all" in argv
    assert "--share-net" not in argv
    assert argv.count("--deselect") == 3
    for name in base["test_names"]:
        assert f"{target}::{name}" in argv

    path = clone / target
    original = path.read_text()
    path.write_text(original.replace(
        "def test_original_candidate_tests_cannot_read_production_or_use_network",
        "def test_original_candidate_tests_cannot_read_production_or_use_network_x",
    ))
    assert not _verify_trusted_namespace_funcs_unchanged(clone, base)
    assert _candidate_test_command(
        clone=clone, python=source_root / ".venv/bin/python",
        targets=(target,), trusted_baseline=base,
    ) is None


def test_unavailable_trusted_runtime_fails_closed(tmp_path, monkeypatch):
    import empire_os.empire_coder_sandbox_runner as runner
    target = "tests/coder/test_isolated_implement_drain.py"
    path = tmp_path / target
    path.parent.mkdir(parents=True)
    path.write_text(_get_test_source())
    original_which = runner.shutil.which
    monkeypatch.setattr(
        runner.shutil, "which",
        lambda program: None if program == "setpriv" else original_which(program),
    )
    assert _trusted_namespace_preflight(
        clone=tmp_path, python=Path("/usr/bin/python3"),
        targets=(target,), time_budget=60,
    ) is None


def test_missing_protected_test_function_fails_closed(tmp_path):
    target = "tests/coder/test_isolated_implement_drain.py"
    path = tmp_path / target
    path.parent.mkdir(parents=True)
    path.write_text("def test_unrelated():\n    assert True\n")
    assert _trusted_namespace_preflight(
        clone=tmp_path, python=Path("/usr/bin/python3"),
        targets=(target,), time_budget=60,
    ) is None


def test_failed_hermes_namespace_preflight_records_only_sanitized_evidence(
    tmp_path, monkeypatch,
):
    import json
    import empire_os.empire_coder_sandbox_runner as runner

    relative = "tests/coder/test_isolated_implement_drain.py"
    file = tmp_path / relative
    file.parent.mkdir(parents=True)
    file.write_text(_get_test_source())
    unexpected = "SECRET_VALUE_MUST_NOT_BE_WRITTEN"
    monkeypatch.setattr(
        runner, "_run",
        lambda *_a, **_k: subprocess.CompletedProcess(
            ["setpriv"], 1,
            stdout=(
                "FAILED tests/coder/test_isolated_implement_drain.py::"
                "test_original_candidate_tests_cannot_read_production_or_use_network\n"
            ),
            stderr="No permissions to create a new namespace " + unexpected,
        ),
    )
    evidence = runner._trusted_namespace_preflight(
        clone=tmp_path,
        python=Path("/usr/bin/python3"),
        targets=(relative,), time_budget=65,
        diagnostics_root=tmp_path,
    )
    assert evidence is None
    path = (
        tmp_path / "runtime/execution_plane/"
        "coder_namespace_preflight_latest.json"
    )
    packet = json.loads(path.read_text())
    assert packet["reason"] == "trusted_original_integration_tests_failed"
    assert packet["exit_code"] == 1
    assert packet["saw_namespace_permission_denied"] is True
    assert len(packet["failing_named_tests"]) == 1
    assert packet["production_mutation"] is False
    assert unexpected not in path.read_text()
    assert path.stat().st_mode & 0o777 == 0o600


def _patch_retry_test_repo(tmp_path):
    import sys
    from empire_os.empire_coder_sandbox_runner import EmpireCoderSandboxJob
    repo = tmp_path / "small-source"
    repo.mkdir()
    subprocess.run(("git", "init", "-q", str(repo)), check=True)
    (repo / "app.py").write_text("VALUE = 1\n")
    subprocess.run(("git", "add", "app.py"), cwd=repo, check=True)
    subprocess.run(
        ("git", "-c", "user.name=Test", "-c",
         "user.email=test@example.com", "commit", "-qm", "baseline"),
        cwd=repo, check=True,
    )
    job = EmpireCoderSandboxJob(
        job_id="one-valid-retry-test",
        objective="Change one harmless fixture.",
        department="engineering", capability="backend_code",
        allowed_paths=("app.py",),
        lease_resources=("path:app.py",),
        pytest_targets=("tests/test_app.py",),
        base_branch="agent/data-cloud-wave4",
    )
    valid_patch = (
        "diff --git a/app.py b/app.py\n"
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -1 +1 @@\n"
        "-VALUE = 1\n"
        "+VALUE = 2\n"
    )
    return repo, job, valid_patch


def test_one_model_regeneration_can_produce_a_valid_scoped_patch(tmp_path):
    import sys
    from empire_os.empire_coder_sandbox_runner import (
        _apply_model_patch_with_one_bounded_retry,
    )
    repo, job, valid = _patch_retry_test_repo(tmp_path)
    model = [
        sys.executable, "-c",
        "import sys; sys.stdin.read(); sys.stdout.write(" + repr(valid) + ")",
    ]
    count, error = _apply_model_patch_with_one_bounded_retry(
        clone=repo, job=job,
        first_response="this is not a git patch",
        model_command=model, model_env={"PATH": "/usr/bin:/bin"},
        original_prompt="Return only a diff for this exact code",
        remaining_seconds=110,
    )
    assert count == 2
    assert error is None
    assert (repo / "app.py").read_text() == "VALUE = 2\n"


def test_valid_first_model_patch_does_not_issue_an_extra_request(tmp_path):
    from empire_os.empire_coder_sandbox_runner import (
        _apply_model_patch_with_one_bounded_retry,
    )
    repo, job, valid = _patch_retry_test_repo(tmp_path)
    count, error = _apply_model_patch_with_one_bounded_retry(
        clone=repo, job=job,
        first_response=valid,
        model_command=["/unavailable-model-binary"],
        model_env={}, original_prompt="no retries permitted",
        remaining_seconds=100,
    )
    assert count == 1 and error is None
    assert (repo / "app.py").read_text() == "VALUE = 2\n"


def test_second_invalid_patch_remains_terminal_without_source_modification(
    tmp_path,
):
    import sys
    from empire_os.empire_coder_sandbox_runner import (
        _apply_model_patch_with_one_bounded_retry,
    )
    repo, job, _ = _patch_retry_test_repo(tmp_path)
    count, error = _apply_model_patch_with_one_bounded_retry(
        clone=repo, job=job,
        first_response="invalid",
        model_command=[sys.executable, "-c", "print('NO_PATCH')"],
        model_env={"PATH": "/usr/bin:/bin"}, original_prompt="bounded retry",
        remaining_seconds=110,
    )
    assert count == 2
    assert error == "tool_free_patch_invalid_or_unapplicable"
    assert (repo / "app.py").read_text() == "VALUE = 1\n"


def test_insufficient_budget_refuses_second_model_call(tmp_path):
    from empire_os.empire_coder_sandbox_runner import (
        _apply_model_patch_with_one_bounded_retry,
    )
    repo, job, _ = _patch_retry_test_repo(tmp_path)
    count, error = _apply_model_patch_with_one_bounded_retry(
        clone=repo, job=job,
        first_response="bad text",
        model_command=["/unavailable-model-binary"],
        model_env={}, original_prompt="no extra budget",
        remaining_seconds=12,
    )
    assert count == 1
    assert error == "invalid_patch_and_retry_time_budget_exhausted"
    assert (repo / "app.py").read_text() == "VALUE = 1\n"
