"""Fail-closed attribution of original Empire Coder VERIFY jobs to exact Git changes.

A test PASS is not a patch; an intended changed_files list is not a Git
change. Evidence of Git content identity is still not independent completion,
customer impact or approval to execute a reusable skill.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
import json
import re
import subprocess

from empire_os.skillforge_coder_test_replay import (
    MAX_ORIGINAL_JOBS, original_coder_test_sources,
)
from empire_os.skillforge_independent_evidence import MAX_RECORD, _internal_pytest_receipt

COMMIT = re.compile(r"^[a-f0-9]{40}$")
SAFE_PATH = re.compile(r"^(?:empire_os|tests)/[A-Za-z0-9_./-]{1,240}\.py$")
MAX_CHANGED = 80


def _relative_code_path(value: Any) -> bool:
    if not isinstance(value,str) or not SAFE_PATH.fullmatch(value):
        return False
    parts=PurePosixPath(value).parts
    return (all(part not in ("..",".","") for part in parts)
            and "//" not in value and "\\" not in value)


def _git(repo:Path,*args:str)->tuple[int,str]:
    run=subprocess.run(
        ["git",*args],cwd=repo,capture_output=True,text=True,
        timeout=12,check=False,
    )
    return run.returncode,run.stdout.strip()


def check_original_coder_commit(
    repo:Path, verify_job:Mapping[str,Any],
) -> dict[str,Any]:
    """Require explicit linked commit and its exact source-file path set.

    A matching Git commit proves attribution to an immutable repository
    object; it does not prove independent review, author identity, production
    deployment or fitness of a reusable skill.
    """
    base={
        "status":"SOURCE_COMMIT_UNPROVEN",
        "explicit_original_implementation_commit_present":False,
        "git_commit_path_set_confirmed":False,
        "independently_verified_implementation":False,
        "source_deployment_verified":False,
        "automatic_skill_promotion":False,
        "execution_authority":"none",
    }
    payload=verify_job.get("payload")
    result=verify_job.get("result")
    if (verify_job.get("kind")!="VERIFY"
        or verify_job.get("status")!="COMPLETED"
        or not isinstance(payload,dict) or not isinstance(result,dict)
        or not _internal_pytest_receipt(result,payload)):
        return {**base,"status":"INELIGIBLE_OR_UNSUPPORTED_VERIFY_JOB"}
    claimed=result.get("implementation_commit_sha")
    if claimed is None:
        return {**base,"status":"MISSING_EXPLICIT_IMPLEMENTATION_COMMIT"}
    if not isinstance(claimed,str) or not COMMIT.fullmatch(claimed):
        return {**base,"status":"INVALID_EXPLICIT_IMPLEMENTATION_COMMIT"}
    base["explicit_original_implementation_commit_present"]=True
    changed=payload.get("changed_files")
    if (not isinstance(changed,list) or not 0<len(changed)<=MAX_CHANGED
        or any(not _relative_code_path(x) for x in changed)
        or len(changed)!=len(set(changed))
        or not any(x.startswith("empire_os/") for x in changed)):
        return {**base,"status":"UNSAFE_OR_NONCODE_CHANGED_PATHS"}
    try:
        rc,ref=_git(repo,"rev-parse","--verify",claimed+"^{commit}")
        if rc or ref!=claimed:
            return {**base,"status":"ORIGINAL_COMMIT_NOT_IN_REPOSITORY"}
        rc,anc=_git(repo,"merge-base","--is-ancestor",claimed,"HEAD")
        if rc:
            return {**base,"status":"ORIGINAL_COMMIT_NOT_IN_CURRENT_ANCESTRY"}
        rc,parents=_git(repo,"rev-list","--parents","-n","1",claimed)
        if rc or len(parents.split())!=2:
            return {**base,"status":"MERGE_OR_ROOT_COMMIT_REQUIRES_OWNER_REVIEW"}
        rc,names=_git(repo,"diff-tree","--no-commit-id","--name-only","-r",claimed)
        if rc:
            return {**base,"status":"ORIGINAL_COMMIT_DIFF_UNAVAILABLE"}
        actual={name for name in names.splitlines() if name}
        if actual!=set(changed):
            return {**base,"status":"CLAIMED_PATHS_NOT_EXACT_GIT_DIFF"}
        # Make sure each changed path is an actual tracked file in the
        # attributed source revision, not merely a deleted path.
        for name in sorted(actual):
            rc,_=_git(repo,"cat-file","-e",claimed+":"+name)
            if rc:
                return {**base,"status":"COMMIT_SOURCE_CONTENT_MISSING"}
        return {
            **base,
            "status":"ORIGINAL_GIT_COMMIT_PATHS_MATCHED_REVIEW_ONLY",
            "git_commit_path_set_confirmed":True,
            "commit_sha256":sha256(claimed.encode()).hexdigest(),
            "changed_python_file_count":len(actual),
        }
    except (OSError,subprocess.SubprocessError,ValueError,TypeError):
        return {**base,"status":"GIT_PROVENANCE_CHECK_UNAVAILABLE"}


def audit_selected_coder_patch_provenance(
    original_root:Path,repo:Path,
)->dict[str,Any]:
    """Audit two independently linked planning receipts, no original writes."""
    original_root=Path(original_root).resolve()
    repo=Path(repo).resolve()
    selected=original_coder_test_sources(original_root)
    digests={x["historical_verify_receipt_sha256"] for x in selected}
    folder=original_root/"runtime/coder/jobs/completed"
    if folder.is_symlink():
        raise ValueError("unsafe source job directory")
    results=[]
    matched=set()
    count=0
    for path in folder.glob("coder_job_*.json"):
        count+=1
        if count>MAX_ORIGINAL_JOBS:
            raise ValueError("original Coder job inventory exceeds limit")
        if path.is_symlink():
            raise ValueError("original source job symlink")
        if not 0<path.stat().st_size<=MAX_RECORD:
            continue
        raw=path.read_bytes()
        digest=sha256(raw).hexdigest()
        if digest not in digests:
            continue
        if digest in matched:
            raise ValueError("duplicate original job content digest")
        job=json.loads(raw)
        if not isinstance(job,dict) or job.get("id")!=path.stem:
            raise ValueError("original job identity mismatch")
        attestation=check_original_coder_commit(repo,job)
        matched.add(digest)
        results.append({
            "historical_verify_receipt_sha256":digest,
            **attestation,
        })
    if matched!=digests:
        raise ValueError("missing original job evidence")
    results.sort(key=lambda x:x["historical_verify_receipt_sha256"])
    successes=sum(x["git_commit_path_set_confirmed"] for x in results)
    return {
        "schema_version":"empire.skillforge.coder_patch_provenance_audit.v1",
        "mode":"ORIGINAL_SOURCE_READONLY",
        "status":("SOURCE_COMMIT_LINKS_PRESENT_REVIEW_REQUIRED" if successes
                  else "MISSING_EXPLICIT_HISTORICAL_IMPLEMENTATION_COMMITS"),
        "selected_original_job_count":len(results),
        "historical_source_commit_path_matches":successes,
        "missing_explicit_implementation_commit_count":sum(
            x["status"]=="MISSING_EXPLICIT_IMPLEMENTATION_COMMIT"
            for x in results),
        "individual_original_receipts":results,
        "independent_code_implementations_verified":0,
        "original_test_revision_reproduced":False,
        "production_deployment_authenticated":False,
        "skillforge_auto_approval":False,
        "execution_authority":"none",
    }
