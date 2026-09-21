"""Continuous Empire Coder supervisor.

Keeps useful development work flowing from Founder Directives:
plan in parallel -> implement one-at-a-time -> deterministic verification ->
explicit-path git commit -> next eligible directive.

Production execution remains outside this supervisor.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping

from empire_os.coder import EmpireCoder
from empire_os.coder.jobs import JobKind, JobStatus, LocalJobQueue
from empire_os.founder_directive_planner import plan_captured_directives
from empire_os.founder_directives import FounderDirectiveStore

PASS_VERDICTS = {"PASS", "PASS_WITH_WARNINGS"}
PROTECTED_ROOTS = frozenset({"recovery", "toop"})


def _is_protected_repo_path(value: str) -> bool:
    raw = str(value or "").strip().replace("\\", "/").rstrip("/")
    return any(
        raw == root or raw.startswith(root + "/")
        for root in PROTECTED_ROOTS
    )


def _active_jobs(queue: LocalJobQueue, kind: JobKind | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for directory in (queue.pending, queue.running):
        for path in sorted(directory.glob("*.json")):
            try:
                row = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if kind is not None and row.get("kind") != kind.value:
                continue
            rows.append(row)
    return rows


def _safe_repo_path(value: Any) -> str:
    raw = str(value or "").strip().replace("\\", "/")
    path = Path(raw)
    if not raw or path.is_absolute() or ".." in path.parts:
        raise ValueError("invalid candidate target path")
    if _is_protected_repo_path(raw):
        raise ValueError("protected candidate target path")
    return raw


def _nonprotected_dirty(
    root: Path,
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> list[str]:
    result = runner(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        return ["git_status_failed"]
    dirty: list[str] = []
    for line in (result.stdout or "").splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        if _is_protected_repo_path(path):
            continue
        dirty.append(path)
    return dirty


def _commit_verified_candidate(
    root: Path,
    title: str,
    result: Mapping[str, Any],
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    if not result.get("applied"):
        return {"committed": False, "reason": "candidate_not_applied"}
    verification = result.get("verification")
    verification = verification if isinstance(verification, Mapping) else {}
    verdict = str(verification.get("verdict") or "")
    if verdict not in PASS_VERDICTS:
        return {
            "committed": False,
            "reason": "verification_not_passed",
            "verdict": verdict or None,
        }
    target = _safe_repo_path(result.get("target_path"))

    check = runner(
        ["git", "diff", "--check", "--", target],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if check.returncode != 0:
        return {
            "committed": False,
            "reason": "git_diff_check_failed",
            "detail": (check.stderr or check.stdout or "")[-1000:],
        }

    status = runner(
        ["git", "status", "--short", "--", target],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if status.returncode != 0:
        return {"committed": False, "reason": "git_status_failed"}
    if not (status.stdout or "").strip():
        return {"committed": False, "reason": "no_candidate_diff"}

    add = runner(
        ["git", "add", "--", target],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if add.returncode != 0:
        return {"committed": False, "reason": "git_add_failed"}

    message = "feat(coder): " + " ".join(str(title or "implement directive").split())[:72]
    commit = runner(
        ["git", "commit", "-m", message, "--", target],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if commit.returncode != 0:
        return {
            "committed": False,
            "reason": "git_commit_failed",
            "detail": (commit.stderr or commit.stdout or "")[-1500:],
        }
    head = runner(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    return {
        "committed": True,
        "target_path": target,
        "commit_sha": (head.stdout or "").strip() or None,
        "pushed": False,
        "production_mutation": False,
    }


def run_coder_supervisor(
    repo_root: str | Path,
    *,
    plan_limit: int = 6,
    coder_factory: Callable[..., Any] = EmpireCoder,
    queue_factory: Callable[..., Any] = LocalJobQueue,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    store = FounderDirectiveStore(root)
    coder_root = root / "runtime" / "coder"
    coder = coder_factory(root, runtime_root=coder_root)
    queue = queue_factory(root, runtime_root=coder_root)

    planning = plan_captured_directives(
        root,
        limit=plan_limit,
        coder_factory=coder_factory,
        queue_factory=queue_factory,
    )

    implementation_reconciled = 0
    implementation_failed = 0
    commits = 0

    for row in store.list(statuses={"implementing"}):
        if not row.implementation_job_id:
            continue
        try:
            job = queue.get(row.implementation_job_id)
        except Exception:
            continue
        if job.status is JobStatus.COMPLETED:
            result = dict(job.result or {})
            commit = _commit_verified_candidate(
                root,
                row.title,
                result,
                runner=runner,
            )
            next_status = "implemented" if commit.get("committed") else "implementation_failed"
            store.update(
                row.id,
                status=next_status,
                implementation_result={
                    **result,
                    "commit": commit,
                },
                commit_sha=commit.get("commit_sha"),
            )
            implementation_reconciled += 1
            commits += int(bool(commit.get("committed")))
        elif job.status is JobStatus.FAILED:
            store.update(
                row.id,
                status="implementation_failed",
                implementation_result={
                    "error": str(job.error or "implementation_failed")[:2000]
                },
            )
            implementation_failed += 1

    active_implement = _active_jobs(queue, JobKind.IMPLEMENT)
    queued_implementation = 0
    blocked_dirty = _nonprotected_dirty(root, runner=runner)

    if not active_implement and not blocked_dirty:
        ready = store.list(statuses={"implementation_ready"})
        if ready:
            row = ready[0]
            task = coder.create_task(
                (
                    "Implement this already-planned Founder Directive as the "
                    "smallest safe DEVELOPMENT patch inside the existing EmpireOS "
                    "architecture. Reuse existing modules; do not create duplicate "
                    "systems. Include focused tests/observability where the narrow "
                    "patch supports them. Do not deploy, touch production databases, "
                    "send outbound, accept terms, move funds, recognize revenue, "
                    "edit protected paths, or widen authority. Directive: "
                    + row.text
                )
            )
            job = queue.enqueue(
                task_id=task.id,
                kind=JobKind.IMPLEMENT,
                priority=row.priority,
                payload={
                    "terms": [
                        row.category,
                        "founder",
                        "directive",
                        "implementation",
                        "tests",
                        "daily_results",
                    ],
                    "budget_chars": 8000,
                    "directive_id": row.id,
                    "authority": row.authority,
                },
            )
            store.update(
                row.id,
                status="implementing",
                implementation_task_id=task.id,
                implementation_job_id=job.id,
                implementation_result={},
            )
            queued_implementation = 1

    snapshot = store.summary()
    return {
        "ok": True,
        "planning": planning,
        "implementation_reconciled": implementation_reconciled,
        "implementation_failed": implementation_failed,
        "commits_created": commits,
        "queued_implementation": queued_implementation,
        "active_implementation_jobs": len(_active_jobs(queue, JobKind.IMPLEMENT)),
        "active_total_jobs": len(_active_jobs(queue)),
        "repo_blocked_by_nonprotected_dirty": blocked_dirty,
        "directive_status_counts": snapshot["status_counts"],
        "founder_gate_count": snapshot["founder_gate_count"],
        "production_execution": False,
        "execution_mode": "OBSERVE",
    }
