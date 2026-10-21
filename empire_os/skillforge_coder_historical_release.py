"""Validate bounded historical Empire Coder release receipts against Git objects.

Original release proof is not proof that an old Department plan caused a commit,
that a change is on today's production ancestry, or that the technique may be
promoted to a trusted SkillForge skill. No arbitrary receipt-supplied commands.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import re
import subprocess
from typing import Any

from empire_os.skillforge_coder_patch_provenance import _relative_code_path

HEX40=re.compile(r"^[0-9a-f]{40}$")
HEX64=re.compile(r"^[0-9a-f]{64}$")
MAX_BYTES=120000

# Explicit, previously reviewed first-party release receipts and test scopes.
RELEASES=(
    {
        "name":"CODER_SANDBOX_RUNTIME_BUDGET_GUARD",
        "path":"runtime/execution_plane/coder_sandbox_runtime_deadline_release_20261020.json",
        "sha256":"551fd0aaacc1792f89e5ef6f686d61cff517301236177793b165a34d2b783613",
        "status":"SCOPED_CODER_RUNTIME_BUDGET_GUARD_INSTALLED",
        "source_commit":"c8f3c55e935333128ad749a38b64f4a6127391ad",
        "test":"tests/test_empire_coder_sandbox_runner.py",
    },
    {
        "name":"CODER_PROVIDER_HEALTH_RECOVERY",
        "path":"runtime/execution_plane/coder_provider_malformed_routes_release_20261020.json",
        "sha256":"26c3775cdf94da834ecd1624ff9f999b8a13e575039dd4f8792e179f096e6645",
        "status":"SCOPED_PROVIDER_HEALTH_RECOVERY_INSTALLED",
        "source_commit":"f087fe743b5f9c81ad7e376f7545817568ec2181",
        "test":"tests/coder/test_provider_health.py",
    },
)


def _run_git(repo:Path,*args:str)->tuple[bool,bytes]:
    proc=subprocess.run(
        ["git",*args],cwd=repo,capture_output=True,timeout=12,check=False,
    )
    return proc.returncode==0,proc.stdout


def _original_release_evidence(original_root:Path,repo:Path,spec:dict)->dict[str,Any]:
    base={
        "release":spec["name"],
        "original_receipt_sha256":spec["sha256"],
        "commit_object_verified":False,
        "commit_parent_source_bytes_verified":False,
        "commit_changed_file_hashes_verified":False,
        "git_commit_on_current_head_ancestry":False,
        "exact_historical_revision_test_replayed":False,
        "independent_department_completion_attributed":False,
        "skill_promotion_authorized":False,
    }
    original=original_root/spec["path"]
    try:
        if (original.is_symlink() or original.parent.is_symlink()
            or not original.is_file()
            or not 0<original.stat().st_size<=MAX_BYTES):
            raise ValueError("original release receipt missing or unsafe")
        raw=original.read_bytes()
        if sha256(raw).hexdigest()!=spec["sha256"]:
            raise ValueError("original release receipt hash changed")
        data=json.loads(raw)
        if not isinstance(data,dict):
            raise ValueError("original receipt must be an object")
        commit=data.get("source_commit")
        prior=data.get("prior_head")
        if (data.get("status")!=spec["status"]
            or commit!=spec["source_commit"]
            or not isinstance(prior,str) or not HEX40.fullmatch(prior)):
            raise ValueError("unexpected original release identity")
        changed=data.get("paths",data.get("files"))
        blobs=data.get("sha256")
        old=data.get("old_hex")
        if (not isinstance(changed,list) or not 1<=len(changed)<=10
            or not isinstance(blobs,dict) or not isinstance(old,dict)
            or set(changed)!=set(blobs) or set(changed)!=set(old)
            or len(set(changed))!=len(changed)
            or not all(_relative_code_path(f) for f in changed)
            or spec["test"] not in changed
            or not any(f.startswith("empire_os/") for f in changed)):
            raise ValueError("untrusted original changed-file contract")
        if (not all(isinstance(blobs[f],str) and HEX64.fullmatch(blobs[f])
                    for f in changed)):
            raise ValueError("invalid original source digests")
        ok,parents=_run_git(repo,"rev-list","--parents","-n","1",commit)
        if not ok or parents.decode().strip()!=commit+" "+prior:
            raise ValueError("source commit parent differs from original receipt")
        ok,names=_run_git(repo,"diff-tree","--no-commit-id","--name-only","-r",commit)
        if not ok or set(names.decode().splitlines())!=set(changed):
            raise ValueError("original commit changed-file list differs")
        for filename in changed:
            ok,after=_run_git(repo,"show",commit+":"+filename)
            if not ok or sha256(after).hexdigest()!=blobs[filename]:
                raise ValueError("original source commit blob hash differs")
            hex_value=old[filename]
            if (not isinstance(hex_value,str) or len(hex_value)>MAX_BYTES*2
                or len(hex_value)%2!=0):
                raise ValueError("invalid original parent file digest")
            try:
                previous=bytes.fromhex(hex_value)
            except ValueError as exc:
                raise ValueError("original parent bytes malformed") from exc
            ok,old_git=_run_git(repo,"show",prior+":"+filename)
            if not ok or previous!=old_git:
                raise ValueError("original parent bytes do not match Git")
        ok,_=_run_git(repo,"merge-base","--is-ancestor",commit,"HEAD")
        return {
            **base,
            "status":"ORIGINAL_GIT_RELEASE_SOURCE_CHAIN_VERIFIED",
            "commit_object_verified":True,
            "commit_parent_source_bytes_verified":True,
            "commit_changed_file_hashes_verified":True,
            "git_commit_on_current_head_ancestry":ok,
            "source_commit_sha256":sha256(commit.encode()).hexdigest(),
            "original_parent_commit_sha256":sha256(prior.encode()).hexdigest(),
            "source_changed_file_count":len(changed),
            "historical_test_file":spec["test"],
            "historical_test_blob_sha256":blobs[spec["test"]],
        }
    except (OSError,ValueError,TypeError,UnicodeError,subprocess.SubprocessError):
        return {**base,"status":"ORIGINAL_GIT_RELEASE_SOURCE_CHAIN_HOLD"}


def audit_original_coder_release_sources(
    original_root:Path,repo:Path,
)->dict[str,Any]:
    original_root=Path(original_root).resolve()
    repo=Path(repo).resolve()
    evidence=[_original_release_evidence(original_root,repo,item)
              for item in RELEASES]
    complete=all(i["status"]=="ORIGINAL_GIT_RELEASE_SOURCE_CHAIN_VERIFIED"
                 for i in evidence)
    return {
        "schema_version":"empire.skillforge.coder_original_git_release_sources.v1",
        "mode":"ORIGINAL_RELEASE_READONLY_GIT_OBJECT_AUDIT",
        "status":("TWO_HISTORICAL_RELEASE_SOURCE_CHAINS_VERIFIED"
                  if complete else "ORIGINAL_RELEASE_SOURCE_CHAIN_HOLD"),
        "historical_receipts_checked":len(evidence),
        "git_source_chains_verified":sum(
            x["status"]=="ORIGINAL_GIT_RELEASE_SOURCE_CHAIN_VERIFIED"
            for x in evidence),
        "historical_release_commits_on_current_head_ancestry":sum(
            x["git_commit_on_current_head_ancestry"] for x in evidence),
        "release_provenance":evidence,
        "independent_department_completions_proven":0,
        "independently_authenticated_production_deployments":0,
        "independently_verified_skill_outcomes":0,
        "skillforge_auto_approval":False,
        "execution_authority":"none",
    }
