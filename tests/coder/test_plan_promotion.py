import subprocess

import pytest

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


def _implement_contract():
    return {
        "kind": "IMPLEMENT",
        "authority": "internal_write",
        "allowed_paths": ["empire_os/x.py"],
        "required_tests": ["tests/test_x.py"],
        "lease_resources": ["path:empire_os/x.py", "domain:coder"],
        "execution_plane_request_id": "request-test",
    }


@pytest.mark.parametrize("kind,field", [
    ("VERIFY", "changed_files"),
    ("VERIFY", "tests"),
    ("IMPLEMENT", "allowed_paths"),
    ("IMPLEMENT", "required_tests"),
    ("IMPLEMENT", "lease_resources"),
])
@pytest.mark.parametrize("unsafe_path", [
    "/tests/test_x.py",
    "../tests/test_x.py",
    "tests/../test_x.py",
    "tests/../../test_x.py",
    "tests//test_x.py",
    ".",
    "tests/./test_x.py",
    "tests/abc:bad.py",
    "tests/bad\x00name.py",
    "tests/bad\nname.py",
    "tests/test_x.py/",
    "tests/..",
    "",
    "   ",
    "tests\\test_x.py",
    "C:/tests/test_x.py",
    "C:\\tests\\test_x.py",
])
def test_unsafe_contract_paths_hold_without_enqueueing(tmp_path, kind, field, unsafe_path):
    root = workspace(tmp_path)
    contract = (
        {"kind": "VERIFY", "changed_files": ["empire_os/x.py"], "tests": ["tests/test_x.py"]}
        if kind == "VERIFY" else _implement_contract()
    )
    value = "path:" + unsafe_path if field == "lease_resources" else unsafe_path
    contract[field].append(value)
    queue, _ = _completed_plan(root, promotion_contract=contract)

    result = run_plan_promotion_cycle(root)

    assert result["promoted_count"] == 0
    assert result["held"][0]["status"] == "HELD_INVALID_CONTRACT"
    assert f"{field}_must_be_safe_repository_paths" in result["held"][0]["blockers"]
    assert queue.list_pending() == []


def test_explicit_implement_contract_preserves_path_and_domain_leases(tmp_path):
    root = workspace(tmp_path)
    contract = _implement_contract()
    queue, _ = _completed_plan(root, promotion_contract=contract)

    assert run_plan_promotion_cycle(root)["promoted_count"] == 1
    assert run_plan_promotion_cycle(root)["promoted_count"] == 0
    pending = queue.list_pending()
    assert len(pending) == 1
    assert pending[0].kind is JobKind.IMPLEMENT
    assert pending[0].payload["lease_resources"] == contract["lease_resources"]
    assert pending[0].payload["execution_authority"] == "none"


def test_implement_contract_still_requires_internal_write_authority(tmp_path):
    root = workspace(tmp_path)
    contract = _implement_contract()
    contract.pop("authority")
    queue, _ = _completed_plan(root, promotion_contract=contract)

    result = run_plan_promotion_cycle(root)

    assert result["promoted_count"] == 0
    assert "internal_write_authority_required" in result["held"][0]["blockers"]
    assert queue.list_pending() == []
