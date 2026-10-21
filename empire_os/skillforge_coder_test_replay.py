"""Bounded current-revision replay of source-linked historical Coder test receipts.

This is a one-shot *development worktree* replay, not a production activation,
independent Department completion, original-code-revision reproduction or
SkillForge approval. Historical job text never supplies commands to execute.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any, Callable
import json
import os
import subprocess
import sys

from empire_os.skillforge_learning import _verified_learning_observations, WORK_ID
from empire_os.skillforge_independent_evidence import (
    MAX_RECORD, _read_safe, _source_context, _internal_pytest_receipt,
)

# Independently inspected fixture-oriented tests. NEVER execute a test path or
# command taken directly from original untrusted Coder job JSON.
FIXED_TESTS = (
    "tests/test_search_traffic_forecast.py",
    "tests/test_organic_search_legacy_recovery.py",
    "tests/test_competitor_search_presence.py",
)
MAX_ORIGINAL_JOBS = 15000
MAX_SELECTED_JOBS = 2
TIMEOUT_SECONDS = 45


def _git(root:Path,*args:str)->str:
    proc=subprocess.run(
        ["git",*args],cwd=root,check=False,
        capture_output=True,text=True,timeout=10)
    if proc.returncode!=0:
        raise ValueError("Git source revision unavailable")
    return proc.stdout.strip()


def _safe_tests(worktree:Path)->dict[str,str]:
    hashes={}
    for relative in FIXED_TESTS:
        test=worktree/relative
        if (test.is_symlink()
            or not test.resolve().is_relative_to(worktree)
            or (worktree/"tests").is_symlink()
            or not test.is_file()
            or test.stat().st_size>256000 or test.stat().st_size==0):
            raise ValueError("selected test is missing or unsafe")
        hashes[relative]=sha256(test.read_bytes()).hexdigest()
    return hashes


def original_coder_test_sources(original_root:Path)->list[dict[str,str]]:
    """Return up to two verified original job digests, never raw identifiers."""
    original_root=Path(original_root).resolve()
    valid,invalid,truncated=_verified_learning_observations(
        original_root,max_observations=5000)
    if invalid or truncated:
        raise ValueError("incomplete canonical SkillForge observation audit")
    done=original_root/"runtime/departments/work/done"
    directory=original_root/"runtime/coder/jobs/completed"
    if done.is_symlink() or directory.is_symlink() or not directory.is_dir():
        raise ValueError("unsafe original DONE / Coder job store")
    done_index={
        sha256(path.stem.encode()).hexdigest():path
        for path in done.glob("dept_work_*.json")
        if WORK_ID.fullmatch(path.stem) and not path.is_symlink()
    }
    completed_plans={}
    for row in valid:
        if row["component"]!="empire_coder" or row["adapter"]!="empire_coder_plan_bridge":
            continue
        refs,ctx,(state,_),plan_link=_source_context(
            original_root,row,done_index)
        if state=="COMPLETED_CODER_PLAN_JOB" and plan_link is not None:
            plan_id,task_id,work_id=plan_link
            completed_plans[plan_id]=(task_id,work_id,row["source_work_sha256"])
    candidates=[]
    count=0
    for path in directory.glob("coder_job_*.json"):
        count+=1
        if count>MAX_ORIGINAL_JOBS:
            raise ValueError("original job inventory exceeds bounded review")
        if path.is_symlink():
            raise ValueError("unsafe original VERIFY job")
        raw=path.read_bytes() if 0<path.stat().st_size<=MAX_RECORD else b""
        if not raw:
            continue
        try:
            job=json.loads(raw)
        except (ValueError,UnicodeError):
            continue
        if not isinstance(job,dict) or job.get("kind")!="VERIFY":
            continue
        payload=job.get("payload")
        result=job.get("result")
        if not isinstance(payload,dict) or not isinstance(result,dict):
            continue
        plan_id=payload.get("source_plan_job_id")
        if not isinstance(plan_id,str) or plan_id not in completed_plans:
            continue
        task_id,work_id,work_sha=completed_plans[plan_id]
        original_tests=payload.get("tests")
        if (not isinstance(original_tests,list)
            or len(original_tests)!=len(FIXED_TESTS)
            or set(original_tests)!=set(FIXED_TESTS)):
            continue
        if (job.get("id")!=path.stem or job.get("task_id")!=task_id
            or payload.get("source_plan_task_id")!=task_id
            or payload.get("department_work_id")!=work_id
            or payload.get("execution_authority")!="none"
            or job.get("status")!="COMPLETED" or job.get("error") is not None
            or result.get("production_mutation") is not False
            or result.get("external_execution_performed") is True
            or result.get("execution_authority") not in (None,"none")
            or not _internal_pytest_receipt(result,payload)):
            continue
        candidates.append({
            "historical_verify_receipt_sha256":sha256(raw).hexdigest(),
            "source_work_reference_sha256":work_sha,
            "source_plan_reference_sha256":sha256(plan_id.encode()).hexdigest(),
            "historical_verify_job_reference_sha256":sha256(path.stem.encode()).hexdigest(),
        })
    candidates.sort(key=lambda x:x["historical_verify_job_reference_sha256"])
    if len(candidates)<MAX_SELECTED_JOBS:
        raise ValueError("fewer than two distinct qualified original VERIFY receipts")
    selected=[]
    selected_plans=set()
    for entry in candidates:
        plan_sha=entry["source_plan_reference_sha256"]
        if plan_sha not in selected_plans:
            selected_plans.add(plan_sha)
            selected.append(entry)
        if len(selected)==MAX_SELECTED_JOBS:
            break
    if len(selected)<MAX_SELECTED_JOBS:
        raise ValueError("source jobs are not distinct planning observations")
    return selected


def replay_current_tests(worktree:Path,original_root:Path, *,
                         execute:Callable[...,Any]=subprocess.run)->dict[str,Any]:
    """One bounded command, fixed selected tests, no network or production writes."""
    worktree=Path(worktree).resolve()
    original_root=Path(original_root).resolve()
    if worktree==original_root or not (worktree/".git").exists():
        raise ValueError("tests must run in an isolated Git worktree")
    if _git(worktree,"status","--porcelain","--untracked-files=normal"):
        raise ValueError("current replay worktree must be clean")
    base_head=_git(worktree,"rev-parse","HEAD")
    test_hashes=_safe_tests(worktree)
    originals=original_coder_test_sources(original_root)
    env=os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"]="1"
    env["PYTHONPATH"]=str(worktree)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"]="1"
    env.pop("PYTEST_ADDOPTS",None)
    cmd=[sys.executable,"-B","-m","pytest","-q","-p","no:cacheprovider",*FIXED_TESTS]
    result=execute(cmd,cwd=worktree,env=env,capture_output=True,
                   text=True,timeout=TIMEOUT_SECONDS,check=False)
    changed=_git(worktree,"status","--porcelain","--untracked-files=normal")
    same_head=_git(worktree,"rev-parse","HEAD")==base_head
    same_tests=_safe_tests(worktree)==test_hashes
    # Never claim a pass when the runner changed its own inputs or workspace.
    return {
        "schema_version":"empire.skillforge.coder_current_revision_test_replay.v1",
        "mode":"ISOLATED_DEVELOPMENT_READONLY_TEST_REPLAY",
        "current_worktree_head":base_head,
        "source_original_root_used_for_read_only_receipts":True,
        "selected_historical_receipt_count":len(originals),
        "historical_original_receipts":originals,
        "fixed_test_files":list(FIXED_TESTS),
        "current_test_file_sha256":test_hashes,
        "current_revision_test_subprocess_executed":True,
        "current_revision_test_exit_code":result.returncode,
        "current_revision_tests_passed":(
            type(result.returncode) is int and result.returncode==0
            and not changed and same_head and same_tests
        ),
        "current_revision_test_workspace_clean":not bool(changed),
        "current_revision_head_unchanged":same_head,
        "current_revision_test_files_unchanged":same_tests,
        "historical_source_revision_reproduced":False,
        "historical_production_revision_tested":False,
        "historical_production_change_authenticated":False,
        "independent_agent_completion_or_owner_attestation":False,
        "independently_verified_code_implementations":0,
        "independently_verified_business_outcomes":0,
        "skillforge_promotion_authorized":False,
        "production_activation_authorized":False,
        "execution_authority":"none",
    }
