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
    content = b"non-production validated patch fixture\n"
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


@pytest.mark.parametrize("alter", ("unverified", "wrong_digest", "wrong_path", "scope_escape"))
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
