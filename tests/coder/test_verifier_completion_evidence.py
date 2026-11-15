"""Independent completion-evidence regressions for governed Empire Coder."""
from __future__ import annotations

import subprocess
import sys

import pytest

from empire_os.coder.models import VerificationVerdict
from empire_os.coder.verifier import Verifier


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(("git", "init", "-q"), cwd=root, check=True)
    (root / "docs").mkdir()
    (root / "docs/BLUEPRINT_V6.md").write_text("# Tested Blueprint\n", encoding="utf-8")
    (root / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests/test_smoke.py").write_text(
        "def test_truth():\n    assert True\n", encoding="utf-8",
    )
    subprocess.run(
        ("git", "add", "--", "app.py", "tests/test_smoke.py"), cwd=root, check=True,
    )
    subprocess.run(
        ("git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
         "commit", "-qm", "fixture"), cwd=root, check=True,
    )
    return root


def verify(root, files=("app.py",), *, run_tests=True):
    commands = ((sys.executable, "-m", "pytest", "-q", "tests/test_smoke.py"),) if run_tests else ()
    return Verifier(root).verify(task_id="completion-proof", changed_files=files, commands=commands)


def test_claimed_but_unchanged_file_fails_despite_passing_tests(repo):
    report = verify(repo)
    assert report.verdict is VerificationVerdict.FAIL
    assert any(check.name == "changed_file:app.py" and not check.passed for check in report.checks)
    assert any(check.name.startswith("command:") and check.passed for check in report.checks)


def test_actual_change_plus_executed_tests_passes_candidate_review(repo):
    (repo / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    report = verify(repo)
    assert report.verdict is VerificationVerdict.PASS
    proof = next(check for check in report.checks if check.name == "changed_file:app.py")
    assert proof.passed is True
    assert "sha256=" in proof.output
    assert "git_status=" in proof.output


def test_changed_file_without_verification_commands_fails(repo):
    (repo / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    report = verify(repo, run_tests=False)
    assert report.verdict is VerificationVerdict.FAIL
    assert any(
        check.name == "verification_commands_present" and not check.passed
        for check in report.checks
    )


def test_green_tests_without_any_claimed_changes_cannot_prove_implementation(repo):
    report = verify(repo, files=())
    assert report.verdict is VerificationVerdict.FAIL
    assert any(check.name == "claimed_changes_present" and not check.passed for check in report.checks)


def test_unrelated_dirty_file_does_not_prove_claimed_file_changed(repo):
    (repo / "tests/test_smoke.py").write_text(
        "def test_truth():\n    assert 2 + 2 == 4\n", encoding="utf-8",
    )
    report = verify(repo)
    assert report.verdict is VerificationVerdict.FAIL
    assert any(check.name == "changed_file:app.py" and not check.passed for check in report.checks)


def test_untracked_candidate_file_is_detected(repo):
    (repo / "new_module.py").write_text("VALUE = 2\n", encoding="utf-8")
    report = verify(repo, files=("new_module.py",))
    assert report.verdict is VerificationVerdict.PASS


def test_every_claimed_file_must_have_change_evidence(repo):
    (repo / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    report = verify(repo, files=("app.py", "tests/test_smoke.py"))
    assert report.verdict is VerificationVerdict.FAIL
    assert any(
        check.name == "changed_file:tests/test_smoke.py" and not check.passed
        for check in report.checks
    )


def test_outside_path_cannot_count_as_work(repo, tmp_path):
    outside = tmp_path / "fake.py"
    outside.write_text("TOKEN = 'not-a-secret'\n", encoding="utf-8")
    report = verify(repo, files=("../fake.py",))
    assert report.verdict is VerificationVerdict.FAIL
    assert any(check.name == "changed_file:../fake.py" and not check.passed for check in report.checks)


def test_failed_test_overrides_real_candidate_diff(repo):
    (repo / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    (repo / "tests/test_smoke.py").write_text(
        "def test_truth():\n    assert False\n", encoding="utf-8",
    )
    report = verify(repo)
    assert report.verdict is VerificationVerdict.FAIL
    assert any(check.name.startswith("command:") and not check.passed for check in report.checks)


def test_staged_whitespace_failure_is_detected(repo):
    (repo / "app.py").write_text("VALUE = 2  \n", encoding="utf-8")
    subprocess.run(("git", "add", "--", "app.py"), cwd=repo, check=True)
    report = verify(repo)
    assert report.verdict is VerificationVerdict.FAIL
    assert any(
        check.name == "git_staged_diff_check" and not check.passed
        for check in report.checks
    )


def test_coder_orchestrator_stops_false_completion_at_approval_gate(repo):
    from empire_os.coder.models import TaskPhase, TaskStatus
    from empire_os.coder.orchestrator import EmpireCoder

    coder = EmpireCoder(repo)
    task = coder.create_task("Make a verified implementation change")
    commands = ((sys.executable, "-m", "pytest", "-q", "tests/test_smoke.py"),)

    false_claim = coder.verify(task.id, changed_files=("app.py",), commands=commands)
    assert false_claim.verdict is VerificationVerdict.FAIL
    blocked = coder.store.load(task.id)
    assert blocked.status is TaskStatus.BLOCKED
    assert blocked.phase is TaskPhase.REPAIR

    (repo / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    genuine_candidate = coder.verify(
        task.id, changed_files=("app.py",), commands=commands,
    )
    assert genuine_candidate.verdict is VerificationVerdict.PASS
    pending = coder.store.load(task.id)
    assert pending.status is TaskStatus.AWAITING_APPROVAL
    assert pending.phase is TaskPhase.APPROVAL
    assert "candidate_commit" in pending.pending_approval
    assert pending.status is not TaskStatus.COMPLETED


def test_git_status_only_is_not_a_substantive_verification(repo):
    (repo / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    report = Verifier(repo).verify(
        task_id="git-is-not-a-test",
        changed_files=("app.py",),
        commands=(("git", "status", "--short"),),
    )
    assert report.verdict is VerificationVerdict.FAIL
    assert any(
        check.name == "substantive_validation_present" and not check.passed
        for check in report.checks
    )
