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
        "execution_mode": "ISOLATED_CANDIDATE_ONLY",
        "base_branch": "agent/data-cloud-wave4",
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


def test_legacy_implement_contract_without_governed_record_is_held(tmp_path):
    root = workspace(tmp_path)
    contract = _implement_contract()
    queue, _ = _completed_plan(root, promotion_contract=contract)

    result = run_plan_promotion_cycle(root)
    assert result["promoted_count"] == 0
    assert result["held"][0]["status"] == "HELD_NO_GOVERNED_IMPLEMENTATION_INTAKE"
    assert queue.list_pending() == []


def test_implement_contract_still_requires_internal_write_authority(tmp_path):
    root = workspace(tmp_path)
    contract = _implement_contract()
    contract.pop("authority")
    queue, _ = _completed_plan(root, promotion_contract=contract)

    result = run_plan_promotion_cycle(root)

    assert result["promoted_count"] == 0
    assert "internal_write_authority_required" in result["held"][0]["blockers"]
    assert queue.list_pending() == []


def _governed_code_intake(root, *, request_id="owner-bounded-code-task-1", **updates):
    from empire_os.coder.plan_promotion import enqueue_authorized_implementation_plan

    options = dict(
        request_id=request_id,
        objective="Implement only a known safe scoped change",
        source_ref="founder-approved-engineering-owner-20261116",
        allowed_paths=("empire_os/x.py",),
        lease_resources=("path:empire_os/x.py", "domain:coder"),
        required_tests=("tests/test_x.py",),
        base_branch="agent/data-cloud-wave4",
    )
    options.update(updates)
    return enqueue_authorized_implementation_plan(root, **options)


def test_governed_real_plan_promotes_exactly_one_isolated_implement(tmp_path):
    from empire_os.coder.plan_fastpath import drain_fast_plans

    root = workspace(tmp_path)
    intake = _governed_code_intake(root)
    assert intake["status"] == "QUEUED"
    assert intake["authority_inferred"] is False
    queue = LocalJobQueue(root)
    assert queue.list_pending()[0].kind is JobKind.PLAN
    coder = EmpireCoder(root)
    completed = drain_fast_plans(coder, queue, max_jobs=1)
    assert completed["completed_count"] == 1
    assert completed["completed"][0]["family"] == "governed_implementation_intake"

    result = run_plan_promotion_cycle(root)
    assert result["promoted_count"] == 1
    assert run_plan_promotion_cycle(root)["promoted_count"] == 0
    jobs = queue.list_pending()
    assert len(jobs) == 1
    job = jobs[0]
    assert job.kind is JobKind.IMPLEMENT
    assert job.payload["execution_mode"] == "ISOLATED_CANDIDATE_ONLY"
    assert job.payload["allowed_paths"] == ["empire_os/x.py"]
    assert job.payload["lease_resources"] == ["path:empire_os/x.py", "domain:coder"]
    assert job.payload["required_tests"] == ["tests/test_x.py"]
    assert job.payload["execution_plane_request_id"] == intake["request_id"]
    assert job.payload["execution_authority"] == "none"
    assert job.payload["founder_release_required"] is True
    assert queue.claim_next(worker_id="general-coder-worker") is None


def test_governed_code_intake_deduplicates_and_rejects_scope_changes(tmp_path):
    root = workspace(tmp_path)
    first = _governed_code_intake(root)
    again = _governed_code_intake(root)
    assert first["task_id"] == again["task_id"]
    assert first["plan_job_id"] == again["plan_job_id"]
    assert again["status"] == "EXISTS"
    assert len(LocalJobQueue(root).list_pending()) == 1
    with pytest.raises(ValueError, match="existing_execution_request_scope_conflict"):
        _governed_code_intake(root, objective="Change to an unrelated objective")
    with pytest.raises(ValueError, match="existing_execution_request_scope_conflict"):
        _governed_code_intake(
            root, allowed_paths=("empire_os/another.py",),
            lease_resources=("path:empire_os/another.py",),
        )


def test_governed_code_intake_rejects_missing_exact_file_leases(tmp_path):
    root = workspace(tmp_path)
    with pytest.raises(ValueError, match="exact_path_lease_required"):
        _governed_code_intake(root, lease_resources=("domain:coder",))
    assert LocalJobQueue(root).list_pending() == []


