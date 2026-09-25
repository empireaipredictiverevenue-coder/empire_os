"""Sandboxed Pi coding worker for EmpireOS.

Pi never works in the production repository. Each job gets an ephemeral full
clone plus an exclusive execution-plane lease. The model process runs through a
hardened systemd user scope with localhost-only networking.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Mapping

from empire_os.execution_lease import (
    ExecutionLeaseError,
    ExecutionLeaseManager,
)


JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
DEFAULT_BRANCH = "feature/revenue-intelligence-v2"
DEFAULT_PI_BIN = Path("/opt/empire/pi-agent/bin/pi")
DEFAULT_PI_CONFIG = Path("/etc/empire_os/pi-agent")
DEFAULT_WORK_ROOT = Path("/var/tmp/empire-pi")
SENSITIVE_ENV = re.compile(
    r"(SECRET|TOKEN|PASSWORD|PASSWD|API_KEY|PRIVATE_KEY|COOKIE|SUPABASE|RESEND|"
    r"SENDGRID|BREVO|OPENROUTER|GITHUB_TOKEN|GH_TOKEN|AWS_|AZURE_|GOOGLE_)",
    re.IGNORECASE,
)


class PiSandboxError(RuntimeError):
    pass


SYSTEMD_EXEC_FAILURES = {
    218: "CAPABILITIES",
    225: "NETWORK",
    226: "NAMESPACE",
    227: "NO_NEW_PRIVILEGES",
    228: "SECCOMP",
    244: "BPF",
}


def _sandbox_failure_stage(returncode: int) -> str | None:
    return SYSTEMD_EXEC_FAILURES.get(int(returncode))


@dataclass(frozen=True)
class PiSandboxJob:
    job_id: str
    prompt: str
    allowed_paths: tuple[str, ...]
    pytest_targets: tuple[str, ...] = ()
    lease_resources: tuple[str, ...] = ()
    base_branch: str = DEFAULT_BRANCH
    max_runtime_seconds: int = 900
    require_changes: bool = True
    publish_proposal: bool = True

    def validate(self) -> None:
        if not JOB_ID_RE.fullmatch(self.job_id):
            raise PiSandboxError("invalid job_id")
        if not self.prompt.strip():
            raise PiSandboxError("prompt required")
        if len(self.prompt) > 20_000:
            raise PiSandboxError("prompt too long")
        if self.base_branch != DEFAULT_BRANCH:
            raise PiSandboxError("base branch is pinned")
        if not self.allowed_paths:
            raise PiSandboxError("allowed_paths required")
        for target in self.pytest_targets:
            if not target.startswith("tests/") or ".py" not in target:
                raise PiSandboxError("invalid pytest target")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: int = 120,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd else None,
        env=dict(env or os.environ),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=check,
    )


def _safe_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    base: dict[str, str] = {}
    for key, value in os.environ.items():
        if SENSITIVE_ENV.search(key):
            continue
        if key in {
            "PYTHONPATH",
            "VIRTUAL_ENV",
            "SSH_AUTH_SOCK",
            "SSH_AGENT_PID",
            "GIT_ASKPASS",
            "SSH_ASKPASS",
            "GPG_AGENT_INFO",
        }:
            continue
        base[key] = value
    base.update(dict(extra or {}))
    return base


def _allowed_changed_path(path: str, allowed: tuple[str, ...]) -> bool:
    clean = path.strip().replace("\\", "/").lstrip("./")
    for raw in allowed:
        prefix = raw.strip().replace("\\", "/").lstrip("./").rstrip("/")
        if not prefix:
            continue
        if clean == prefix or clean.startswith(prefix + "/"):
            return True
    return False


def _changed_paths(clone: Path) -> list[str]:
    result = _run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=clone,
        check=True,
    )
    paths: list[str] = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        value = line[3:].strip()
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        if value:
            paths.append(value)
    return sorted(dict.fromkeys(paths))


def _model_id(config_dir: Path) -> str:
    try:
        raw = json.loads((config_dir / "models.json").read_text(encoding="utf-8"))
        providers = raw.get("providers") or {}
        provider = providers.get("empire-local") or {}
        models = provider.get("models") or []
        model_id = str((models[0] if models else {}).get("id") or "").strip()
    except (OSError, json.JSONDecodeError, AttributeError):
        model_id = ""
    if not model_id:
        raise PiSandboxError("Pi local model configuration unavailable")
    return model_id


def build_pi_systemd_command(
    *,
    clone: Path,
    prompt: str,
    model_id: str,
    max_runtime_seconds: int,
    system_prompt: str,
    pi_bin: Path = DEFAULT_PI_BIN,
) -> list[str]:
    config = clone / ".empire_pi"
    argv = [
        "systemd-run",
        "--user",
        "--wait",
        "--collect",
        "--pipe",
        "--quiet",
        "--property=NoNewPrivileges=yes",
        "--property=PrivateTmp=yes",
        "--property=PrivateUsers=yes",
        "--property=ProtectSystem=strict",
        "--property=ProtectHome=yes",
        "--property=RestrictSUIDSGID=yes",
        "--property=IPAddressDeny=any",
        "--property=IPAddressAllow=localhost",
        "--property=MemoryMax=2G",
        "--property=TasksMax=64",
        f"--property=ReadWritePaths={clone}",
        "--property=ReadOnlyPaths=/opt/empire/pi-agent",
        "--property=InaccessiblePaths=/srv/empire_os",
        "--property=InaccessiblePaths=/etc/empire_os",
        "--property=InaccessiblePaths=/var/lib/empire",
        "--property=InaccessiblePaths=/home/ubuntu/.ssh",
        f"--working-directory={clone}",
        "env",
        f"PI_CODING_AGENT_DIR={config}",
        "PI_OFFLINE=1",
        "PI_TELEMETRY=0",
        str(pi_bin),
        "--provider",
        "empire-local",
        "--model",
        model_id,
        "--no-session",
        "--no-extensions",
        "--no-skills",
        "--no-prompt-templates",
        "--no-context-files",
        "--tools",
        "read,grep,find,ls,edit,write,bash",
        "--system-prompt",
        system_prompt,
        "--mode",
        "json",
        prompt,
    ]
    return argv


def run_pi_sandbox_job(
    repo_root: str | Path,
    job: PiSandboxJob,
    *,
    lease_manager: ExecutionLeaseManager | None = None,
    work_root: Path = DEFAULT_WORK_ROOT,
    pi_bin: Path = DEFAULT_PI_BIN,
    pi_config: Path = DEFAULT_PI_CONFIG,
) -> dict[str, Any]:
    job.validate()
    root = Path(repo_root).resolve()
    if root != Path("/srv/empire_os"):
        # Tests may use temporary repos, but real production invocation remains
        # explicitly bound by its caller.
        pass
    if not pi_bin.exists():
        raise PiSandboxError("Pi binary not installed")
    if not pi_config.exists():
        raise PiSandboxError("Pi configuration not installed")

    lease_resources = job.lease_resources or tuple(
        f"path:{path}" for path in job.allowed_paths
    )
    manager = lease_manager or ExecutionLeaseManager()
    try:
        lease = manager.acquire(
            owner="pi",
            job_id=job.job_id,
            resources=lease_resources,
            ttl_seconds=job.max_runtime_seconds + 300,
        )
    except ExecutionLeaseError as exc:
        raise PiSandboxError(str(exc)) from exc

    work_root.mkdir(parents=True, exist_ok=True)
    clone = work_root / job.job_id
    shutil.rmtree(clone, ignore_errors=True)
    result: dict[str, Any] = {
        "schema_version": "empire.pi-sandbox-result.v1",
        "job_id": job.job_id,
        "status": "FAILED",
        "lease_id": lease.lease_id,
        "changed_paths": [],
        "verification": None,
        "proposal_branch": None,
        "production_mutation": False,
        "external_send": False,
        "payment_action": False,
        "revenue_recognition": False,
        "execution_authority": "none",
    }

    try:
        _run(
            [
                "git",
                "clone",
                "--no-hardlinks",
                "--single-branch",
                "--branch",
                job.base_branch,
                str(root),
                str(clone),
            ],
            timeout=180,
            check=True,
        )

        config = clone / ".empire_pi"
        config.mkdir(mode=0o700)
        shutil.copy2(pi_config / "models.json", config / "models.json")
        shutil.copy2(
            pi_config / "empire-policy.txt",
            config / "empire-policy.txt",
        )

        model_id = _model_id(config)
        system_prompt = (config / "empire-policy.txt").read_text(
            encoding="utf-8"
        ).strip()
        command = build_pi_systemd_command(
            clone=clone,
            prompt=job.prompt,
            model_id=model_id,
            max_runtime_seconds=job.max_runtime_seconds,
            system_prompt=system_prompt,
            pi_bin=pi_bin,
        )
        try:
            completed = _run(
                command,
                env=_safe_env(),
                timeout=max(60, min(job.max_runtime_seconds + 30, 1830)),
            )
        except subprocess.TimeoutExpired as exc:
            raise PiSandboxError("Pi sandbox timed out") from exc

        result["pi_returncode"] = completed.returncode
        result["sandbox_failure_stage"] = _sandbox_failure_stage(
            completed.returncode
        )
        result["pi_output_tail"] = (
            (completed.stdout or "") + "\n" + (completed.stderr or "")
        )[-4000:]
        if completed.returncode != 0:
            result["status"] = "PI_FAILED"
            return result

        changed = [
            path
            for path in _changed_paths(clone)
            if not path.startswith(".empire_pi/")
        ]
        rejected = [
            path
            for path in changed
            if not _allowed_changed_path(path, job.allowed_paths)
        ]
        if rejected:
            result["status"] = "PATH_POLICY_FAILED"
            result["rejected_paths"] = rejected
            return result
        result["changed_paths"] = changed

        if not changed:
            result["status"] = (
                "NO_IMPLEMENTATION"
                if job.require_changes
                else "COMPLETED_NO_CHANGES"
            )
            result["no_change_allowed"] = not job.require_changes
            return result

        checks: list[dict[str, Any]] = []
        if job.pytest_targets:
            verify = _run(
                [
                    str(root / ".venv/bin/python"),
                    "-m",
                    "pytest",
                    "-q",
                    *job.pytest_targets,
                ],
                cwd=clone,
                env=_safe_env({"PYTHONPATH": str(clone)}),
                timeout=600,
            )
            checks.append(
                {
                    "argv": [
                        "python",
                        "-m",
                        "pytest",
                        "-q",
                        *job.pytest_targets,
                    ],
                    "returncode": verify.returncode,
                    "output_tail": (
                        (verify.stdout or "") + "\n" + (verify.stderr or "")
                    )[-4000:],
                }
            )

        verification_passed = all(
            check["returncode"] == 0 for check in checks
        )
        result["verification"] = {
            "passed": verification_passed,
            "checks": checks,
        }
        if not verification_passed:
            result["status"] = "VERIFICATION_FAILED"
            return result

        if not job.publish_proposal:
            result["status"] = "MUTATION_SMOKE_PASSED"
            result["proposal_branch"] = None
            return result

        branch = f"pi/job-{job.job_id}"
        _run(["git", "switch", "-C", branch], cwd=clone, check=True)
        for path in changed:
            _run(["git", "add", "-A", "--", path], cwd=clone, check=True)
        _run(
            [
                "git",
                "-c",
                "user.name=Empire Pi",
                "-c",
                "user.email=pi@empire-ai.co.uk",
                "commit",
                "-m",
                f"Pi proposal: {job.job_id}",
            ],
            cwd=clone,
            check=True,
        )
        sha = _run(
            ["git", "rev-parse", "HEAD"],
            cwd=clone,
            check=True,
        ).stdout.strip()

        remote_url = _run(
            ["git", "remote", "get-url", "origin"],
            cwd=root,
            check=True,
        ).stdout.strip()
        _run(["git", "remote", "set-url", "origin", remote_url], cwd=clone, check=True)
        _run(
            ["git", "push", "origin", f"HEAD:refs/heads/{branch}"],
            cwd=clone,
            env=_safe_env(),
            timeout=180,
            check=True,
        )
        result["proposal_branch"] = branch
        result["proposal_commit"] = sha
        result["status"] = "PROPOSAL_READY"
        return result
    finally:
        manager.release(lease.lease_id)
        shutil.rmtree(clone, ignore_errors=True)
