"""Governed EmpireOS Swarm V6.

Swarm V6 replaces the retired public/file-backed Swarm 3.0 execution model.
It continuously assigns deterministic VERIFY work across bounded specialist
lanes. It cannot deploy, send outreach, mutate production data, move funds,
accept terms, fulfil work, or recognize revenue.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from empire_os.coder import EmpireCoder
from empire_os.coder.jobs import JobKind, LocalJobQueue
from empire_os.coder.worker import CoderTaskWorker


@dataclass(frozen=True)
class SwarmLane:
    key: str
    role: str
    changed_files: tuple[str, ...]
    tests: tuple[str, ...]


LANES: tuple[SwarmLane, ...] = (
    SwarmLane(
        key="revenue_payments",
        role="Revenue / Payments specialist",
        changed_files=(
            "empire_os/commercial_terms_materializer.py",
            "empire_os/commercial_terms_readiness.py",
            "empire_os/bsc_payment_evidence.py",
            "empire_os/first_revenue_proof.py",
        ),
        tests=(
            "tests/test_commercial_terms_materializer.py",
            "tests/test_commercial_terms_readiness.py",
            "tests/test_bsc_payment_evidence.py",
            "tests/test_first_revenue_proof.py",
        ),
    ),
    SwarmLane(
        key="closer_outreach",
        role="Closer / Outreach specialist",
        changed_files=(
            "empire_os/closer_reply_worker.py",
            "empire_os/closer_reply_draft.py",
            "empire_os/buyer_capacity_intake.py",
            "empire_os/outbound_role_transport.py",
            "empire_os/gtm_swarm_v6.py",
            "empire_os/gtm_offer_strategy.py",
        ),
        tests=(
            "tests/test_closer_reply_worker.py",
            "tests/test_closer_reply_draft.py",
            "tests/test_buyer_capacity_intake.py",
            "tests/test_outbound_role_transport.py",
            "tests/test_gtm_swarm_v6.py",
            "tests/test_gtm_offer_strategy.py",
        ),
    ),
    SwarmLane(
        key="growth_conversion",
        role="Growth / Conversion specialist",
        changed_files=(
            "empire_os/conversion_intelligence.py",
            "empire_os/conversion_runtime.py",
            "empire_os/advertising_landing_feedback.py",
            "empire_os/experiment_business_impact.py",
        ),
        tests=(
            "tests/test_conversion_intelligence.py",
            "tests/test_conversion_runtime.py",
            "tests/test_advertising_landing_feedback.py",
            "tests/test_experiment_business_impact.py",
        ),
    ),
    SwarmLane(
        key="search_opportunity",
        role="Search / Opportunity specialist",
        changed_files=(
            "empire_os/search_intelligence/attribution.py",
            "empire_os/search_intelligence/attribution_review.py",
            "empire_os/search_intelligence/scoring.py",
            "empire_os/revenue_exchange.py",
        ),
        tests=(
            "tests/search_intelligence/test_attribution.py",
            "tests/search_intelligence/test_attribution_review.py",
            "tests/search_intelligence/test_scoring.py",
            "tests/test_revenue_exchange.py",
        ),
    ),
    SwarmLane(
        key="platform_saas",
        role="Platform / SaaS specialist",
        changed_files=(
            "empire_os/saas_readiness.py",
            "empire_os/saas_usage_billing.py",
            "empire_os/enterprise_readiness.py",
            "empire_os/enterprise_remediation.py",
        ),
        tests=(
            "tests/test_saas_readiness.py",
            "tests/test_saas_usage_billing.py",
            "tests/test_enterprise_review.py",
            "tests/test_enterprise_remediation.py",
        ),
    ),
    SwarmLane(
        key="integration_qa",
        role="Integration / QA specialist",
        changed_files=(
            "empire_os/astra_dispatcher.py",
            "empire_os/founder_dashboard.py",
            "empire_os/circuit_breaker.py",
        ),
        tests=(
            "tests/test_astra_dispatcher.py",
            "tests/test_founder_dashboard.py",
            "tests/test_circuit_breaker.py",
        ),
    ),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _count_jobs(queue: LocalJobQueue) -> dict[str, int]:
    return {
        "pending": len(tuple(queue.pending.glob("coder_job_*.json"))),
        "running": len(tuple(queue.running.glob("coder_job_*.json"))),
        "completed": len(tuple(queue.completed.glob("coder_job_*.json"))),
        "failed": len(tuple(queue.failed.glob("coder_job_*.json"))),
    }


def _worker_once(
    workspace: Path,
    runtime_root: Path,
) -> dict[str, Any]:
    coder = EmpireCoder(workspace, runtime_root=runtime_root)
    queue = LocalJobQueue(workspace, runtime_root=runtime_root)
    job = CoderTaskWorker(coder, queue).run_once()
    if job is None:
        return {"status": "idle"}
    result = job.result if isinstance(job.result, dict) else {}
    verification = (
        result.get("verification")
        if isinstance(result.get("verification"), dict)
        else {}
    )
    return {
        "job_id": job.id,
        "task_id": job.task_id,
        "status": job.status.value,
        "error": job.error,
        "verdict": verification.get("verdict"),
        "model_inference": result.get("model_inference"),
        "production_mutation": result.get("production_mutation"),
    }


def run_swarm_cycle(
    workspace: str | Path = "/srv/empire_os",
    *,
    runtime_root: str | Path | None = None,
    max_workers: int = 3,
    execute_verify: bool = True,
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    runtime = (
        Path(runtime_root).resolve()
        if runtime_root is not None
        else root / "runtime" / "coder"
    )
    coder = EmpireCoder(root, runtime_root=runtime)
    queue = LocalJobQueue(root, runtime_root=runtime)
    before = _count_jobs(queue)

    queued: list[dict[str, Any]] = []
    if before["pending"] == 0 and before["running"] == 0:
        for lane in LANES:
            task = coder.create_task(
                (
                    f"Swarm V6 lane {lane.key}: deterministically verify "
                    f"{lane.role} against the current Blueprint and launch "
                    "checkpoint. Report repository evidence only. Do not "
                    "mutate production."
                ),
                blueprint_path="docs/BLUEPRINT_V6.md",
            )
            job = queue.enqueue(
                task_id=task.id,
                kind=JobKind.VERIFY,
                payload={
                    "swarm_lane": lane.key,
                    "swarm_role": lane.role,
                    "changed_files": list(lane.changed_files),
                    "tests": list(lane.tests),
                },
            )
            queued.append(
                {
                    "lane": lane.key,
                    "role": lane.role,
                    "task_id": task.id,
                    "job_id": job.id,
                }
            )

    executions: list[dict[str, Any]] = []
    if execute_verify:
        worker_count = max(1, min(int(max_workers), 6))
        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            futures = [
                pool.submit(_worker_once, root, runtime)
                for _ in range(len(LANES))
            ]
            for future in as_completed(futures):
                executions.append(future.result())

    after = _count_jobs(queue)
    payload = {
        "schema_version": "empire.swarm.v6",
        "observed_at": _now(),
        "mode": "INTERNAL_VERIFY",
        "commander": "astra",
        "lanes": [asdict(lane) for lane in LANES],
        "queued": queued,
        "executions": executions,
        "queue_before": before,
        "queue_after": after,
        "authority": {
            "production_mutation": False,
            "outbound_send": False,
            "commercial_terms_acceptance": False,
            "fund_movement": False,
            "payment_confirmation": False,
            "fulfilment": False,
            "revenue_recognition": False,
            "authority_expansion": False,
        },
    }
    out = root / "runtime" / "swarm_v6" / "latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(out)
    return payload
