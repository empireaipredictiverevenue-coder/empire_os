import subprocess
from empire_os.coder.jobs import JobKind, JobStatus, LocalJobQueue
from empire_os.coder.verify_fastpath import drain_verify_jobs

def workspace(tmp_path):
    root=tmp_path/"repo"; root.mkdir()
    subprocess.run(["git","init","-q",str(root)],check=True)
    (root/"tests").mkdir()
    (root/"tests/test_ok.py").write_text("def test_ok():\n    assert 1 + 1 == 2\n")
    return root

def test_verify_fastpath_runs_explicit_tests_without_changed_files(tmp_path):
    root=workspace(tmp_path)
    q=LocalJobQueue(root)
    job=q.enqueue(task_id="task-verify",kind=JobKind.VERIFY,payload={"tests":["tests/test_ok.py"]},priority=90)
    result=drain_verify_jobs(q,max_jobs=1,timeout_seconds=60)
    assert result["completed_count"]==1
    terminal=q.get(job.id)
    assert terminal.status is JobStatus.COMPLETED
    assert terminal.result["verification"]["verdict"]=="TESTS_ONLY"
    assert terminal.result["verification"]["scope"]=="TEST_EXECUTION_ONLY"
    assert terminal.result["implementation_verified"] is False
    assert terminal.result["task_completed"] is False
    assert terminal.result["changed_files_inferred"] is False
    assert terminal.result["model_inference"] is False

def test_verify_fastpath_skips_claimed_changes_without_starving_test_only(tmp_path):
    root = workspace(tmp_path)
    q = LocalJobQueue(root)
    claimed = q.enqueue(
        task_id="task-implementation", kind=JobKind.VERIFY,
        payload={"changed_files": ["module.py"], "tests": ["tests/test_ok.py"]},
        priority=100,
    )
    tests_only = q.enqueue(
        task_id="task-tests-only", kind=JobKind.VERIFY,
        payload={"verification_scope": "TEST_EXECUTION_ONLY",
                 "tests": ["tests/test_ok.py"]},
        priority=20,
    )
    result = drain_verify_jobs(q, max_jobs=1, timeout_seconds=60)
    assert result["completed_count"] == 1
    assert result["skipped_count"] == 1
    assert q.get(claimed.id).status is JobStatus.PENDING
    completed = q.get(tests_only.id)
    assert completed.status is JobStatus.COMPLETED
    assert completed.result["verification"]["verdict"] == "TESTS_ONLY"


def test_verify_fastpath_skips_invalid_test_contract(tmp_path):
    root=workspace(tmp_path)
    q=LocalJobQueue(root)
    job=q.enqueue(task_id="task-invalid",kind=JobKind.VERIFY,payload={"tests":["scripts/deploy.py"]})
    result=drain_verify_jobs(q,max_jobs=1)
    assert result["skipped_count"]==1
    assert q.get(job.id).status is JobStatus.PENDING

def test_verify_fastpath_defers_code_change_to_task_provenance_verifier(tmp_path):
    root=workspace(tmp_path)
    (root/"module.py").write_text("VALUE = 2\n")
    q=LocalJobQueue(root)
    job=q.enqueue(task_id="task-claimed",kind=JobKind.VERIFY,payload={
        "tests":["tests/test_ok.py"],"changed_files":["module.py"],
    })
    result=drain_verify_jobs(q,max_jobs=1,timeout_seconds=60)
    assert result["completed_count"]==0
    assert result["skipped_count"]==1
    assert result["skipped"][0]["reason"]=="task_provenance_verifier_required"
    assert q.get(job.id).status is JobStatus.PENDING


def test_verify_fastpath_green_test_does_not_prove_unrelated_code_change(tmp_path):
    root=workspace(tmp_path)
    (root/"module.py").write_text("VALUE = 2\n")
    q=LocalJobQueue(root)
    job=q.enqueue(task_id="task-claimed",kind=JobKind.VERIFY,payload={
        "tests":["tests/test_ok.py"],
    })
    result=drain_verify_jobs(q,max_jobs=1,timeout_seconds=60)
    assert result["completed_count"]==1
    terminal=q.get(job.id)
    assert terminal.result["verification"]["verdict"]=="TESTS_ONLY"
    assert terminal.result["implementation_verified"] is False
    assert terminal.result["task_completed"] is False


def test_verify_fastpath_failed_tests_remain_failed(tmp_path):
    root=workspace(tmp_path)
    (root/"tests/test_ok.py").write_text("def test_bad():\n    assert False\n")
    q=LocalJobQueue(root)
    job=q.enqueue(task_id="task-failure",kind=JobKind.VERIFY,payload={
        "tests":["tests/test_ok.py"],
    })
    result=drain_verify_jobs(q,max_jobs=1,timeout_seconds=60)
    assert result["failed_count"]==1
    terminal=q.get(job.id)
    assert terminal.status is JobStatus.FAILED
    assert terminal.result["verification"]["verdict"]=="FAIL"
    assert terminal.result["implementation_verified"] is False


def test_verify_fastpath_rejects_path_traversal(tmp_path):
    root=workspace(tmp_path)
    q=LocalJobQueue(root)
    job=q.enqueue(task_id="task-traversal",kind=JobKind.VERIFY,payload={
        "tests":["tests/../../outside.py"],
    })
    result=drain_verify_jobs(q,max_jobs=1)
    assert result["skipped_count"]==1
    assert q.get(job.id).status is JobStatus.PENDING


def test_verify_fastpath_rejects_symlink_outside_workspace(tmp_path):
    root=workspace(tmp_path)
    external=tmp_path/"outside.py"
    external.write_text("def test_external():\n    assert True\n")
    (root/"tests/test_outside.py").symlink_to(external)
    q=LocalJobQueue(root)
    job=q.enqueue(task_id="task-symlink",kind=JobKind.VERIFY,payload={
        "tests":["tests/test_outside.py"],
    })
    result=drain_verify_jobs(q,max_jobs=1)
    assert result["skipped_count"]==1
    assert q.get(job.id).status is JobStatus.PENDING
