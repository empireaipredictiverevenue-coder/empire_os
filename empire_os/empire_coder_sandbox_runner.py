"""Isolated structured-patch runner for Empire Coder.

The local model never edits the live EmpireOS working tree. A bounded job runs
in a disposable clone under the central execution lease, applies at most the
validated structured patch, runs focused tests, and publishes only a proposal
branch for independent verification.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
import fcntl
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import threading
import time
from typing import Any, Mapping

from empire_os.aider_builder import (
    AiderMutationRequest,
    run_aider_mutation,
)
from empire_os.aider_model_selector import select_usable_aider_model
from empire_os.builder_capabilities import (
    builder_capability_ready,
    builder_capability_snapshot,
)
from empire_os.coder import EmpireCoder
from empire_os.coder.context import ContextDocument
from empire_os.coder.models import VerificationVerdict
from empire_os.execution_lease import ExecutionLeaseError, ExecutionLeaseManager


JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
DEFAULT_BRANCH = "agent/data-cloud-wave4"
DATA_CLOUD_CLOSEOUT_BRANCH = DEFAULT_BRANCH
LEGACY_REVENUE_BRANCH = "feature/revenue-intelligence-v2"
ALLOWED_BASE_BRANCHES = frozenset({DEFAULT_BRANCH, LEGACY_REVENUE_BRANCH})
DEFAULT_WORK_ROOT = Path("/var/tmp/empire-coder-sandbox")


class EmpireCoderSandboxError(RuntimeError):
    pass


@contextmanager
def _structured_patch_runtime_env(
    enabled: bool,
    *,
    model: str | None = None,
):
    """Pin proven structured-patch work to the proven llama.cpp backend."""
    keys = (
        "EMPIRE_CODER_LLAMA_CPP_ENABLED",
        "EMPIRE_CODER_LLAMA_CPP_MODEL",
        "EMPIRE_CODER_LLAMA_CPP_CAPABILITY",
        "EMPIRE_CODER_LLAMA_CPP_ROLES",
        "EMPIRE_CODER_OLLAMA_TIMEOUT_SECONDS",
    )
    previous = {key: os.environ.get(key) for key in keys}
    try:
        if enabled:
            os.environ["EMPIRE_CODER_LLAMA_CPP_ENABLED"] = "true"
            os.environ["EMPIRE_CODER_LLAMA_CPP_MODEL"] = (
                str(model or "qwen2.5-coder:1.5b").strip()
                or "qwen2.5-coder:1.5b"
            )
            # The proven llama.cpp structured-patch endpoint currently
            # serves a 1.5B model. Successful small-format output is NOT
            # evidence that it can safely implement architecture/security
            # tasks (capability 3). Let the existing router choose an
            # eligible higher-capability local Ollama writer, or fail closed.
            os.environ["EMPIRE_CODER_LLAMA_CPP_CAPABILITY"] = "1"
            os.environ["EMPIRE_CODER_LLAMA_CPP_ROLES"] = (
                "planner,writer,verifier"
            )
            # Allow the genuinely capable local Ollama writer bounded time
            # to load/respond. Thirty seconds was too short for the larger
            # architecture writer; ninety seconds remains a firm HTTP cap.
            os.environ["EMPIRE_CODER_OLLAMA_TIMEOUT_SECONDS"] = "90"
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


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
        if self.base_branch not in ALLOWED_BASE_BRANCHES:
            raise EmpireCoderSandboxError(
                "base branch is outside the governed branch allowlist"
            )
        if not self.allowed_paths:
            raise EmpireCoderSandboxError("allowed_paths required")
        if any(_scoped_repo_path(target) is None for target in self.allowed_paths):
            raise EmpireCoderSandboxError("allowed_paths must be safe repo-relative paths")
        if not self.lease_resources:
            raise EmpireCoderSandboxError("lease_resources required")
        for target in self.pytest_targets:
            if (not target.startswith("tests/")
                    or not target.endswith(".py")
                    or _scoped_repo_path(target) is None):
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


@contextmanager
def _bounded_inference_runtime(seconds: float):
    """Fail closed when model inference exhausts the job's remaining time.

    Only operate on a dedicated main-thread sandbox execution. Do not
    overwrite other components' SIGALRM deadline or signal handler.
    The existing run_empire_coder_sandbox_job finally always releases its
    execution lease and deletes the temporary clone after this exits.
    """
    if seconds <= 0:
        raise EmpireCoderSandboxError("model_inference_deadline_exceeded")
    if (not hasattr(signal, "setitimer")
            or threading.current_thread() is not threading.main_thread()):
        raise EmpireCoderSandboxError("model_deadline_requires_main_thread")
    if signal.getitimer(signal.ITIMER_REAL)[0] > 0:
        raise EmpireCoderSandboxError("existing_process_deadline_owned_elsewhere")

    previous_handler = signal.getsignal(signal.SIGALRM)

    def deadline_exceeded(_signum, _frame):
        raise EmpireCoderSandboxError("model_inference_deadline_exceeded")

    signal.signal(signal.SIGALRM, deadline_exceeded)
    try:
        signal.setitimer(signal.ITIMER_REAL, seconds)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


@contextmanager
def _shared_coder_ollama_lock(root: Path):
    """Serialize sandbox model calls with the original Empire Coder worker.

    Each disposable clone has a different runtime/ollama.lock. Use the
    original worker's existing real-root lock instead, so multiple Coder
    tasks cannot silently compete for CPU inference. Never wait behind
    another owner: return a distinct busy result before contacting Ollama.
    The caller retains its separate execution lease and source allowlist.
    """
    target = root / "runtime/coder/ollama.lock"
    try:
        fd = os.open(target, os.O_RDWR | os.O_NOFOLLOW)
    except OSError as exc:
        raise EmpireCoderSandboxError(
            "original_coder_inference_lock_unavailable"
        ) from exc
    with os.fdopen(fd, "r+") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise EmpireCoderSandboxError("original_coder_inference_busy") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _scoped_repo_path(value: str) -> str | None:
    """Accept only repo-relative paths without traversal or empty segments.

    Remove a single conventional './' prefix, NEVER strip '..' or '/'.
    This must be applied to both the permitted scope and the proposed path
    before using any prefix-based allowlist comparison.
    """
    raw = str(value or "").strip().replace("\\", "/")
    if not raw or raw.startswith("/") or raw.endswith("//") or "\x00" in raw:
        return None
    if raw.startswith("./"):
        raw = raw[2:]
    raw = raw.rstrip("/")
    parts = raw.split("/")
    if any(not part or part in (".", "..") or ":" in part for part in parts):
        return None
    return "/".join(parts)


def _path_allowed(path: str, allowed: tuple[str, ...]) -> bool:
    clean = _scoped_repo_path(path)
    if clean is None:
        return False
    for raw in allowed:
        prefix = _scoped_repo_path(raw)
        if prefix and (clean == prefix or clean.startswith(prefix + "/")):
            return True
    return False


def _scoped_source_context(coder, context, allowed_paths: tuple[str, ...]):
    """Prioritise bounded, exact source files over unrelated search matches.

    Only the existing repo.read path validator accesses files. Never walk a
    broad symbol index or source tree just to infer which file to patch.
    """
    selected: list[ContextDocument] = []
    for raw in allowed_paths:
        path = _scoped_repo_path(raw)
        if not path or not path.endswith(".py") or len(selected) >= 2:
            continue
        try:
            snippet = coder.repo.read(path, max_chars=2400)
        except (OSError, ValueError):
            continue
        if snippet:
            selected.append(ContextDocument(
                path=path,
                reason="exact authorised source-file evidence",
                excerpt=snippet,
            ))
    if not selected:
        return context
    # Preserve a brief architectural provenance excerpt, rather than losing
    # the original Blueprint context entirely.
    blueprint = [
        ContextDocument(
            path=doc.path,
            reason=doc.reason,
            excerpt=doc.excerpt[:800],
        )
        for doc in context.documents
        if doc.path == "docs/BLUEPRINT_V6.md"
    ][:1]
    return replace(
        context,
        documents=tuple(selected + blueprint),
        token_budget_chars=6000,
    )


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
        if not value:
            continue
        if value.startswith("runtime/"):
            continue
        if value.startswith(".aider.tags.cache."):
            continue
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
    job_started = time.monotonic()
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

        capability_path = (
            root / "runtime/execution_plane/builder_capabilities.json"
        )
        ledger_exists = capability_path.exists()
        aider_ready = builder_capability_ready(
            "empire_coder",
            "aider_mutation",
            path=capability_path,
        )
        structured_ready = builder_capability_ready(
            "empire_coder",
            "structured_patch_mutation",
            path=capability_path,
        )
        capability_snapshot = builder_capability_snapshot(capability_path)
        structured_capability = (
            ((capability_snapshot.get("workers") or {})
             .get("empire_coder") or {})
            .get("structured_patch_mutation") or {}
        )
        structured_model = (
            str(structured_capability.get("model") or "").strip()
            or "qwen2.5-coder:1.5b"
        )
        preference = str(
            os.getenv("EMPIRE_CODER_MUTATION_BACKEND") or "auto"
        ).strip().lower()
        if preference not in {"auto", "aider", "structured_patch"}:
            preference = "auto"

        if preference == "aider":
            backend_order = ("aider", "structured_patch")
        elif preference == "structured_patch":
            backend_order = ("structured_patch", "aider")
        elif aider_ready:
            backend_order = ("aider", "structured_patch")
        else:
            backend_order = ("structured_patch", "aider")

        result["mutation_backend_policy"] = {
            "preference": preference,
            "aider_ready": aider_ready,
            "structured_patch_ready": structured_ready,
            "structured_patch_model": structured_model,
            "capability_ledger_observed": ledger_exists,
            "attempt_order": list(backend_order),
        }
        result["backend_attempts"] = []

        mutation_backend = None
        coder = None
        task = None
        candidate = None
        proposal = None

        for backend in backend_order:
            if backend == "aider":
                if not aider_ready:
                    result["backend_attempts"].append({
                        "backend": "aider",
                        "status": "SKIPPED",
                        "reason": "aider_mutation_capability_not_proven",
                    })
                    continue

                model_selection = select_usable_aider_model(
                    timeout_seconds=20,
                    max_candidates=6,
                )
                selected_model = model_selection.get("selected")
                if not selected_model:
                    result["backend_attempts"].append({
                        "backend": "aider",
                        "status": "SKIPPED",
                        "reason": "no_usable_omniroute_model",
                    })
                    result["aider_model_selection"] = model_selection
                    continue

                result["aider_model_selection"] = model_selection
                aider_result = run_aider_mutation(
                    clone,
                    AiderMutationRequest(
                        objective=job.objective,
                        allowed_paths=job.allowed_paths,
                        model=str(selected_model),
                        max_runtime_seconds=job.max_runtime_seconds,
                    ),
                )
                result["aider"] = aider_result
                result["backend_attempts"].append({
                    "backend": "aider",
                    "status": aider_result.get("status"),
                    "reason": aider_result.get("reason"),
                })
                if aider_result.get("status") == "EDITED":
                    mutation_backend = "aider"
                    break
                continue

            if backend == "structured_patch":
                if ledger_exists and not structured_ready:
                    result["backend_attempts"].append({
                        "backend": "structured_patch",
                        "status": "SKIPPED",
                        "reason": (
                            "structured_patch_mutation_capability_not_proven"
                        ),
                    })
                    continue

                try:
                    with _structured_patch_runtime_env(
                        structured_ready,
                        model=structured_model,
                    ):
                        coder = EmpireCoder(
                            clone,
                            runtime_root=clone / "runtime/coder",
                        )
                        task = coder.create_task(job.objective)
                        context = coder.build_context(
                            task.id,
                            terms=(),
                            symbols=(),
                            budget_chars=4000,
                        )
                        context = _scoped_source_context(
                            coder, context, job.allowed_paths
                        )
                        remaining = (
                            job.max_runtime_seconds
                            - (time.monotonic() - job_started)
                        )
                        with _shared_coder_ollama_lock(root):
                            with _bounded_inference_runtime(remaining):
                                candidate = coder.propose_structured_patch(
                                    task.id,
                                    (
                                        "Implement exactly one smallest safe DEVELOPMENT "
                                        "patch for the task objective. Return only the "
                                        "machine-checkable structured patch requested by "
                                        "Empire Coder. Do not touch deployment, services, "
                                        "production databases, outbound, credentials, "
                                        "payments, funds or revenue truth.\n\nTASK:\n"
                                        + job.objective
                                    ),
                                    context,
                                )
                except Exception as exc:
                    result["backend_attempts"].append({
                        "backend": "structured_patch",
                        "status": "FAILED",
                        "reason": (
                            f"{type(exc).__name__}:{exc}"
                        )[:1000],
                    })
                    if (isinstance(exc, EmpireCoderSandboxError)
                            and str(exc) in {
                                "original_coder_inference_busy",
                                "original_coder_inference_lock_unavailable",
                            }):
                        result["status"] = "MODEL_INFERENCE_BUSY"
                        result["reason"] = str(exc)
                        return result
                    if isinstance(exc, EmpireCoderSandboxError) and (
                        "deadline" in str(exc)
                    ):
                        result["status"] = "TIME_BUDGET_EXCEEDED"
                        result["reason"] = str(exc)
                        return result
                    continue

                proposal = candidate.proposal
                result["candidate"] = {
                    "eligible": candidate.eligible,
                    "target_path": proposal.target_path,
                    "operation": proposal.operation.value,
                    "validation": candidate.validation.as_dict(),
                }
                if not candidate.eligible:
                    result["backend_attempts"].append({
                        "backend": "structured_patch",
                        "status": "INELIGIBLE",
                        "reason": "candidate_not_eligible",
                    })
                    continue
                if not _path_allowed(
                    proposal.target_path,
                    job.allowed_paths,
                ):
                    result["backend_attempts"].append({
                        "backend": "structured_patch",
                        "status": "PATH_POLICY_FAILED",
                        "reason": proposal.target_path,
                    })
                    continue

                coder.apply_structured_patch(task.id, candidate)
                mutation_backend = "structured_patch"
                result["backend_attempts"].append({
                    "backend": "structured_patch",
                    "status": "EDITED",
                    "reason": None,
                })
                break

        if mutation_backend is None:
            result["status"] = "NO_IMPLEMENTATION"
            result["reason"] = "no_proven_mutation_backend_succeeded"
            return result

        result["mutation_backend"] = mutation_backend
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
            result["reason"] = "mutation_backend_made_no_repository_change"
            return result

        expected_tests = (
            tuple(proposal.expected_tests)
            if proposal is not None
            else ()
        )
        tests = tuple(dict.fromkeys(
            expected_tests + tuple(job.pytest_targets)
        ))
        checks: list[dict[str, Any]] = []
        if tests:
            remaining = job.max_runtime_seconds - (time.monotonic() - job_started)
            if remaining <= 0:
                result["status"] = "TIME_BUDGET_EXCEEDED"
                result["reason"] = "verification_time_budget_exceeded"
                return result
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
                timeout=max(1, min(int(remaining), 1200)),
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

        if time.monotonic() - job_started >= job.max_runtime_seconds:
            result["status"] = "TIME_BUDGET_EXCEEDED"
            result["reason"] = "proposal_publication_time_budget_exceeded"
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
        remaining = job.max_runtime_seconds - (time.monotonic() - job_started)
        if remaining <= 0:
            result["status"] = "TIME_BUDGET_EXCEEDED"
            result["reason"] = "proposal_push_time_budget_exceeded"
            return result
        pushed = _run(
            ["git", "push", "origin", f"HEAD:refs/heads/{proposal_branch}"],
            cwd=clone,
            timeout=max(1, min(int(remaining), 180)),
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