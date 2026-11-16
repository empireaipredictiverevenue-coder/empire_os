"""Existing Empire Coder IMPLEMENT queue -> isolated Codex proposal consumer.

The only terminal success is AWAITING_APPROVAL, never live implementation.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import threading
from typing import Any, Callable

from empire_os.coder.jobs import CoderJob, JobKind, JobStatus, LocalJobQueue
from empire_os.coder.plan_promotion import (
    ISOLATED_CANDIDATE_MODE, _contract_hash, _promotion_key,
    _validate_contract, _validate_governed_intake,
)
from empire_os.empire_coder_sandbox_runner import (
    EmpireCoderSandboxJob, run_empire_coder_codex_local_candidate,
)


def _scoped_candidate(
    root: Path, queue: LocalJobQueue, job: CoderJob,
) -> tuple[EmpireCoderSandboxJob | None, str | None]:
    payload = job.payload
    if (
        job.kind is not JobKind.IMPLEMENT
        or payload.get("execution_mode") != ISOLATED_CANDIDATE_MODE
        or payload.get("execution_authority") != "none"
        or payload.get("founder_release_required") is not True
    ):
        return None, "not_approval_gated_implementation"
    try:
        plan = queue.get(str(payload.get("source_plan_job_id") or ""))
    except Exception:
        return None, "original_completed_plan_missing"
    if (
        plan.kind is not JobKind.PLAN or plan.status is not JobStatus.COMPLETED
        or plan.task_id != job.task_id
        or plan.result.get("proposal_persisted") is not True
    ):
        return None, "source_plan_not_completed"
    contract = plan.payload.get("promotion_contract")
    if not isinstance(contract, dict):
        return None, "source_implementation_contract_missing"
    kind, blockers = _validate_contract(contract)
    if kind is not JobKind.IMPLEMENT or blockers:
        return None, "invalid_source_implementation_contract"
    if not _validate_governed_intake(root, plan.as_dict(), contract):
        return None, "original_execution_authority_mismatch"
    if payload.get("plan_promotion_key") != _promotion_key(plan.id, contract):
        return None, "promotion_key_mismatch"
    for key in ("allowed_paths", "lease_resources", "required_tests"):
        if payload.get(key) != contract.get(key):
            return None, f"{key}_scope_mismatch"
    if (
        payload.get("execution_plane_request_id") != contract.get("execution_plane_request_id")
        or payload.get("base_branch") != contract.get("base_branch")
        or payload.get("max_runtime_seconds") != contract.get("max_runtime_seconds")
        or payload.get("source_ref") != plan.payload.get("governed_intake_source_ref")
    ):
        return None, "source_runtime_or_identity_mismatch"
    request_id = contract["execution_plane_request_id"]
    receipt = (
        root / "runtime/execution_plane/coder_plan_intake" / f"{request_id}.json"
    )
    try:
        saved = json.loads(receipt.read_text(encoding="utf-8"))
        if (
            saved.get("plan_job_id") != plan.id
            or saved.get("task_id") != job.task_id
            or saved.get("contract_sha256") != _contract_hash(contract)
            or not isinstance(saved.get("objective"), str)
            or not saved["objective"].strip()
        ):
            return None, "governed_request_receipt_mismatch"
        sandbox = EmpireCoderSandboxJob(
            job_id=job.id, objective=saved["objective"],
            department="engineering", capability="backend_code",
            allowed_paths=tuple(contract["allowed_paths"]),
            lease_resources=tuple(contract["lease_resources"]),
            pytest_targets=tuple(contract["required_tests"]),
            base_branch=contract["base_branch"],
            max_runtime_seconds=int(contract["max_runtime_seconds"]),
        )
        sandbox.validate()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return None, f"invalid_governed_request_or_sandbox:{type(exc).__name__}"
    return sandbox, None


def _candidate_verified(
    root: Path, candidate: EmpireCoderSandboxJob, result: dict[str, Any],
) -> bool:
    if (
        result.get("status") != "LOCAL_PROPOSAL_READY"
        or result.get("verification_passed") is not True
        or result.get("founder_gate_required") is not True
        or result.get("production_mutation") is not False
        or result.get("production_deploy") is not False
        or not isinstance(result.get("changed_paths"), list)
        or not result["changed_paths"]
        or not set(result["changed_paths"]).issubset(candidate.allowed_paths)
        or not result.get("proposal_patch")
        or not result.get("proposal_sha256")
    ):
        return False
    folder = (root / "runtime/execution_plane/coder_proposals").resolve()
    expected = folder / f"{candidate.job_id}.patch"
    proposed = Path(str(result["proposal_patch"]))
    if (
        expected.is_symlink() or not expected.resolve().is_relative_to(folder)
        or proposed.resolve() != expected.resolve() or not expected.is_file()
    ):
        return False
    return hashlib.sha256(expected.read_bytes()).hexdigest() == result["proposal_sha256"]


def drain_isolated_implement_jobs(
    repo_root: str | Path, *,
    max_jobs: int = 1,
    runtime_root: str | Path | None = None,
    candidate_runner: Callable[..., dict[str, Any]] = run_empire_coder_codex_local_candidate,
    heartbeat_seconds: int = 30,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    queue = LocalJobQueue(root, runtime_root=runtime_root)
    max_count = max(1, min(int(max_jobs), 2))
    processed = 0
    ready: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []
    for pending in queue.list_pending(kind=JobKind.IMPLEMENT):
        if processed >= max_count:
            break
        if pending.payload.get("execution_mode") != ISOLATED_CANDIDATE_MODE:
            continue
        scoped, reason = _scoped_candidate(root, queue, pending)
        lease_for = max(300, (scoped.max_runtime_seconds if scoped else 300) + 240)
        claimed = queue.claim_specific(
            pending.id, worker_id=f"isolated-codex:{os.getpid()}",
            lease_seconds=lease_for,
        )
        if claimed is None:
            continue
        processed += 1
        if (
            claimed.payload != pending.payload
            or claimed.task_id != pending.task_id
        ):
            reason = "request_changed_between_governed_preflight_and_claim"
            scoped = None
        if reason or scoped is None:
            bad = queue.fail(
                claimed, reason or "unverified_governed_request",
                result={
                    "candidate_status": "HELD_UNVERIFIED_REQUEST",
                    "task_completed": False, "production_mutation": False,
                    "founder_release_required": True,
                },
            )
            failed.append({"job_id": bad.id, "reason": reason or "unverified_governed_request"})
            continue
        stop = threading.Event()

        def beat() -> None:
            while not stop.wait(max(2, int(heartbeat_seconds))):
                try:
                    queue.heartbeat(claimed, lease_seconds=lease_for)
                except Exception:
                    return

        thread = threading.Thread(target=beat, daemon=True, name="isolated-coder-heartbeat")
        thread.start()
        try:
            result = candidate_runner(root, scoped)
            if not isinstance(result, dict):
                result = {"status": "HELD", "reason": "invalid_runner_result"}
            if _candidate_verified(root, scoped, result):
                packet = {
                    "candidate_status": "LOCAL_PROPOSAL_READY",
                    "candidate_verification_passed": True,
                    "candidate_changed_paths": list(result["changed_paths"]),
                    "proposal_patch": result["proposal_patch"],
                    "proposal_sha256": result["proposal_sha256"],
                    "implementation_verified": False,
                    "task_completed": False,
                    "founder_release_required": True,
                    "live_code_modified": False, "production_deploy": False,
                    "remote_push": False, "execution_authority": "none",
                }
                terminal = queue.hold_candidate_for_approval(claimed, packet)
                ready.append({"job_id": terminal.id, "status": terminal.status.value})
            else:
                reason = str(result.get("reason") or "candidate_artifact_not_verified")
                terminal = queue.fail(
                    claimed, reason,
                    result={
                        "candidate_status": str(result.get("status") or "UNKNOWN"),
                        "task_completed": False, "production_mutation": False,
                        "founder_release_required": True,
                    },
                )
                failed.append({"job_id": terminal.id, "reason": reason})
        except Exception as exc:
            reason = "isolated_candidate_failed:" + type(exc).__name__
            terminal = queue.fail(
                claimed, reason,
                result={
                    "candidate_status": "FAILED", "task_completed": False,
                    "production_mutation": False, "founder_release_required": True,
                },
            )
            failed.append({"job_id": terminal.id, "reason": reason})
        finally:
            stop.set()
            thread.join(timeout=2)

    return {
        "schema_version": "empire.coder.isolated-implement-consumer.v1",
        "status": "AVAILABLE", "processed_count": processed,
        "awaiting_approval_count": len(ready), "failed_count": len(failed),
        "awaiting_approval": ready, "failed": failed,
        "implementation_verified": False,
        "production_mutation": False, "external_send": False,
        "payment_action": False, "founder_release_gate_preserved": True,
    }
