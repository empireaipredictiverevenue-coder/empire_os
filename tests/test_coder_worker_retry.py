from empire_os.coder.jobs import CoderJob, JobKind, JobStatus
from empire_os.coder.worker import CoderTaskWorker


class DummyQueue:
    def __init__(self, job):
        self.job = job
        self.failed = None
        self.retried = None

    def recover_stale(self, **kwargs):
        return []

    def quarantine_exhausted(self, **kwargs):
        return []

    def claim_next(self, **kwargs):
        job, self.job = self.job, None
        return job

    def heartbeat(self, job, **kwargs):
        return job

    def fail(self, job, error):
        job.status = JobStatus.FAILED
        job.error = error
        self.failed = job
        return job

    def retry(self, job, error, **kwargs):
        job.status = JobStatus.PENDING
        job.error = error
        self.retried = job
        return job

    def complete(self, job, result):
        job.status = JobStatus.COMPLETED
        job.result = result
        return job


def _job(attempts):
    return CoderJob(
        id="coder_job_test",
        task_id="coder_task_test",
        kind=JobKind.PLAN,
        attempts=attempts,
        status=JobStatus.RUNNING,
    )


def test_transient_failure_is_quarantined_after_max_attempts(monkeypatch):
    queue = DummyQueue(_job(3))
    worker = CoderTaskWorker(object(), queue, max_attempts=3)
    monkeypatch.setattr(
        worker,
        "_process",
        lambda job: (_ for _ in ()).throw(
            RuntimeError("ollama_request_failed:TimeoutError")
        ),
    )

    result = worker.run_once()

    assert result.status is JobStatus.FAILED
    assert queue.failed is result
    assert queue.retried is None
    assert "max_attempts_exhausted" in result.error


def test_transient_failure_retries_before_max_attempts(monkeypatch):
    queue = DummyQueue(_job(1))
    worker = CoderTaskWorker(object(), queue, max_attempts=3)
    monkeypatch.setattr(
        worker,
        "_process",
        lambda job: (_ for _ in ()).throw(
            TimeoutError("temporary timeout")
        ),
    )

    result = worker.run_once()

    assert result.status is JobStatus.PENDING
    assert queue.retried is result
    assert queue.failed is None
