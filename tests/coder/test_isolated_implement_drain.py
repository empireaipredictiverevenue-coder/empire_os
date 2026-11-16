"""Real execution-plane PLAN -> isolated IMPLEMENT -> founder review contract."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

import pytest

from empire_os.coder import EmpireCoder
from empire_os.coder.jobs import JobKind, JobStatus, LocalJobQueue
from empire_os.coder.plan_fastpath import drain_fast_plans
from empire_os.coder.plan_promotion import (
    enqueue_authorized_implementation_plan, run_plan_promotion_cycle,
)
from empire_os.coder.isolated_implement_drain import drain_isolated_implement_jobs


def _root(tmp_path):
    root = tmp_path / "original"
    root.mkdir()
    subprocess.run(("git", "init", "-q", str(root)), check=True)
    (root / "empire_os").mkdir()
    (root / "empire_os/test_owner.py").write_text("VALUE = 1\n")
    (root / "tests").mkdir()
    (root / "tests/test_owner.py").write_text("def test_owner():\n    assert True\n")
    subprocess.run(
        ("git", "add", "empire_os/test_owner.py", "tests/test_owner.py"),
        cwd=root, check=True,
    )
    subprocess.run(
        ("git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
         "commit", "-qm", "original-baseline"), cwd=root, check=True,
    )
    return root


def _enqueue(root):
    receipt = enqueue_authorized_implementation_plan(
        root, request_id="founder-scope-queue-20261116",
        objective="Update existing owner safely, then keep proposal for approval.",
        source_ref="founder-approved-implementation-scope-20261116",
        allowed_paths=("empire_os/test_owner.py",),
        lease_resources=("path:empire_os/test_owner.py",),
        required_tests=("tests/test_owner.py",),
        base_branch="agent/data-cloud-wave4",
    )
    q = LocalJobQueue(root)
    assert drain_fast_plans(EmpireCoder(root), q, max_jobs=1)["completed_count"] == 1
    assert run_plan_promotion_cycle(root, max_jobs=1)["promoted_count"] == 1
    jobs = q.list_pending(kind=JobKind.IMPLEMENT)
    assert len(jobs) == 1
    return q, jobs[0], receipt


def _verified_stub(root, candidate):
    path = (
        root / "runtime/execution_plane/coder_proposals"
        / f"{candidate.job_id}.patch"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (
        b"diff --git a/empire_os/test_owner.py b/empire_os/test_owner.py\n"
        b"--- a/empire_os/test_owner.py\n"
        b"+++ b/empire_os/test_owner.py\n"
        b"@@ -1 +1 @@\n"
        b"-VALUE = 1\n"
        b"+VALUE = 2\n"
    )
    path.write_bytes(content)
    return {
        "status": "LOCAL_PROPOSAL_READY",
        "verification_passed": True,
        "founder_gate_required": True,
        "production_mutation": False,
        "production_deploy": False,
        "changed_paths": ["empire_os/test_owner.py"],
        "proposal_patch": str(path),
        "proposal_sha256": sha256(content).hexdigest(),
        "source_commit": subprocess.check_output(
            ("git", "rev-parse", "HEAD"), cwd=root, text=True,
        ).strip(),
        "test_isolation": "BWRAP_NO_NETWORK_READ_ONLY_SOURCE",
        "model_filesystem_isolation": "BWRAP_CLONE_AND_READONLY_AUTH",
    }


def test_authorized_real_promotion_becomes_approval_held_candidate(tmp_path):
    root = _root(tmp_path)
    queue, job, receipt = _enqueue(root)
    source_before = (root / "empire_os/test_owner.py").read_bytes()
    assert queue.claim_next(worker_id="general-worker") is None
    result = drain_isolated_implement_jobs(root, candidate_runner=_verified_stub)
    assert result["processed_count"] == 1
    assert result["awaiting_approval_count"] == 1
    assert result["failed_count"] == 0
    current = queue.get(job.id)
    assert current.status is JobStatus.AWAITING_APPROVAL
    assert current.result["candidate_status"] == "LOCAL_PROPOSAL_READY"
    assert current.result["implementation_verified"] is False
    assert current.result["task_completed"] is False
    assert current.result["founder_release_required"] is True
    assert current.result["test_isolation"] == "BWRAP_NO_NETWORK_READ_ONLY_SOURCE"
    assert current.result["model_filesystem_isolation"] == "BWRAP_CLONE_AND_READONLY_AUTH"
    assert (root / "empire_os/test_owner.py").read_bytes() == source_before
    assert list(queue.awaiting_approval.glob("*.json"))
    assert not list(queue.completed.glob(f"{job.id}.json"))
    assert queue.claim_next() is None
    assert run_plan_promotion_cycle(root, max_jobs=2)["promoted_count"] == 0
    again = drain_isolated_implement_jobs(root, candidate_runner=_verified_stub)
    assert again["processed_count"] == 0
    assert enqueue_authorized_implementation_plan(
        root, request_id="founder-scope-queue-20261116",
        objective="Update existing owner safely, then keep proposal for approval.",
        source_ref="founder-approved-implementation-scope-20261116",
        allowed_paths=("empire_os/test_owner.py",),
        lease_resources=("path:empire_os/test_owner.py",),
        required_tests=("tests/test_owner.py",),
        base_branch="agent/data-cloud-wave4",
    )["status"] == "EXISTS"


@pytest.mark.parametrize("tamper", (
    {"allowed_paths": ["empire_os/other.py"]},
    {"required_tests": ["tests/test_other.py"]},
    {"execution_plane_request_id": "different-request"},
    {"plan_promotion_key": "forged"},
    {"source_ref": "attacker"},
    {"founder_release_required": False},
))
def test_changed_authorization_cannot_invoke_codex(tmp_path, tamper):
    root = _root(tmp_path)
    queue, job, _ = _enqueue(root)
    packet = json.loads((queue.pending / f"{job.id}.json").read_text())
    packet["payload"].update(tamper)
    (queue.pending / f"{job.id}.json").write_text(json.dumps(packet))
    def never(*_args, **_kwargs):
        raise AssertionError("model must never execute unauthorized scope")
    result = drain_isolated_implement_jobs(root, candidate_runner=never)
    assert result["processed_count"] == 1
    assert result["awaiting_approval_count"] == 0
    assert queue.get(job.id).status is JobStatus.FAILED
    assert "codex" not in queue.get(job.id).error.lower()


def test_forged_implementation_without_completed_plan_fails_closed(tmp_path):
    root = _root(tmp_path)
    queue = LocalJobQueue(root)
    job = queue.enqueue(task_id="forged-task", kind=JobKind.IMPLEMENT,
        payload={"execution_mode": "ISOLATED_CANDIDATE_ONLY",
                 "execution_authority": "none", "founder_release_required": True})
    def never(*_args, **_kwargs):
        raise AssertionError("untrusted job must never invoke model")
    result = drain_isolated_implement_jobs(root, candidate_runner=never)
    assert result["failed_count"] == 1
    assert queue.get(job.id).status is JobStatus.FAILED


@pytest.mark.parametrize("alter", ("unverified", "wrong_digest", "wrong_path", "scope_escape", "no_model_isolation"))
def test_model_claims_alone_do_not_create_approval_ready_record(tmp_path, alter):
    root = _root(tmp_path)
    queue, job, _ = _enqueue(root)
    def bad(root, sandbox):
        data = _verified_stub(root, sandbox)
        if alter == "unverified":
            data["verification_passed"] = False
        elif alter == "wrong_digest":
            data["proposal_sha256"] = "0" * 64
        elif alter == "wrong_path":
            data["proposal_patch"] = "/tmp/forged.patch"
        elif alter == "no_model_isolation":
            data["model_filesystem_isolation"] = None
        else:
            data["changed_paths"] = ["empire_os/other.py"]
        return data
    result = drain_isolated_implement_jobs(root, candidate_runner=bad)
    assert result["awaiting_approval_count"] == 0
    assert result["failed_count"] == 1
    assert queue.get(job.id).status is JobStatus.FAILED
    assert not list(queue.awaiting_approval.glob("*.json"))


def test_runner_exception_is_terminal_not_false_completion(tmp_path):
    root = _root(tmp_path)
    queue, job, _ = _enqueue(root)
    def broken(*_args):
        raise RuntimeError("model endpoint unavailable")
    result = drain_isolated_implement_jobs(root, candidate_runner=broken)
    assert result["failed_count"] == 1
    assert queue.get(job.id).status is JobStatus.FAILED
    assert queue.get(job.id).result["task_completed"] is False


def test_script_entrypoint_is_idle_on_empty_production_like_queue(tmp_path):
    root = _root(tmp_path)
    script = Path(__file__).resolve().parents[2] / "scripts/run_coder_isolated_implement_drain.py"
    ran = subprocess.run(
        (sys.executable, str(script), "--repo-root", str(root), "--max-jobs", "1"),
        cwd=root, check=True, text=True, capture_output=True,
    )
    assert json.loads(ran.stdout)["processed_count"] == 0


def test_existing_hermes_timer_is_integrated_without_another_schedule():
    source = Path(__file__).resolve().parents[2]
    sh = (source / "scripts/run_hermes_resident_latest.sh").read_text()
    assert "run_coder_isolated_implement_drain.py" in sh
    assert sh.index("run_coder_isolated_implement_drain.py") < sh.index(
        "=== HERMES RESIDENT CODE SYNC ==="
    )
    runner = (source / "empire_os/empire_coder_sandbox_runner.py").read_text()
    assert '"exec", "--ephemeral"' in runner


def test_full_existing_isolated_codex_runner_is_consumed_by_original_queue(
    tmp_path, monkeypatch,
):
    """Real sandbox subprocess + Git patch; fake model avoids external API cost."""
    import empire_os.empire_coder_sandbox_runner as builder

    root = _root(tmp_path)
    (root / "tests/test_owner.py").write_text(
        "from empire_os.test_owner import VALUE\n"
        "def test_owner():\n    assert VALUE == 2\n"
    )
    subprocess.run(("git", "branch", "-M", "agent/data-cloud-wave4"), cwd=root, check=True)
    subprocess.run(
        ("git", "add", "empire_os/test_owner.py", "tests/test_owner.py"),
        cwd=root, check=True,
    )
    subprocess.run(
        ("git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
         "commit", "-qm", "model-scoped-baseline"), cwd=root, check=True,
    )
    queue, job, _ = _enqueue(root)
    fake = tmp_path / "fake-codex"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "from pathlib import Path\n"
        "import sys\n"
        "if sys.argv[1:3] == ['login', 'status']:\n"
        "    print('Logged in using ChatGPT', file=sys.stderr)\n"
        "    sys.exit(0)\n"
        "root = Path(sys.argv[sys.argv.index('-C') + 1])\n"
        "(root / 'empire_os/test_owner.py').write_text('VALUE = 2\\n')\n"
        "print('model generated requested scoped patch')\n"
    )
    fake.chmod(0o700)
    monkeypatch.setattr(builder, "_local_codex_binary", lambda: str(fake))
    def actual_sandbox(repo, sandbox):
        return builder.run_empire_coder_codex_local_candidate(
            repo, sandbox, work_root=tmp_path / "isolated-work",
        )
    result = drain_isolated_implement_jobs(root, candidate_runner=actual_sandbox)
    assert result["awaiting_approval_count"] == 1, result
    assert result["failed_count"] == 0
    done = queue.get(job.id)
    assert done.status is JobStatus.AWAITING_APPROVAL
    assert done.result["candidate_verification_passed"] is True
    patch = Path(done.result["proposal_patch"])
    assert patch.exists()
    assert sha256(patch.read_bytes()).hexdigest() == done.result["proposal_sha256"]
    assert (root / "empire_os/test_owner.py").read_text() == "VALUE = 1\n"
    assert not list((tmp_path / "isolated-work").glob("codex-*"))


def test_legacy_complete_api_cannot_mislabel_isolated_candidate_as_implementation(tmp_path):
    root = _root(tmp_path)
    queue, job, _ = _enqueue(root)
    claimed = queue.claim_specific(job.id)
    assert claimed is not None
    completed = queue.complete(
        claimed, {"applied": True, "verification": {"verdict": "PASS"}}
    )
    assert completed.status is JobStatus.FAILED
    assert completed.result["implementation_verified"] is False
    assert completed.result["task_completed"] is False
    assert completed.error == "isolated_implementation_requires_founder_review"
    assert not list(queue.completed.glob(f"{job.id}.json"))



def test_original_candidate_tests_cannot_read_production_or_use_network(tmp_path):
    """Run a real pytest subprocess in the OS sandbox, not a mocked policy."""
    import os
    import socket
    import empire_os.empire_coder_sandbox_runner as runner

    clone = tmp_path / "isolated_repo"
    (clone / "tests").mkdir(parents=True)
    (clone / "tests/test_sandbox.py").write_text(
        "import pytest, socket\n"
        "from pathlib import Path\n"
        "def test_production_secrets_absent_and_network_denied():\n"
        "    assert not Path('/srv/empire_os/runtime/execution_plane/leases.json').exists()\n"
        "    assert not Path('/etc/passwd').exists()\n"
        "    with pytest.raises(OSError):\n"
        "        Path(__file__).with_name('unauthorised.py').write_text('x')\n"
        "    with pytest.raises(OSError):\n"
        "        socket.create_connection(('127.0.0.1', 9), timeout=0.2)\n"
    )
    argv = runner._isolated_pytest_argv(
        clone=clone, python=Path(sys.executable),
        tests=("tests/test_sandbox.py",),
    )
    assert argv is not None, "bubblewrap must be present on production host"
    assert "--unshare-all" in argv
    assert "--ro-bind" in argv
    tested = subprocess.run(
        argv, cwd=clone, capture_output=True, text=True, timeout=30,
        env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert tested.returncode == 0, tested.stdout + tested.stderr
    assert not (clone / "tests/unauthorised.py").exists()


def test_missing_os_sandbox_cannot_be_substituted_with_host_pytest(
    tmp_path, monkeypatch,
):
    import empire_os.empire_coder_sandbox_runner as builder

    original = builder.shutil.which
    monkeypatch.setattr(
        builder.shutil, "which",
        lambda x: None if x == "bwrap" else original(x),
    )
    result = builder._isolated_pytest_argv(
        clone=tmp_path, python=Path(sys.executable),
        tests=("tests/test_owner.py",),
    )
    assert result is None


def test_dirty_local_source_blocks_candidate_model_before_inference(tmp_path, monkeypatch):
    import empire_os.empire_coder_sandbox_runner as builder

    root = _root(tmp_path)
    subprocess.run(("git", "branch", "-M", "agent/data-cloud-wave4"), cwd=root, check=True)
    (root / "empire_os/test_owner.py").write_text("VALUE = 999\n")
    fake = tmp_path / "fake-codex"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "if sys.argv[1:3] == ['login', 'status']:\n"
        " print('Logged in using ChatGPT', file=sys.stderr)\n"
        " sys.exit(0)\n"
        "raise RuntimeError('model must never run for dirty source')\n"
    )
    fake.chmod(0o700)
    monkeypatch.setattr(builder, "_local_codex_binary", lambda: str(fake))
    sandbox = builder.EmpireCoderSandboxJob(
        job_id="dirty-source-blocked",
        objective="Do not override existing work.",
        department="engineering", capability="backend_code",
        allowed_paths=("empire_os/test_owner.py",),
        lease_resources=("path:empire_os/test_owner.py",),
        pytest_targets=("tests/test_owner.py",),
    )
    result = builder.run_empire_coder_codex_local_candidate(
        root, sandbox, work_root=tmp_path / "isolated",
    )
    assert result["status"] == "HELD"
    assert result["reason"] == "source_paths_dirty_or_unavailable"
    assert result["proposal_patch"] is None


@pytest.mark.parametrize("modification", ("wrong_source_sha", "wrong_patch_paths", "unapplicable_patch"))
def test_untrusted_patch_cannot_be_presented_for_founder_review(tmp_path, modification):
    root = _root(tmp_path)
    queue, job, _ = _enqueue(root)

    def attacker(repo, scoped):
        data = _verified_stub(repo, scoped)
        patch = Path(data["proposal_patch"])
        if modification == "wrong_source_sha":
            data["source_commit"] = "a" * 40
        elif modification == "wrong_patch_paths":
            patch.write_bytes(patch.read_bytes().replace(
                b"empire_os/test_owner.py", b"tests/test_owner.py"
            ))
            data["proposal_sha256"] = sha256(patch.read_bytes()).hexdigest()
        else:
            patch.write_bytes(patch.read_bytes().replace(
                b"-VALUE = 1", b"-VALUE = 404"
            ))
            data["proposal_sha256"] = sha256(patch.read_bytes()).hexdigest()
        return data

    summary = drain_isolated_implement_jobs(root, candidate_runner=attacker)
    assert summary["awaiting_approval_count"] == 0
    assert summary["failed_count"] == 1
    assert queue.get(job.id).status is JobStatus.FAILED


def _remove_retry_delay(queue: LocalJobQueue, job_id: str) -> None:
    path = queue.pending / (job_id + ".json")
    record = json.loads(path.read_text())
    record["retry_after"] = None
    path.write_text(json.dumps(record))


def test_bounded_model_timeout_retries_then_produces_founder_candidate(tmp_path):
    root = _root(tmp_path)
    queue, job, _ = _enqueue(root)
    times = []

    def sometimes_timeout(repo, scope):
        times.append(True)
        if len(times) == 1:
            return {"status": "HELD", "reason": "codex_model_timeout"}
        return _verified_stub(repo, scope)

    first = drain_isolated_implement_jobs(root, candidate_runner=sometimes_timeout)
    assert first["retried_count"] == 1
    assert first["failed_count"] == 0
    assert queue.get(job.id).status is JobStatus.PENDING
    assert queue.get(job.id).retry_after is not None
    health = root / "runtime/execution_plane/coder_implement_consumer_latest.json"
    receipt = json.loads(health.read_text())
    assert receipt["health_status"] == "RETRY_PENDING"
    assert receipt["pending_isolated_implement_count"] == 1
    assert health.stat().st_mode & 0o777 == 0o600
    assert "Update existing owner safely" not in health.read_text()
    _remove_retry_delay(queue, job.id)
    second = drain_isolated_implement_jobs(root, candidate_runner=sometimes_timeout)
    assert second["awaiting_approval_count"] == 1
    assert queue.get(job.id).status is JobStatus.AWAITING_APPROVAL
    assert queue.get(job.id).attempts == 2
    receipt = json.loads(health.read_text())
    assert receipt["health_status"] == "FOUNDER_REVIEW_PENDING"
    assert receipt["total_awaiting_approval_count"] == 1


def test_permanent_model_failure_cannot_retry_indefinitely(tmp_path):
    root = _root(tmp_path)
    queue, job, _ = _enqueue(root)
    for index in range(3):
        if index:
            _remove_retry_delay(queue, job.id)
        result = drain_isolated_implement_jobs(
            root,
            candidate_runner=lambda *_: {
                "status": "HELD",
                "reason": "execution_lease_conflict",
            },
        )
        if index < 2:
            assert result["retried_count"] == 1
            assert result["failed_count"] == 0
            assert queue.get(job.id).status is JobStatus.PENDING
        else:
            assert result["retried_count"] == 0
            assert result["failed_count"] == 1
            assert queue.get(job.id).status is JobStatus.FAILED
    assert queue.get(job.id).attempts == 3
    assert not queue.list_pending(kind=JobKind.IMPLEMENT)


def test_nontransient_failure_is_dead_lettered_immediately(tmp_path):
    root = _root(tmp_path)
    queue, job, _ = _enqueue(root)
    result = drain_isolated_implement_jobs(
        root, candidate_runner=lambda *_: {
            "status": "HELD", "reason": "isolated_test_runtime_unavailable",
        },
    )
    assert result["failed_count"] == 1
    assert result["retried_count"] == 0
    assert queue.get(job.id).status is JobStatus.FAILED
