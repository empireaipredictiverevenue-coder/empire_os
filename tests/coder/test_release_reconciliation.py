"""Release reconciliation is a separate, founder-gated, SHA-bound step."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys

import pytest

from empire_os.coder.models import TaskStatus, VerificationVerdict
from empire_os.coder.orchestrator import EmpireCoder, EmpireCoderError


def _run(root, *args):
    return subprocess.run(args, cwd=root, check=True, capture_output=True, text=True)


@pytest.fixture
def candidate(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _run(root, "git", "init", "-q")
    (root / "docs").mkdir()
    (root / "docs/BLUEPRINT_V6.md").write_text("# Blueprint\n")
    (root / "app.py").write_text("VALUE = 1\n")
    (root / "tests").mkdir()
    (root / "tests/test_smoke.py").write_text(
        "def test_ok():\n    assert 1 + 1 == 2\n"
    )
    _run(root, "git", "add", "app.py", "tests/test_smoke.py")
    _run(root, "git", "-c", "user.name=Test", "-c",
         "user.email=test@example.com", "commit", "-qm", "baseline")
    coder = EmpireCoder(root)
    task = coder.create_task("Correct one small guarded application value")
    coder.read_for_patch(task.id, "app.py")
    coder.patch_exact(task.id, "app.py", "VALUE = 1", "VALUE = 2")
    report = coder.verify(
        task.id, changed_files=("app.py",),
        commands=((sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                   "tests/test_smoke.py"),),
    )
    assert report.verdict is VerificationVerdict.PASS
    _run(root, "git", "add", "--", "app.py")
    _run(root, "git", "-c", "user.name=Test",
         "-c", "user.email=test@example.com", "commit", "-qm", "verified change")
    sha = _run(root, "git", "rev-parse", "HEAD").stdout.strip()
    receipt_dir = root / "runtime/execution_plane/coder_proposals"
    receipt_dir.mkdir(parents=True)
    receipt = receipt_dir / "valid-release.json"
    payload = {
        "live_task_id": task.id,
        "live_commit": sha,
        "approval_source": "founder-explicit-test",
        "independent_verdict": "PASS",
        "scoped_live_entrypoint_canary": "PASS",
        "scheduled_service_last_readback": "SUCCESS_AFTER_LIVE_COMMIT",
        "scoped_paths": ["app.py"],
        "hashes_sha256": {
            "app.py": hashlib.sha256((root / "app.py").read_bytes()).hexdigest()
        },
    }
    receipt.write_text(json.dumps(payload))
    return coder, task.id, sha, receipt, payload


def _reconcile(candidate, **changes):
    coder, task_id, sha, receipt, _ = candidate
    kwargs = dict(commit_sha=sha, founder_approved=True,
                  approval_reference="founder-explicit-test",
                  release_receipt=receipt)
    kwargs.update(changes)
    return coder.reconcile_approved_live_commit(task_id, **kwargs)


def test_exact_approved_live_commit_can_complete_task(candidate):
    result = _reconcile(candidate)
    coder, task_id, sha, receipt, _ = candidate
    task = coder.load_task(task_id)
    assert result["commit"] == sha
    assert result["verified_paths"] == ["app.py"]
    assert task.status is TaskStatus.COMPLETED
    assert not task.pending_approval
    assert "founder-explicit-test" in task.decisions[-1]
    assert any(
        event["event"] == "approved_live_commit_reconciled"
        for event in coder.audit.read_task(task_id)
    )


def test_approval_is_never_inferred_from_green_tests(candidate):
    with pytest.raises(EmpireCoderError, match="explicit_founder_approval_required"):
        _reconcile(candidate, founder_approved=False)
    coder, task_id, *_ = candidate
    assert coder.load_task(task_id).status is TaskStatus.AWAITING_APPROVAL


def test_missing_or_altered_approval_reference_fails_closed(candidate):
    with pytest.raises(EmpireCoderError, match="release_receipt_evidence_mismatch"):
        _reconcile(candidate, approval_reference="another-ref")


def test_changed_code_after_commit_does_not_count(candidate):
    coder, task_id, sha, receipt, _ = candidate
    (coder.workspace / "app.py").write_text("VALUE = 77\n")
    with pytest.raises(EmpireCoderError, match="committed_file_hash_mismatch"):
        _reconcile(candidate)


def test_unrelated_commit_paths_are_rejected(candidate):
    coder, task_id, sha, receipt, payload = candidate
    (coder.workspace / "extra.py").write_text("FEATURE = True\n")
    _run(coder.workspace, "git", "add", "extra.py")
    _run(coder.workspace, "git", "-c", "user.name=Test",
         "-c", "user.email=test@example.com", "commit", "-qm", "extra")
    new_sha = _run(coder.workspace, "git", "rev-parse", "HEAD").stdout.strip()
    payload["live_commit"] = new_sha
    receipt.write_text(json.dumps(payload))
    with pytest.raises(EmpireCoderError, match="commit_paths_do_not_match_task_patch_audit"):
        _reconcile(candidate, commit_sha=new_sha)


def test_receipt_has_to_match_scoped_source_files(candidate):
    coder, task_id, sha, receipt, payload = candidate
    payload["scoped_paths"] = ["unrelated.py"]
    receipt.write_text(json.dumps(payload))
    with pytest.raises(EmpireCoderError, match="receipt_paths_do_not_match_commit"):
        _reconcile(candidate)


def test_receipt_must_reside_in_governed_runtime(candidate, tmp_path):
    outside = tmp_path / "fake.json"
    outside.write_text(candidate[-1] and json.dumps(candidate[-1]))
    with pytest.raises(EmpireCoderError, match="release_receipt_not_in_governed_runtime"):
        _reconcile(candidate, release_receipt=outside)


def test_missing_patch_audit_cannot_prove_committed_change(candidate):
    coder, task_id, sha, receipt, payload = candidate
    # Removing patch evidence from a test harness must fail even if a
    # seemingly valid receipt and commit exist.
    real_read_task = coder.audit.read_task
    coder.audit.read_task = lambda tid: [
        event for event in real_read_task(tid)
        if event["event"] not in (
            "patch_applied", "symbol_patch_applied", "structured_patch_applied"
        )
    ]
    with pytest.raises(EmpireCoderError, match="commit_paths_do_not_match_task_patch_audit"):
        _reconcile(candidate)


def test_repeated_approval_never_reopens_completed_task(candidate):
    _reconcile(candidate)
    with pytest.raises(EmpireCoderError, match="task_not_verified_and_awaiting_candidate_commit"):
        _reconcile(candidate)
