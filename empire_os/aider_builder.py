"""Governed Aider mutation backend for Empire Coder.

Aider is an optional edit engine only. EmpireOS retains workspace isolation,
mutation leases, changed-path policy, tests, proposal publication and
verification authority.

The backend expects to run inside an already-disposable git clone. It never
commits, pushes, deploys or grants execution authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "empire.aider-builder.v1"
DEFAULT_MODEL = "openai/auto"
KNOWN_EXECUTABLES = (
    "/usr/local/bin/aider",
    "/home/ubuntu/.local/bin/aider",
)
OMNIROUTE_ENV_PATH = Path("/etc/empire_os/omniroute-hermes.env")


@dataclass(frozen=True)
class AiderMutationRequest:
    objective: str
    allowed_paths: tuple[str, ...]
    model: str = DEFAULT_MODEL
    max_runtime_seconds: int = 900

    def validate(self) -> None:
        if not self.objective.strip():
            raise ValueError("objective required")
        if len(self.objective) > 20_000:
            raise ValueError("objective too long")
        if not self.allowed_paths:
            raise ValueError("allowed_paths required")
        for raw in self.allowed_paths:
            path = _normalise_path(raw)
            if not path:
                raise ValueError("allowed path cannot be empty")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalise_path(value: str) -> str:
    raw = str(value or "").strip().replace("\\", "/")
    while raw.startswith("./"):
        raw = raw[2:]
    if raw.startswith("/"):
        raise ValueError("absolute allowed paths are forbidden")
    parts = Path(raw).parts
    if ".." in parts:
        raise ValueError("parent traversal is forbidden")
    return "/".join(parts)


def _path_allowed(path: str, allowed: Sequence[str]) -> bool:
    clean = _normalise_path(path)
    for raw in allowed:
        prefix = _normalise_path(raw).rstrip("/")
        if prefix and (
            clean == prefix
            or clean.startswith(prefix + "/")
        ):
            return True
    return False


def resolve_aider_executable() -> str | None:
    configured = str(
        os.getenv("EMPIRE_AIDER_EXECUTABLE") or ""
    ).strip()
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
        return None

    discovered = shutil.which("aider")
    if discovered:
        return discovered

    for raw in KNOWN_EXECUTABLES:
        candidate = Path(raw)
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def aider_health() -> dict[str, Any]:
    executable = resolve_aider_executable()
    if not executable:
        return {
            "schema_version": SCHEMA_VERSION,
            "ready": False,
            "reason": "aider_executable_not_found",
            "version": None,
            "executable": None,
            "execution_authority": "none",
        }
    try:
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "ready": False,
            "reason": f"aider_health_failed:{type(exc).__name__}",
            "version": None,
            "executable": executable,
            "execution_authority": "none",
        }
    version = (result.stdout or result.stderr or "").strip()[:300]
    return {
        "schema_version": SCHEMA_VERSION,
        "ready": result.returncode == 0,
        "reason": (
            "aider_ready"
            if result.returncode == 0
            else f"aider_version_exit:{result.returncode}"
        ),
        "version": version or None,
        "executable": executable,
        "execution_authority": "none",
    }


def _protected_omniroute_env(
    path: Path = OMNIROUTE_ENV_PATH,
) -> dict[str, str]:
    allowed = {
        "OPENAI_BASE_URL",
        "OPENAI_API_KEY",
        "EMPIRE_HERMES_MODEL",
    }
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        if key in allowed and value.strip():
            values[key] = value.strip().strip('"').strip("'")
    return values


def _provider_environment(
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    current = dict(os.environ if source is None else source)
    if source is None:
        protected = _protected_omniroute_env()
        for key, value in protected.items():
            current.setdefault(key, value)
    base = str(
        current.get("EMPIRE_AIDER_OPENAI_API_BASE")
        or current.get("AIDER_OPENAI_API_BASE")
        or current.get("OPENAI_API_BASE")
        or current.get("OPENAI_BASE_URL")
        or ""
    ).strip()
    key = str(
        current.get("EMPIRE_AIDER_OPENAI_API_KEY")
        or current.get("AIDER_OPENAI_API_KEY")
        or current.get("OPENAI_API_KEY")
        or ""
    ).strip()

    env = {
        key_name: value
        for key_name, value in current.items()
        if key_name in {
            "PATH",
            "LANG",
            "LC_ALL",
            "SSL_CERT_FILE",
            "SSL_CERT_DIR",
            "HTTPS_PROXY",
            "HTTP_PROXY",
            "ALL_PROXY",
            "NO_PROXY",
        }
    }
    if base:
        env["OPENAI_API_BASE"] = base
        env["AIDER_OPENAI_API_BASE"] = base
    if key:
        env["OPENAI_API_KEY"] = key
        env["AIDER_OPENAI_API_KEY"] = key

    # Disable network telemetry/update behavior that is unrelated to the job.
    env["AIDER_ANALYTICS"] = "false"
    env["AIDER_ANALYTICS_DISABLE"] = "true"
    env["AIDER_CHECK_UPDATE"] = "false"
    env["AIDER_SHOW_RELEASE_NOTES"] = "false"
    env["AIDER_AUTO_COMMITS"] = "false"
    env["AIDER_DIRTY_COMMITS"] = "false"
    env["AIDER_AUTO_TEST"] = "false"
    env["AIDER_AUTO_LINT"] = "false"
    env["AIDER_SUGGEST_SHELL_COMMANDS"] = "false"
    env["AIDER_DETECT_URLS"] = "false"
    env["AIDER_CACHE_PROMPTS"] = "false"
    return env


def _sanitize_output(
    value: str,
    environment: Mapping[str, str] | None = None,
) -> str:
    text = str(value or "")
    env = _provider_environment(environment)
    secret = str(env.get("OPENAI_API_KEY") or "")
    if secret:
        text = text.replace(secret, "[REDACTED]")
    return text[-4000:]


def resolved_aider_model(
    requested: str | None = None,
) -> str:
    explicit = str(
        requested
        or os.getenv("EMPIRE_AIDER_MODEL")
        or ""
    ).strip()
    if explicit and explicit != DEFAULT_MODEL:
        return explicit

    protected = _protected_omniroute_env()
    routed = str(
        protected.get("EMPIRE_HERMES_MODEL") or ""
    ).strip()
    if routed:
        if routed.startswith("openai/"):
            return routed
        return "openai/" + routed

    return DEFAULT_MODEL


def provider_ready(
    source: Mapping[str, str] | None = None,
) -> tuple[bool, str]:
    env = _provider_environment(source)
    if not env.get("OPENAI_API_BASE"):
        return False, "openai_compatible_base_missing"
    if not env.get("OPENAI_API_KEY"):
        return False, "openai_compatible_key_missing"
    return True, "provider_ready"


def build_aider_command(
    workspace: str | Path,
    request: AiderMutationRequest,
    *,
    executable: str | None = None,
) -> list[str]:
    request.validate()
    root = Path(workspace).resolve()
    binary = executable or resolve_aider_executable()
    if not binary:
        raise RuntimeError("aider executable unavailable")

    history_root = root / ".git"
    config_path = history_root / "empire-aider-config.yml"
    env_path = history_root / "empire-aider.env"
    command = [
        binary,
        "--model",
        request.model,
        "--message",
        (
            "You are an EmpireOS governed edit backend. "
            "Modify only the explicitly allowed files for this task. "
            "Do not run shell commands, do not commit, do not push, do not "
            "touch runtime, credentials, environment files, deployment state, "
            "production data, outbound systems, payments or revenue truth. "
            "Make the smallest production-quality code change that satisfies "
            "the objective. EmpireOS will independently validate paths and run "
            "tests after you exit.\n\nOBJECTIVE:\n"
            + request.objective
        ),
        "--yes-always",
        "--no-auto-commits",
        "--no-dirty-commits",
        "--no-auto-test",
        "--no-auto-lint",
        "--no-suggest-shell-commands",
        "--no-detect-urls",
        "--no-analytics",
        "--no-check-update",
        "--no-show-release-notes",
        "--no-cache-prompts",
        "--map-tokens",
        "0",
        "--map-refresh",
        "manual",
        "--no-gitignore",
        "--no-add-gitignore-files",
        "--no-pretty",
        "--no-stream",
        "--no-restore-chat-history",
        "--env-file",
        str(env_path),
        "--config",
        str(config_path),
        "--input-history-file",
        str(history_root / "empire-aider-input.history"),
        "--chat-history-file",
        str(history_root / "empire-aider-chat.history.md"),
    ]

    # Existing allowed files are supplied explicitly. Missing paths may still
    # be created when named in the objective; changed-path policy is enforced
    # after Aider exits.
    for raw in request.allowed_paths:
        path = root / _normalise_path(raw)
        if path.is_file():
            command.extend(["--file", _normalise_path(raw)])
    return command


def _changed_paths(workspace: Path) -> list[str]:
    result = subprocess.run(
        [
            "git",
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("git status failed after aider")
    changed: list[str] = []
    for line in result.stdout.splitlines():
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


def run_aider_mutation(
    workspace: str | Path,
    request: AiderMutationRequest,
    *,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Run one bounded Aider edit inside an existing disposable clone."""
    request.validate()
    root = Path(workspace).resolve()
    health = aider_health()
    if not health["ready"]:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "BACKEND_UNAVAILABLE",
            "reason": health["reason"],
            "health": health,
            "changed_paths": [],
            "production_mutation": False,
            "external_send": False,
            "production_deploy": False,
            "execution_authority": "none",
        }

    ready, reason = provider_ready(environment)
    if not ready:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "PROVIDER_UNAVAILABLE",
            "reason": reason,
            "health": health,
            "changed_paths": [],
            "production_mutation": False,
            "external_send": False,
            "production_deploy": False,
            "execution_authority": "none",
        }

    env = _provider_environment(environment)
    git_dir = root / ".git"
    git_dir.mkdir(parents=True, exist_ok=True)
    (git_dir / "empire-aider-config.yml").write_text(
        "{}\n",
        encoding="utf-8",
    )
    (git_dir / "empire-aider.env").write_text(
        "",
        encoding="utf-8",
    )
    env["HOME"] = "/var/tmp/empire-aider-home"
    env["XDG_CACHE_HOME"] = "/var/tmp/empire-aider-cache"
    Path(env["HOME"]).mkdir(parents=True, exist_ok=True)
    Path(env["XDG_CACHE_HOME"]).mkdir(parents=True, exist_ok=True)

    command = build_aider_command(
        root,
        request,
        executable=str(health.get("executable") or "") or None,
    )
    try:
        run = subprocess.run(
            command,
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
            timeout=max(
                60,
                min(int(request.max_runtime_seconds), 1800),
            ),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "AIDER_FAILED",
            "reason": "aider_timeout",
            "changed_paths": [],
            "production_mutation": False,
            "external_send": False,
            "production_deploy": False,
            "execution_authority": "none",
        }
    except OSError as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "AIDER_FAILED",
            "reason": f"aider_os_error:{type(exc).__name__}",
            "changed_paths": [],
            "production_mutation": False,
            "external_send": False,
            "production_deploy": False,
            "execution_authority": "none",
        }

    try:
        changed = _changed_paths(root)
    except RuntimeError as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "AIDER_FAILED",
            "reason": str(exc),
            "returncode": run.returncode,
            "changed_paths": [],
            "output_tail": _sanitize_output(
                (run.stdout or "") + "\n" + (run.stderr or ""),
                environment,
            ),
            "production_mutation": False,
            "external_send": False,
            "production_deploy": False,
            "execution_authority": "none",
        }

    rejected = [
        path
        for path in changed
        if not _path_allowed(path, request.allowed_paths)
    ]
    status = (
        "PATH_POLICY_FAILED"
        if rejected
        else "EDITED"
        if changed and run.returncode == 0
        else "NO_CHANGES"
        if run.returncode == 0
        else "AIDER_FAILED"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "reason": (
            "changed_path_outside_allowlist"
            if rejected
            else None
        ),
        "model": request.model,
        "returncode": run.returncode,
        "changed_paths": changed,
        "rejected_paths": rejected,
        "output_tail": _sanitize_output(
            (run.stdout or "") + "\n" + (run.stderr or ""),
            environment,
        ),
        "production_mutation": False,
        "external_send": False,
        "payment_action": False,
        "revenue_recognition": False,
        "production_deploy": False,
        "commit_performed": False,
        "push_performed": False,
        "execution_authority": "none",
    }
