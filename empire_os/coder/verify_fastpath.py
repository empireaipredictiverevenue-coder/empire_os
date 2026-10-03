"""Deterministic no-model verification lane for queued VERIFY jobs."""
from __future__ import annotations
import os, subprocess, sys, time
from typing import Any
from .jobs import JobKind, LocalJobQueue

def _valid_test(path: str) -> bool:
    return path.startswith("tests/") and path.endswith(".py")

def drain_verify_jobs(
    queue: LocalJobQueue,
    *,
    max_jobs: int = 2,
    timeout_seconds: int = 900,
    worker_id: str = "coder-verify-fastpath",
) -> dict[str, Any]:
    root=queue.workspace
    bounded=max(1,min(int(max_jobs),8))
    timeout=max(30,min(int(timeout_seconds),1800))
    completed=[]; failed=[]; skipped=[]
    child_env=os.environ.copy()
    child_env.pop("PYTEST_ADDOPTS",None)
    child_env["PYTHONDONTWRITEBYTECODE"]="1"
    for candidate in queue.list_pending(kind=JobKind.VERIFY)[:bounded]:
        tests=[str(v).strip() for v in (candidate.payload.get("tests") or ()) if str(v).strip()]
        if not tests or any(not _valid_test(t) for t in tests):
            skipped.append({"job_id":candidate.id,"reason":"valid_repository_tests_required"})
            continue
        claimed=queue.claim_specific(candidate.id,worker_id=worker_id,lease_seconds=max(120,timeout+60))
        if claimed is None:
            continue
        started=time.perf_counter()
        try:
            py=subprocess.run(
                [sys.executable,"-m","pytest","-q",*tests],
                cwd=root,capture_output=True,text=True,timeout=timeout,check=False,env=child_env,
            )
            diff=subprocess.run(
                ["git","diff","--check"],
                cwd=root,capture_output=True,text=True,timeout=60,check=False,env=child_env,
            )
        except subprocess.TimeoutExpired:
            terminal=queue.fail(claimed,"deterministic_verify_timeout")
            failed.append({"job_id":terminal.id,"reason":"timeout"})
            continue
        elapsed=round((time.perf_counter()-started)*1000.0,3)
        passed=py.returncode==0 and diff.returncode==0
        result={
            "kind":"VERIFY",
            "verification":{
                "verdict":"PASS" if passed else "FAIL",
                "checks":[
                    {"name":"pytest","passed":py.returncode==0,"returncode":py.returncode,"tests":tests,
                     "output_tail":((py.stdout or "")+"\n"+(py.stderr or ""))[-8000:]},
                    {"name":"git_diff_check","passed":diff.returncode==0,"returncode":diff.returncode,
                     "output_tail":((diff.stdout or "")+"\n"+(diff.stderr or ""))[-4000:]},
                ],
                "elapsed_ms":elapsed,
                "reasons":[] if passed else ["verification_failed"],
                "warnings":[],
            },
            "tests":tests,
            "changed_files_inferred":False,
            "model_inference":False,
            "production_mutation":False,
            "external_execution_performed":False,
            "execution_authority":"none",
        }
        if passed:
            terminal=queue.complete(claimed,result)
            completed.append({"job_id":terminal.id,"task_id":terminal.task_id,"test_count":len(tests),"elapsed_ms":elapsed})
        else:
            terminal=queue.fail(
                claimed,
                "deterministic_verification_failed",
                result=result,
            )
            failed.append({"job_id":terminal.id,"reason":"verification_failed",
                           "pytest_returncode":py.returncode,"diff_check_returncode":diff.returncode})
    return {
        "schema_version":"empire.coder.verify-fastpath.v1",
        "status":"AVAILABLE",
        "completed_count":len(completed),
        "failed_count":len(failed),
        "skipped_count":len(skipped),
        "completed":completed,
        "failed":failed,
        "skipped":skipped,
        "model_inference":False,
        "production_mutation":False,
        "execution_authority":"none",
    }
