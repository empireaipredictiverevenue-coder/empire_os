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
    assert terminal.result["verification"]["verdict"]=="PASS"
    assert terminal.result["changed_files_inferred"] is False
    assert terminal.result["model_inference"] is False

def test_verify_fastpath_skips_invalid_test_contract(tmp_path):
    root=workspace(tmp_path)
    q=LocalJobQueue(root)
    job=q.enqueue(task_id="task-invalid",kind=JobKind.VERIFY,payload={"tests":["scripts/deploy.py"]})
    result=drain_verify_jobs(q,max_jobs=1)
    assert result["skipped_count"]==1
    assert q.get(job.id).status is JobStatus.PENDING
