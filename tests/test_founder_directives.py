from pathlib import Path
from types import SimpleNamespace

from empire_os.coder.jobs import JobStatus

from empire_os.founder_directives import (
    FounderDirectiveStore,
    classify_authority,
    classify_category,
)
from empire_os.founder_directive_planner import plan_captured_directives


def test_directive_is_deduplicated(tmp_path):
    store = FounderDirectiveStore(tmp_path)
    first, created = store.ingest(
        "Build the SEO product into the existing business.",
        source="founder_chat",
    )
    second, created_again = store.ingest(
        " build   the SEO product into the existing business ",
        source="founder_chat",
    )
    assert created is True
    assert created_again is False
    assert first.id == second.id
    assert store.summary()["directive_count"] == 1


def test_irreversible_authority_is_founder_gate():
    authority, reasons = classify_authority(
        "Transfer USDT funds and accept the binding contract."
    )
    assert authority == "founder_gate"
    assert "fund_movement" in reasons
    assert "binding_commercial_terms" in reasons


def test_reversible_feature_is_auto_planned():
    authority, reasons = classify_authority(
        "Connect the CRM to the SEO product for backlinks and mentions."
    )
    assert authority == "internal_plan"
    assert reasons == ()
    assert classify_category(
        "Connect the CRM to the SEO product for backlinks and mentions."
    ) == "search"


class FakeCoder:
    def __init__(self, *args, **kwargs):
        self.created = []

    def create_task(self, objective):
        self.created.append(objective)
        return SimpleNamespace(id="coder_task_1")


class FakeQueue:
    jobs = {}

    def __init__(self, *args, **kwargs):
        pass

    def enqueue(self, **kwargs):
        job = SimpleNamespace(
            id="coder_job_1",
            status=SimpleNamespace(value="PENDING"),
            result={},
            error=None,
        )
        self.jobs[job.id] = job
        return job

    def get(self, job_id):
        return self.jobs[job_id]


def test_planner_queues_plan_not_implementation(tmp_path):
    store = FounderDirectiveStore(tmp_path)
    directive, _ = store.ingest(
        "Add Revenue Pulse results to the Founder Console.",
        source="founder_chat",
    )
    result = plan_captured_directives(
        tmp_path,
        coder_factory=FakeCoder,
        queue_factory=FakeQueue,
    )
    row = store.get(directive.id)
    assert result["queued"] == 1
    assert row.status == "planning"
    assert row.coder_job_id == "coder_job_1"
    assert result["automatic_production_execution"] is False


def test_failed_plan_is_not_immediately_requeued_same_cycle(tmp_path):
    store = FounderDirectiveStore(tmp_path)
    directive, _ = store.ingest(
        "Build internal revenue telemetry.",
        source="founder_chat",
    )
    store.update(
        directive.id,
        status="planning",
        coder_task_id="task_old",
        coder_job_id="job_old",
    )

    class FailedQueue(FakeQueue):
        jobs = {
            "job_old": SimpleNamespace(
                id="job_old",
                status=JobStatus.FAILED,
                result={},
                error="timeout",
            )
        }

    result = plan_captured_directives(
        tmp_path,
        coder_factory=FakeCoder,
        queue_factory=FailedQueue,
    )
    row = store.get(directive.id)

    assert result["plan_failures"] == 1
    assert result["queued"] == 0
    assert row.status == "plan_failed"
    assert row.plan_result["retry_count"] == 1
    assert row.plan_result["retry_after"]
    assert result["retry_policy"]["immediate_same_cycle_retry"] is False
