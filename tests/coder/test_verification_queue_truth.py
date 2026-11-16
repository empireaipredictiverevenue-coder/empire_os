"""Verification jobs must not be completed when their actual verdict fails."""
from __future__ import annotations

import subprocess

import pytest

from empire_os.coder.jobs import JobKind, JobStatus, LocalJobQueue


@pytest.fixture
def queue(tmp_path):
    root=tmp_path / "repo"
    root.mkdir()
    subprocess.run(("git","init","-q",str(root)),check=True)
    return LocalJobQueue(root)


@pytest.mark.parametrize("verdict", ["FAIL", "UNKNOWN", ""])
def test_failure_or_unknown_verdict_is_recorded_as_failed(queue, verdict):
    job=queue.enqueue(task_id="real-verification",kind=JobKind.VERIFY)
    active=queue.claim_specific(job.id)
    terminal=queue.complete(active,{"verification":{"verdict":verdict,"checks":[]}})
    assert terminal.status is JobStatus.FAILED
    assert "verification_verdict_not_successful" in (terminal.error or "")
    assert queue.get(job.id).status is JobStatus.FAILED
    assert terminal.result["verification"]["verdict"]==verdict


@pytest.mark.parametrize("verdict", ["PASS","PASS_WITH_WARNINGS","TESTS_ONLY"])
def test_evidence_or_explicit_test_only_job_processing_can_finish(queue, verdict):
    job=queue.enqueue(task_id="real-verification",kind=JobKind.VERIFY)
    active=queue.claim_specific(job.id)
    terminal=queue.complete(active,{"verification":{"verdict":verdict},
                                     "implementation_verified":False,
                                     "task_completed":False})
    assert terminal.status is JobStatus.COMPLETED
    assert queue.get(job.id).result["verification"]["verdict"]==verdict


def test_missing_verification_packet_fails_closed(queue):
    job=queue.enqueue(task_id="missing-verdict",kind=JobKind.VERIFY)
    active=queue.claim_specific(job.id)
    terminal=queue.complete(active,{"tests":["tests/test_smoke.py"]})
    assert terminal.status is JobStatus.FAILED


def test_plan_completion_remains_unchanged(queue):
    job=queue.enqueue(task_id="real-plan",kind=JobKind.PLAN)
    active=queue.claim_specific(job.id)
    terminal=queue.complete(active,{"proposal_persisted":True})
    assert terminal.status is JobStatus.COMPLETED
