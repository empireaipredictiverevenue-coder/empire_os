"""Isolated structured-patch runner for Empire Coder.

The local model never edits the live EmpireOS working tree. A bounded job runs
in a disposable clone under the central execution lease, applies at most the
validated structured patch, runs focused tests, and publishes only a proposal
branch for independent verification.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Mapping

from empire_os.coder import EmpireCoder
from empire_os.coder.models import VerificationVerdict
from empire_os.execution_lease import ExecutionLeaseError, ExecutionLeaseManager


JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
DEFAULT_BRANCH = "feature/revenue-intelligence-v2"
DEFAULT_WORK_ROOT = Path("/var/tmp/empire-coder-sandbox")


class EmpireCoderSandboxError(RuntimeError):
    pass


@dataclass(frozen=True)
class EmpireCoderSandboxJob:
    job_id: str
    objective: str
    department: str
    capability: str
    allowed_paths: tuple[str, ...]
    lease_resources: tuple[str, ...]
    pytest_targets: tuple[str, ...] = ()
    base_branch: str = DEFAULT_BRANCH
    max_runtime_seconds: int = 900

    def validate(self) -> None:
        if not JOB_ID_RE.fullmatch(self.job_id):
            raise EmpireCoderSandboxError("invalid job_id")
        if not self.objective.strip():
            raise EmpireCoderSandboxError("objective required")
        if len(self.objective) > 20_000:
            raise EmpireCoderSandboxError("objective too long")
        if self.base_branch != DEFAULT_BRANCH:
            raise EmpireCoderSandboxError("base branch is pinned")
        if not self.allowed_paths:
            raise EmpireCoderSandboxError("allowed_paths required")
        if not self.lease_resources:
            raise EmpireCoderSandboxError("lease_resources required")
        for target in self.pytest_targets:
            if not target.startswith("tests/") or ".py" not in target:
                raise EmpireCoderSandboxError("invalid pytest target")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _run(
    argv: list[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(cwd),
        env=dict(env or os.environ),
        capture_output=True,
        text=True,
        timeout=max(1, timeout),
        check=False,
    )


def _path_allowed(path: str, allowed: tuple[str, ...]) -> bool:
    clean = str(path or "").strip().replace("\\", "/").lstrip("./")
    for raw in allowed:
        prefix = str(raw or "").strip().replace("\\", "/").lstrip("./").rstrip("/")
        if prefix and (clean == prefix or clean.startswith(prefix + "/")):
            return True
    return False


def _changed_paths(clone: Path) -> list[str]:
    status = _run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=clone,
    )
    if status.returncode != 0:
        raise EmpireCoderSandboxError("git status failed")
    changed: list[str] = []
    for line in status.stdout.splitlines():
        if len(line) < 4:
            continue
        value = line[3:].strip()
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        if value and not value.startswith("runtime/"):
            changed.append(value)
    return sorted(dict.fromkeys(changed))


def run_empire_coder_sandbox_job(
    repo_root: str | Path,
    job: EmpireCoderSandboxJob,
    *,
    lease_manager: ExecutionLeaseManager | None = None,
    work_root: str | Path = DEFAULT_WORK_ROOT,
) -> dict[str, Any]:
    job.validate()
    root = Path(repo_root).resolve()
    work_base = Path(work_root)
    work_base.mkdir(parents=True, exist_ok=True)
    clone = work_base / job.job_id
    shutil.rmtree(clone, ignore_errors=True)

    manager = lease_manager or ExecutionLeaseManager(
        root / "runtime/execution_plane"
    )
    try:
        lease = manager.acquire(
            owner="empire_coder",
            job_id=job.job_id,
            resources=job.lease_resources,
            ttl_seconds=job.max_runtime_seconds + 300,
        )
    except ExecutionLeaseError as exc:
        raise EmpireCoderSandboxError(str(exc)) from exc

    result: dict[str, Any] = {
        "schema_version": "empire.empire-coder-sandbox-result.v1",
        "job_id": job.job_id,
        "status": "FAILED",
        "lease_id": lease.lease_id,
        "changed_paths": [],
        "proposal_branch": None,
        "verification": None,
        "production_mutation": False,
        "production_deploy": False,
        "external_send": False,
        "payment_action": False,
        "revenue_recognition": False,
        "execution_authority": "none",
    }

    try:
        cloned = _run(
            [
                "git", "clone", "--no-hardlinks", "--single-branch",
                "--branch", job.base_branch, str(root), str(clone),
            ],
            cwd=work_base,
            timeout=180,
        )
        if cloned.returncode != 0:
            result["status"] = "CLONE_FAILED"
            result["error_tail"] = (cloned.stderr or cloned.stdout)[-3000:]
            return result

        coder = EmpireCoder(
            clone,
            runtime_root=clone / "runtime/coder",
        )
        task = coder.create_task(job.objective)
        context = coder.build_context(
            task.id,
            terms=(job.department, job.capability),
            budget_chars=8000,
        )
        try:
            candidate = coder.propose_structured_patch(
                task.id,
                (
                    "Implement exactly one smallest safe DEVELOPMENT patch for "
                    "the task objective. Return only the machine-checkable "
                    "structured patch requested by Empire Coder. Do not touch "
                    "deployment, services, production databases, outbound, "
                    "credentials, payments, funds or revenue truth.\n\nTASK:\n"
                    + job.objective
                ),
                context,
            )
        except Exception as exc:
            result["status"] = "NO_IMPLEMENTATION"
            result["reason"] = f"{type(exc).__name__}:{exc}"[:1000]
            return result

        proposal = candidate.proposal
        result["candidate"] = {
            "eligible": candidate.eligible,
            "target_path": proposal.target_path,
            "operation": proposal.operation.value,
            "validation": candidate.validation.as_dict(),
        }
        if not candidate.eligible:
            result["status"] = "NO_IMPLEMENTATION"
            return result
        if not _path_allowed(proposal.target_path, job.allowed_paths):
            result["status"] = "PATH_POLICY_FAILED"
            result["rejected_paths"] = [proposal.target_path]
            return result

        coder.apply_structured_patch(task.id, candidate)
        changed = _changed_paths(clone)
        rejected = [
            path for path in changed
            if not _path_allowed(path, job.allowed_paths)
        ]
        result["changed_paths"] = changed
        if rejected:
            result["status"] = "PATH_POLICY_FAILED"
            result["rejected_paths"] = rejected
            return result
        if not changed:
            result["status"] = "NO_IMPLEMENTATION"
            result["reason"] = "structured_patch_made_no_repository_change"
            return result

        tests = tuple(dict.fromkeys(
            tuple(proposal.expected_tests) + tuple(job.pytest_targets)
        ))
        checks: list[dict[str, Any]] = []
        if tests:
            env = {
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                "PYTHONPATH": str(clone),
                "HOME": "/var/tmp",
            }
            check = _run(
                [
                    str(root / ".venv/bin/python"),
                    "-m", "pytest", "-q", *tests,
                ],
                cwd=clone,
                env=env,
                timeout=min(max(job.max_runtime_seconds, 120), 1200),
            )
            checks.append({
                "kind": "pytest",
                "targets": list(tests),
                "returncode": check.returncode,
                "output_tail": ((check.stdout or "") + "\n" + (check.stderr or ""))[-5000:],
            })
        passed = all(row["returncode"] == 0 for row in checks)
        if not checks:
            passed = True
        result["verification"] = {
            "passed": passed,
            "checks": checks,
        }
        if not passed:
            result["status"] = "VERIFICATION_FAILED"
            return result

        proposal_branch = f"empire-coder/job-{job.job_id}"
        switched = _run(
            ["git", "switch", "-C", proposal_branch],
            cwd=clone,
        )
        if switched.returncode != 0:
            result["status"] = "COMMIT_FAILED"
            return result
        for path in changed:
            added = _run(["git", "add", "--", path], cwd=clone)
            if added.returncode != 0:
                result["status"] = "COMMIT_FAILED"
                return result
        committed = _run(
            [
                "git", "-c", "user.name=Empire Coder",
                "-c", "user.email=coder@empire-ai.co.uk",
                "commit", "-m", f"Empire Coder proposal: {job.job_id}",
            ],
            cwd=clone,
        )
        if committed.returncode != 0:
            result["status"] = "COMMIT_FAILED"
            result["error_tail"] = (committed.stderr or committed.stdout)[-3000:]
            return result
        sha = _run(["git", "rev-parse", "HEAD"], cwd=clone).stdout.strip()

        remote = _run(
            ["git", "remote", "get-url", "origin"],
            cwd=root,
        ).stdout.strip()
        if not remote:
            result["status"] = "PUSH_FAILED"
            result["reason"] = "origin_remote_unavailable"
            return result
        _run(["git", "remote", "set-url", "origin", remote], cwd=clone)
        pushed = _run(
            ["git", "push", "origin", f"HEAD:refs/heads/{proposal_branch}"],
            cwd=clone,
            timeout=180,
        )
        if pushed.returncode != 0:
            result["status"] = "PUSH_FAILED"
            result["error_tail"] = (pushed.stderr or pushed.stdout)[-3000:]
            return result

        result["proposal_branch"] = proposal_branch
        result["proposal_commit"] = sha
        result["status"] = "PROPOSAL_READY"
        return result
    finally:
        manager.release(lease.lease_id)
        shutil.rmtree(clone, ignore_errors=True)