@pytest.mark.parametrize("identifier", ["../../other", ".hidden", "request/other", "a" * 81])
def test_governed_code_intake_rejects_unsafe_request_ids(tmp_path, identifier):
    root = workspace(tmp_path)
    with pytest.raises(ValueError, match="request_id_must_be_safe"):
        _governed_code_intake(root, request_id=identifier)
    assert LocalJobQueue(root).list_pending() == []


def test_governed_code_intake_cannot_promote_tampered_plan(tmp_path):
    import json
    from empire_os.coder.plan_fastpath import drain_fast_plans

    root = workspace(tmp_path)
    receipt = _governed_code_intake(root)
    queue = LocalJobQueue(root)
    drain_fast_plans(EmpireCoder(root), queue, max_jobs=1)
    plan_path = queue.completed / (receipt["plan_job_id"] + ".json")
    raw = json.loads(plan_path.read_text())
    raw["payload"]["promotion_contract"]["allowed_paths"] = ["empire_os/elsewhere.py"]
    plan_path.write_text(json.dumps(raw))
    result = run_plan_promotion_cycle(root)
    assert result["promoted_count"] == 0
    assert result["held"][0]["status"] == "HELD_NO_GOVERNED_IMPLEMENTATION_INTAKE"
    assert queue.list_pending() == []


def test_governed_code_intake_requires_exact_record_after_plan(tmp_path):
    from empire_os.coder.plan_fastpath import drain_fast_plans
    from empire_os.coder.plan_promotion import INTAKE_DIRECTORY

    root = workspace(tmp_path)
    receipt = _governed_code_intake(root)
    queue = LocalJobQueue(root)
    drain_fast_plans(EmpireCoder(root), queue, max_jobs=1)
    (root / INTAKE_DIRECTORY / (receipt["request_id"] + ".json")).unlink()
    result = run_plan_promotion_cycle(root)
    assert result["promoted_count"] == 0
    assert result["held"][0]["status"] == "HELD_NO_GOVERNED_IMPLEMENTATION_INTAKE"
    assert queue.list_pending() == []


def test_existing_owner_prioritizes_authorized_plan_over_newer_advisory_noise(tmp_path):
    from empire_os.coder.plan_fastpath import drain_fast_plans

    root = workspace(tmp_path)
    _governed_code_intake(root)
    queue = LocalJobQueue(root)
    assert drain_fast_plans(EmpireCoder(root), queue, max_jobs=1)["completed_count"] == 1
    for _ in range(7):
        _completed_plan(root)
    # The old newest-first scan repeatedly held recent advisory-only plans,
    # even when an older genuinely bound implementation existed.
    result = run_plan_promotion_cycle(root, max_jobs=2)
    assert result["promoted_count"] == 1
    assert result["scanned_count"] == 2
    pending = queue.list_pending()
    assert len(pending) == 1
    assert pending[0].kind is JobKind.IMPLEMENT
    assert pending[0].payload["execution_mode"] == "ISOLATED_CANDIDATE_ONLY"


def test_already_promoted_plans_do_not_consume_bounded_scan_slots(tmp_path):
    root = workspace(tmp_path)
    verify = {"kind": "VERIFY", "changed_files": ["empire_os/x.py"],
              "tests": ["tests/test_x.py"]}
    queue, older = _completed_plan(root, promotion_contract=verify)
    _, newer = _completed_plan(root, promotion_contract=verify)

    first = run_plan_promotion_cycle(root, max_jobs=1)
    assert first["promoted_count"] == 1
    assert first["promoted"][0]["source_plan_job_id"] == newer.id
    second = run_plan_promotion_cycle(root, max_jobs=1)
    assert second["promoted_count"] == 1
    assert second["promoted"][0]["source_plan_job_id"] == older.id
    third = run_plan_promotion_cycle(root, max_jobs=1)
    assert third["promoted_count"] == 0
    assert third["scanned_count"] == 0
    assert len(queue.list_pending()) == 2


def test_promotion_key_index_built_only_once_per_cycle(tmp_path, monkeypatch):
    import empire_os.coder.plan_promotion as module

    root = workspace(tmp_path)
    for _ in range(4):
        _completed_plan(root, promotion_contract={
            "kind": "VERIFY", "changed_files": ["empire_os/x.py"],
            "tests": ["tests/test_x.py"],
        })
    observed = []
    original = module._existing_promotion_keys

    def indexed(queue):
        observed.append(True)
        return original(queue)

    monkeypatch.setattr(module, "_existing_promotion_keys", indexed)
    result = run_plan_promotion_cycle(root, max_jobs=4)
    assert result["promoted_count"] == 4
    assert len(observed) == 1
