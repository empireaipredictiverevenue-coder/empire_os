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
