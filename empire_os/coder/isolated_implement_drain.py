"""Existing Empire Coder IMPLEMENT queue -> isolated Codex proposal consumer.

The only terminal success is AWAITING_APPROVAL, never live implementation.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
import re
import subprocess
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
        or result.get("test_isolation") != "BWRAP_NO_NETWORK_READ_ONLY_SOURCE"
        or result.get("model_filesystem_isolation") != "BWRAP_CLONE_AND_READONLY_AUTH"
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
    patch = expected.read_bytes()
    if hashlib.sha256(patch).hexdigest() != result["proposal_sha256"]:
        return False
    source_commit = str(result.get("source_commit") or "")
    if not re.fullmatch(r"[a-f0-9]{40}", source_commit):
        return False
    try:
        current = subprocess.run(
            ("git", "rev-parse", "HEAD"), cwd=root,
            check=False, capture_output=True, text=True, timeout=15,
        )
        if current.returncode or current.stdout.strip() != source_commit:
            return False
        # Independent patch review: don't trust the model or its tool's
        # changed_paths claim. Git must parse the patch and report EXACT
        # permitted files before a founder can even review it.
        numstat = subprocess.run(
            ("git", "apply", "--numstat", "-z", "-"), cwd=root,
            input=patch, check=False, capture_output=True, timeout=20,
        )
        if numstat.returncode:
            return False
        actual_paths = {
            row.rsplit(b"\t", 1)[-1].decode("utf-8", errors="strict")
            for row in numstat.stdout.split(b"\x00")
            if row
        }
        if actual_paths != set(result["changed_paths"]):
            return False
        for rel in actual_paths:
            target = (root / rel)
            if (
                target.is_symlink()
                or not target.resolve().is_relative_to(root)
                or not (root / rel).parent.resolve().is_relative_to(root)
            ):
                return False
        if any(
            token in patch for token in (
                b"new file mode 120000",
                b"old mode 120000",
                b"new mode 120000",
                b"GIT binary patch",
                b"rename from ",
                b"rename to ",
            )
        ):
            return False
        check = subprocess.run(
            ("git", "apply", "--check", "-"), cwd=root,
            input=patch, check=False, capture_output=True, timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError, ValueError):
        return False
    return check.returncode == 0


TRANSIENT_CANDIDATE_REASONS = frozenset({
    "execution_lease_conflict",
    "codex_model_timeout",
    "isolated_clone_failed",
})


def _requeue_transient(
    queue: LocalJobQueue, job: CoderJob, reason: str,
) -> CoderJob | None:
    if reason not in TRANSIENT_CANDIDATE_REASONS:
        return None
    if job.attempts >= 3:
        return None
    return queue.retry(
        job, reason,
        delay_seconds=min(300, 30 * (2 ** max(0, job.attempts - 1))),
        max_attempts=3,
    )


def _write_health_receipt(
    root: Path, queue: LocalJobQueue, result: dict[str, Any],
) -> None:
    """Small, non-PII readback for the original Coder/Hermes department."""
    pending = [
        j for j in queue.list_pending(kind=JobKind.IMPLEMENT)
        if j.payload.get("execution_mode") == ISOLATED_CANDIDATE_MODE
    ]
    approval_dir = queue.awaiting_approval
    event = {
        **result,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "pending_isolated_implement_count": len(pending),
        "total_awaiting_approval_count": sum(
            1 for _ in approval_dir.glob("*.json")
        ),
        "health_status": (
            "DEGRADED" if result["failed_count"] else
            "RETRY_PENDING" if result["retried_count"] else
            "FOUNDER_REVIEW_PENDING" if result["awaiting_approval_count"] else
            "IDLE"
        ),
    }
    path = root / "runtime/execution_plane/coder_implement_consumer_latest.json"
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(event, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(temp, 0o600)
    os.replace(temp, path)


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
    retried: list[dict[str, str]] = []
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
                    "source_commit": result["source_commit"],
                    "test_isolation": result["test_isolation"],
                    "model_filesystem_isolation": result["model_filesystem_isolation"],
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
                deferred = _requeue_transient(queue, claimed, reason)
                if deferred is not None:
                    retried.append({
                        "job_id": deferred.id,
                        "reason": reason,
                        "next_attempt_after_utc": str(deferred.retry_after),
                    })
                else:
                    terminal = queue.fail(
                        claimed, reason,
                        result={
                            "candidate_status": str(result.get("status") or "UNKNOWN"),
                            "task_completed": False, "production_mutation": False,
                            "founder_release_required": True,
                        },
                    )
                    failed.append({"job_id": terminal.id, "reason": reason})
        except (TimeoutError, ConnectionError) as exc:
            reason = "codex_model_timeout"
            deferred = _requeue_transient(queue, claimed, reason)
            if deferred is not None:
                retried.append({
                    "job_id": deferred.id, "reason": reason,
                    "next_attempt_after_utc": str(deferred.retry_after),
                })
            else:
                terminal = queue.fail(
                    claimed, "bounded_retry_exhausted:" + type(exc).__name__,
                    result={
                        "candidate_status": "FAILED", "task_completed": False,
                        "production_mutation": False, "founder_release_required": True,
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

    summary = {
        "schema_version": "empire.coder.isolated-implement-consumer.v1",
        "status": "AVAILABLE", "processed_count": processed,
        "awaiting_approval_count": len(ready), "failed_count": len(failed),
        "retried_count": len(retried), "retried": retried,
        "awaiting_approval": ready, "failed": failed,
        "implementation_verified": False,
        "production_mutation": False, "external_send": False,
        "payment_action": False, "founder_release_gate_preserved": True,
    }
    _write_health_receipt(root, queue, summary)
    return summary
