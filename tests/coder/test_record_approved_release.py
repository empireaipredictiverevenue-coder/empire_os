"""Canonical recorded source release, not a forged implementation completion."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess

import pytest

from empire_os.coder.jobs import (
    JobKind, JobQueueError, JobStatus, LocalJobQueue,
)


def _run(repo: Path, *argv: str) -> str:
    return subprocess.run(
        ("git", *argv), cwd=repo, check=True,
        capture_output=True, text=True,
    ).stdout.strip()


def _evidence(tmp_path):
    repo=tmp_path/"repo"
    repo.mkdir()
    _run(repo,"init","-q")
    _run(repo,"branch","-M","agent/data-cloud-wave4")
    (repo/".gitignore").write_text("runtime/\n")
    (repo/"hello.py").write_text("VALUE = 1\n")
    _run(repo,"add","hello.py",".gitignore")
    _run(repo,"-c","user.name=Test","-c","user.email=test@example.com",
         "commit","-qm","baseline")
    base=_run(repo,"rev-parse","HEAD")
    q=LocalJobQueue(repo)
    enqueued=q.enqueue(
        task_id="test-release",
        kind=JobKind.IMPLEMENT,
        payload={
            "execution_mode":"ISOLATED_CANDIDATE_ONLY",
            "allowed_paths":["hello.py"],
            "plan_promotion_key":"original-plan-promotion-unique-key",
        },
    )
    original=repo/"hello.py"
    original.write_text("VALUE = 2\n")
    patch=subprocess.check_output(("git","diff","--","hello.py"),cwd=repo)
    digest=sha256(patch).hexdigest()
    approvals=repo/"runtime/execution_plane/coder_proposals"
    approvals.mkdir(parents=True,exist_ok=True)
    patch_path=approvals/f"{enqueued.id}.patch"
    patch_path.write_bytes(patch)
    claimed=q.claim_specific(enqueued.id)
    q.hold_candidate_for_approval(
        claimed,
        result={
            "candidate_status":"LOCAL_PROPOSAL_READY",
            "candidate_verification_passed":True,
            "implementation_verified":False,
            "task_completed":False,
            "founder_release_required":True,
            "proposal_sha256":digest,
            "proposal_patch":str(patch_path),
            "source_commit":base,
        },
    )
    _run(repo,"add","hello.py")
    _run(repo,"-c","user.name=Test","-c","user.email=test@example.com",
         "commit","-qm","approved implementation")
    released=_run(repo,"rev-parse","HEAD")
    approved_doc={
        "schema_version":"empire.coder.founder_scoped_release_authorization.v1",
        "authorization_interpretation":
            "FOUNDER_APPROVAL_TO_GUARDED_RELEASE_THIS_EXACT_CODE_PATCH_ONLY",
        "preflight_approved":True,
        "job_id":enqueued.id,"source_commit":base,"patch_sha256":digest,
        "exact_allowed_paths":["hello.py"],
    }
    release_doc={
        "schema_version":"empire.coder.guarded_source_release.v1",
        "job_id":enqueued.id,
        "base_commit":base,
        "release_commit":released,
        "approved_patch_sha256":digest,
        "changed_paths":["hello.py"],
        "source_release_committed":True,
        "scoped_release_tests_passed":True,
        "after_sha256":{"hello.py":sha256(original.read_bytes()).hexdigest()},
    }
    approve=approvals/f"{enqueued.id}_founder_scope_approval_test.json"
    release=approvals/f"{enqueued.id}_guarded_source_release_test.json"
    release_doc["approval_record_path"]=str(approve)
    approve.write_text(json.dumps(approved_doc))
    release.write_text(json.dumps(release_doc))
    return repo,q,enqueued.id,approve,release,released


def test_founder_approved_exact_released_commit_transitions_to_released(tmp_path):
    repo,q,jid,approval,release,commit=_evidence(tmp_path)
    assert q.get(jid).status is JobStatus.AWAITING_APPROVAL
    job=q.record_approved_release(
        jid,approval_record=approval,release_record=release,
    )
    assert job.status is JobStatus.RELEASED
    assert job.result["release"]["status"]=="FOUNDER_APPROVED_SOURCE_RELEASE_VERIFIED"
    assert job.result["release"]["release_commit"]==commit
    assert job.result["implementation_verified"] is False
    assert job.result["task_completed"] is False
    assert q.get(jid).status is JobStatus.RELEASED
    assert not list(q.awaiting_approval.glob(f"{jid}.json"))
    assert (q.released/f"{jid}.json").exists()
    assert (q.released/f"{jid}.json").stat().st_mode&0o777==0o600
    assert not list(q.completed.glob(f"{jid}.json"))
    from empire_os.coder.plan_promotion import _existing_promotion_keys
    assert "original-plan-promotion-unique-key" in _existing_promotion_keys(q)
    # Deterministic idempotency: no second transition, no forged completion.
    again=q.record_approved_release(
        jid,approval_record=approval,release_record=release,
    )
    assert again.status is JobStatus.RELEASED
    assert again.result==job.result


@pytest.mark.parametrize("tamper",(
    "approval_not_granted","approval_sha","release_sha",
    "unapproved_path","fake_commit","fake_after_hash",
    "missing_release_tests","uncommitted_source_change",
))
def test_mismatched_release_is_rejected_without_mutating_queue(tmp_path,tamper):
    repo,q,jid,approval,release,commit=_evidence(tmp_path)
    approval_data=json.loads(approval.read_text())
    release_data=json.loads(release.read_text())
    if tamper=="approval_not_granted":
        approval_data["authorization_interpretation"]="ASSUMED"
    elif tamper=="approval_sha":
        approval_data["patch_sha256"]="a"*64
    elif tamper=="release_sha":
        release_data["approved_patch_sha256"]="b"*64
    elif tamper=="unapproved_path":
        release_data["changed_paths"]=["credentials.json"]
    elif tamper=="fake_commit":
        release_data["release_commit"]="c"*40
    elif tamper=="fake_after_hash":
        release_data["after_sha256"]["hello.py"]="d"*64
    elif tamper=="missing_release_tests":
        release_data["scoped_release_tests_passed"]=False
    elif tamper=="uncommitted_source_change":
        (repo/"hello.py").write_text("VALUE = 444\n")
    approval.write_text(json.dumps(approval_data))
    release.write_text(json.dumps(release_data))
    with pytest.raises(JobQueueError):
        q.record_approved_release(
            jid,approval_record=approval,release_record=release,
        )
    assert q.get(jid).status is JobStatus.AWAITING_APPROVAL
    assert (q.awaiting_approval/f"{jid}.json").exists()
    assert not (q.released/f"{jid}.json").exists()


def test_approved_release_can_be_reconciled_after_unrelated_commit(tmp_path):
    repo,q,jid,approval,release,commit=_evidence(tmp_path)
    (repo/"unrelated.md").write_text("other owner change\n")
    _run(repo,"add","unrelated.md")
    _run(repo,"-c","user.name=Other","-c","user.email=other@example.com",
         "commit","-qm","unrelated authorized improvement")
    assert _run(repo,"rev-parse","HEAD")!=commit
    reconciled=q.record_approved_release(
        jid,approval_record=approval,release_record=release,
    )
    assert reconciled.status is JobStatus.RELEASED
    assert reconciled.result["release"]["release_commit"]==commit


def test_candidate_cannot_be_released_without_approval_state(tmp_path):
    repo,q,jid,approval,release,commit=_evidence(tmp_path)
    (q.awaiting_approval/f"{jid}.json").unlink()
    with pytest.raises(JobQueueError,match="candidate_not_awaiting_approval"):
        q.record_approved_release(
            jid,approval_record=approval,release_record=release,
        )


def test_receipts_must_be_local_not_symlinks_or_other_jobs(tmp_path):
    repo,q,jid,approval,release,commit=_evidence(tmp_path)
    outside=tmp_path/"external.json"
    outside.write_text(approval.read_text())
    with pytest.raises(JobQueueError,match="release_evidence_path_not_authorized"):
        q.record_approved_release(
            jid,approval_record=outside,release_record=release,
        )
    symlink=approval.with_name(f"{jid}_founder_scope_approval_link.json")
    symlink.symlink_to(approval)
    with pytest.raises(JobQueueError,match="release_evidence_path_not_authorized"):
        q.record_approved_release(
            jid,approval_record=symlink,release_record=release,
        )
    assert q.get(jid).status is JobStatus.AWAITING_APPROVAL
