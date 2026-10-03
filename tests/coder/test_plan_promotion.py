import subprocess

from empire_os.coder import EmpireCoder
from empire_os.coder.jobs import JobKind, JobStatus, LocalJobQueue
from empire_os.coder.plan_promotion import run_plan_promotion_cycle


def workspace(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


def _completed_plan(root, *, promotion_contract=None):
    coder = EmpireCoder(root)
    queue = LocalJobQueue(root)
    task = coder.create_task("Advisory plan task.")
    job = queue.enqueue(
        task_id=task.id,
        kind=JobKind.PLAN,
        payload=(
            {"promotion_contract": promotion_contract}
            if promotion_contract is not None else {}
        ),
    )
    claimed = queue.claim_specific(job.id)
    queue.complete(claimed, {
        "proposal_persisted": True,
        "deterministic_fastpath": True,
        "fastpath_family": "completion_review",
    })
    return queue, job


def test_missing_contract_holds_instead_of_guessing(tmp_path):
    root = workspace(tmp_path)
    queue, job = _completed_plan(root)

    result = run_plan_promotion_cycle(root)

    assert result["promoted_count"] == 0
    assert result["held_count"] == 1
    assert result["held"][0]["status"] == "AWAITING_EXACT_CONTRACT"
    assert queue.list_pending() == []


def test_explicit_verify_contract_promotes_once(tmp_path):
    root = workspace(tmp_path)
    queue, job = _completed_plan(
        root,
        promotion_contract={
            "kind": "VERIFY",
            "changed_files": ["empire_os/x.py"],
            "tests": ["tests/test_x.py"],
        },
    )

    first = run_plan_promotion_cycle(root)
    second = run_plan_promotion_cycle(root)

    assert first["promoted_count"] == 1
    assert second["promoted_count"] == 0
    pending = queue.list_pending()
    assert len(pending) == 1
    assert pending[0].kind is JobKind.VERIFY
    assert pending[0].payload["source_plan_job_id"] == job.id


def test_implement_contract_requires_exact_scope_and_lease(tmp_path):
    root = workspace(tmp_path)
    queue, _ = _completed_plan(
        root,
        promotion_contract={
            "kind": "IMPLEMENT",
            "authority": "internal_write",
            "required_tests": ["tests/test_x.py"],
        },
    )

    result = run_plan_promotion_cycle(root)

    assert result["promoted_count"] == 0
    assert "allowed_paths_required" in result["held"][0]["blockers"]
    assert "lease_resources_required" in result["held"][0]["blockers"]
    assert "execution_plane_request_id_required" in result["held"][0][
        "blockers"
    ]
