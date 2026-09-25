"""Governed Hermes resident worker for EmpireOS.

The worker consumes job manifests from a dedicated GitHub control branch,
executes Hermes in an isolated git worktree, validates the resulting diff,
runs bounded verification, pushes a proposal branch, and publishes a result
back to the control branch.

It never merges into the production branch, never applies database migrations,
never sends outbound, never moves funds, and never grants execution authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from typing import Any, Iterable, Mapping

from empire_os.execution_lease import (
    ExecutionLeaseError,
    ExecutionLeaseManager,
)



SCHEMA_VERSION = "empire.hermes.control_job.v1"
RESULT_SCHEMA_VERSION = "empire.hermes.control_result.v1"

DEFAULT_CONTROL_BRANCH = "ops/hermes-control"
DEFAULT_BASE_BRANCH = "feature/revenue-intelligence-v2"
DEFAULT_REMOTE = "origin"

JOB_PATH_PREFIX = "jobs/inbox/"
RESULT_PATH_PREFIX = "jobs/results/"

JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
TEST_TARGET_RE = re.compile(r"^tests/[A-Za-z0-9_./-]+\.py(?:::[A-Za-z0-9_\[\].:-]+)?$")

PROTECTED_PREFIXES = (
    "recovery/",
    "toop/",
    ".git/",
    "runtime/",
)
PROTECTED_EXACT = {
    ".env",
    ".env.local",
    ".env.production",
}
SAFE_EDIT_PREFIXES = (
    "empire_os/",
    "tests/",
    "scripts/",
    "docs/",
    "deploy/",
    "supabase/migrations/",
)
SAFE_EDIT_EXACT = {
    "pyproject.toml",
    "README.md",
}

ALLOWED_AUTHORITIES = {"observe", "internal_write"}
ALLOWED_KINDS = {"code_task"}

FORBIDDEN_RESULT_PATH_TOKENS = (
    "/recovery/",
    "/toop/",
)


class HermesControlError(RuntimeError):
    pass


@dataclass(frozen=True)
class HermesJob:
    job_id: str
    prompt: str
    kind: str = "code_task"
    authority: str = "internal_write"
    base_branch: str = DEFAULT_BASE_BRANCH
    allowed_paths: tuple[str, ...] = SAFE_EDIT_PREFIXES
    pytest_targets: tuple[str, ...] = ()
    lease_resources: tuple[str, ...] = ()
    max_runtime_seconds: int = 900
    created_at: str | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "HermesJob":
        schema = str(raw.get("schema_version") or "").strip()
        if schema != SCHEMA_VERSION:
            raise HermesControlError(
                f"unsupported schema_version: {schema or '<missing>'}"
            )

        job_id = str(raw.get("job_id") or "").strip()
        if not JOB_ID_RE.fullmatch(job_id):
            raise HermesControlError("invalid job_id")

        prompt = str(raw.get("prompt") or "").strip()
        if not prompt:
            raise HermesControlError("prompt is required")
        if len(prompt) > 20_000:
            raise HermesControlError("prompt exceeds 20000 characters")

        kind = str(raw.get("kind") or "code_task").strip()
        if kind not in ALLOWED_KINDS:
            raise HermesControlError(f"unsupported job kind: {kind}")

        authority = str(
            raw.get("authority") or "internal_write"
        ).strip()
        if authority not in ALLOWED_AUTHORITIES:
            raise HermesControlError(
                "Hermes worker accepts observe/internal_write jobs only"
            )

        base_branch = str(
            raw.get("base_branch") or DEFAULT_BASE_BRANCH
        ).strip()
        if base_branch != DEFAULT_BASE_BRANCH:
            raise HermesControlError(
                "base_branch is pinned to the canonical working branch"
            )

        requested_paths = raw.get("allowed_paths")
        if requested_paths is None:
            allowed_paths = SAFE_EDIT_PREFIXES
        elif isinstance(requested_paths, list):
            cleaned = tuple(
                _normalise_allowed_prefix(str(value))
                for value in requested_paths
                if str(value).strip()
            )
            if not cleaned:
                raise HermesControlError(
                    "allowed_paths cannot be empty when supplied"
                )
            for prefix in cleaned:
                if not _allowed_requested_prefix(prefix):
                    raise HermesControlError(
                        f"requested path is outside worker policy: {prefix}"
                    )
            allowed_paths = cleaned
        else:
            raise HermesControlError("allowed_paths must be a list")

        raw_lease_resources = raw.get("lease_resources")
        if raw_lease_resources is None:
            lease_resources = tuple(
                f"path:{value.rstrip('/')}"
                for value in allowed_paths
            )
        elif isinstance(raw_lease_resources, list):
            lease_resources = tuple(
                str(value).strip()
                for value in raw_lease_resources
                if str(value).strip()
            )
            if not lease_resources:
                raise HermesControlError(
                    "lease_resources cannot be empty when supplied"
                )
        else:
            raise HermesControlError("lease_resources must be a list")

        raw_targets = raw.get("pytest_targets") or []
        if not isinstance(raw_targets, list):
            raise HermesControlError("pytest_targets must be a list")
        targets: list[str] = []
        for value in raw_targets[:20]:
            target = str(value).strip()
            if not TEST_TARGET_RE.fullmatch(target):
                raise HermesControlError(
                    f"invalid pytest target: {target}"
                )
            targets.append(target)

        try:
            max_runtime = int(raw.get("max_runtime_seconds") or 900)
        except (TypeError, ValueError) as exc:
            raise HermesControlError(
                "max_runtime_seconds must be an integer"
            ) from exc
        max_runtime = max(60, min(max_runtime, 1800))

        created_at = str(raw.get("created_at") or "").strip() or None

        return cls(
            job_id=job_id,
            prompt=prompt,
            kind=kind,
            authority=authority,
            base_branch=base_branch,
            allowed_paths=allowed_paths,
            pytest_targets=tuple(targets),
            lease_resources=lease_resources,
            max_runtime_seconds=max_runtime,
            created_at=created_at,
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalise_allowed_prefix(value: str) -> str:
    value = value.strip().replace("\\", "/")
    value = value.lstrip("/")
    if value in SAFE_EDIT_EXACT:
        return value
    return value.rstrip("/") + "/"


def _allowed_requested_prefix(prefix: str) -> bool:
    if prefix in SAFE_EDIT_EXACT:
        return True
    return any(
        prefix.startswith(safe) or safe.startswith(prefix)
        for safe in SAFE_EDIT_PREFIXES
    )


def _normalise_repo_path(value: str) -> str:
    value = value.strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    if value.startswith("/"):
        raise HermesControlError("absolute paths are forbidden")
    parts = PurePosixPath(value).parts
    if ".." in parts:
        raise HermesControlError("parent traversal is forbidden")
    return "/".join(parts)


def path_is_protected(path: str) -> bool:
    path = _normalise_repo_path(path)
    if path in PROTECTED_EXACT:
        return True
    return any(path.startswith(prefix) for prefix in PROTECTED_PREFIXES)


def path_is_allowed(path: str, allowed_paths: Iterable[str]) -> bool:
    path = _normalise_repo_path(path)
    if path_is_protected(path):
        return False
    if path in SAFE_EDIT_EXACT and path in set(allowed_paths):
        return True
    return any(
        path.startswith(prefix)
        for prefix in allowed_paths
        if prefix.endswith("/")
    )


def validate_changed_paths(
    changed_paths: Iterable[str],
    *,
    allowed_paths: Iterable[str],
) -> list[str]:
    cleaned: list[str] = []
    violations: list[str] = []
    for raw in changed_paths:
        path = _normalise_repo_path(raw)
        if not path:
            continue
        cleaned.append(path)
        if not path_is_allowed(path, allowed_paths):
            violations.append(path)
    if violations:
        raise HermesControlError(
            "Hermes changed paths outside job policy: "
            + ", ".join(sorted(set(violations)))
        )
    return sorted(set(cleaned))


def _run(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: int = 120,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        env=dict(env) if env is not None else None,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if check and result.returncode != 0:
        raise HermesControlError(
            "command failed: "
            + " ".join(args[:4])
            + f"\nstdout:\n{result.stdout[-4000:]}"
            + f"\nstderr:\n{result.stderr[-4000:]}"
        )
    return result


def _git(
    repo_root: Path,
    *args: str,
    timeout: int = 120,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return _run(
        ["git", "-C", str(repo_root), *args],
        timeout=timeout,
        check=check,
    )


def _prepare_worktree_slot(
    repo_root: Path,
    worktree: Path,
) -> None:
    """Clear only the target slot plus stale Git worktree metadata.

    Interrupted workers can leave a registered worktree whose directory was
    already removed. A later job with the same id then fails before Hermes
    starts. Remove the target if it still exists, prune stale registrations,
    and recreate from a clean path.
    """
    _git(
        repo_root,
        "worktree",
        "remove",
        "--force",
        str(worktree),
        check=False,
    )
    shutil.rmtree(worktree, ignore_errors=True)
    _git(
        repo_root,
        "worktree",
        "prune",
        "--expire",
        "now",
        check=False,
    )


def fetch_control_refs(
    repo_root: Path,
    *,
    control_branch: str = DEFAULT_CONTROL_BRANCH,
    base_branch: str = DEFAULT_BASE_BRANCH,
    remote: str = DEFAULT_REMOTE,
) -> None:
    _git(
        repo_root,
        "fetch",
        remote,
        f"{control_branch}:refs/remotes/{remote}/{control_branch}",
        f"{base_branch}:refs/remotes/{remote}/{base_branch}",
        timeout=180,
    )


def list_pending_job_paths(
    repo_root: Path,
    *,
    control_branch: str = DEFAULT_CONTROL_BRANCH,
    remote: str = DEFAULT_REMOTE,
) -> list[str]:
    result = _git(
        repo_root,
        "ls-tree",
        "-r",
        "--name-only",
        f"{remote}/{control_branch}",
        "--",
        JOB_PATH_PREFIX.rstrip("/"),
    )
    return sorted(
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip().startswith(JOB_PATH_PREFIX)
        and line.strip().endswith(".json")
    )


def control_path_exists(
    repo_root: Path,
    path: str,
    *,
    control_branch: str = DEFAULT_CONTROL_BRANCH,
    remote: str = DEFAULT_REMOTE,
) -> bool:
    result = _git(
        repo_root,
        "cat-file",
        "-e",
        f"{remote}/{control_branch}:{path}",
        check=False,
    )
    return result.returncode == 0


def read_control_json(
    repo_root: Path,
    path: str,
    *,
    control_branch: str = DEFAULT_CONTROL_BRANCH,
    remote: str = DEFAULT_REMOTE,
) -> dict[str, Any]:
    result = _git(
        repo_root,
        "show",
        f"{remote}/{control_branch}:{path}",
    )
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise HermesControlError(
            f"invalid JSON at {path}"
        ) from exc
    if not isinstance(value, dict):
        raise HermesControlError(
            f"control document must be an object: {path}"
        )
    return value


def _changed_paths(worktree: Path) -> list[str]:
    result = _git(
        worktree,
        "status",
        "--porcelain=v1",
        "-z",
    )
    entries = result.stdout.split("\0")
    paths: list[str] = []
    for entry in entries:
        if not entry:
            continue
        if len(entry) < 4:
            continue
        path = entry[3:]
        if " -> " in path:
            _, path = path.split(" -> ", 1)
        paths.append(path)
    return paths


def _hermes_environment() -> dict[str, str]:
    allowed = (
        "PATH",
        "HOME",
        "USER",
        "LOGNAME",
        "LANG",
        "LC_ALL",
        "TERM",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "HTTPS_PROXY",
        "HTTP_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "OPENAI_BASE_URL",
        "OPENAI_API_KEY",
    )
    env = {
        key: value
        for key, value in os.environ.items()
        if key in allowed
    }
    env.setdefault("HOME", "/home/ubuntu")
    env.setdefault("USER", "ubuntu")
    env.setdefault("LOGNAME", "ubuntu")
    env["EMPIRE_AUTONOMOUS_MODE"] = "OBSERVE"
    env["EMPIRE_HERMES_GOVERNED_WORKER"] = "1"
    return env


def build_hermes_prompt(
    job: HermesJob,
    *,
    production_repo: Path,
    worktree: Path,
) -> str:
    allowed = "\n".join(
        f"- {prefix}" for prefix in job.allowed_paths
    )
    tests = "\n".join(
        f"- {target}" for target in job.pytest_targets
    ) or "- worker will run compile checks; no explicit pytest target supplied"

    return f"""You are Empire Coder running through Hermes in a governed isolated worktree.

JOB
id: {job.job_id}
authority: {job.authority}
base branch: {job.base_branch}

WORKSPACE
Editable isolated worktree: {worktree}
Production repo is READ-ONLY context: {production_repo}
Production runtime is READ-ONLY context: {production_repo / 'runtime'}

MANDATORY RULES
- Work only inside the isolated worktree.
- Do not use sudo.
- Do not run systemctl start/stop/restart/enable/disable.
- Do not send email, SMS, voice calls, webhooks, messages, or public posts.
- Do not create payment requests, move funds, sign agreements, recognize revenue, or change accounting truth.
- Do not apply database migrations or execute mutating SQL against production.
- Do not change execution authority or autonomous mode.
- Do not touch recovery/, toop/, runtime/, .git/, .env, credentials, secrets, SSH config, or Hermes auth/config.
- Do not push, merge, rebase, tag, or alter remote git refs. The worker handles git publication after verification.
- Unknown remains unknown. Do not fabricate production data, customers, revenue, test results, or external evidence.
- You may inspect read-only production runtime evidence when useful.
- Make the smallest production-quality implementation that satisfies the task.
- Run relevant local tests when possible. If a test fails, diagnose and fix within the allowed scope.
- Finish with a concise summary of changed files, tests run, unresolved risks, and any founder gate that remains.

ALLOWED EDIT PATHS
{allowed}

PYTHON / TEST ENVIRONMENT
Use {production_repo / '.venv/bin/python'} for Python/pytest.
Use PYTHONPATH={worktree} when running EmpireOS code from this worktree.

WORKER VERIFICATION TARGETS
{tests}

TASK
{job.prompt}
"""


DEFAULT_OMNIROUTE_MODEL_CANDIDATES = (
    "openrouter/openrouter/free",
    "openrouter/deepseek/deepseek-v4-flash-0731:free",
)

MAX_DISCOVERED_MODEL_CANDIDATES = 4
MAX_COOLDOWN_RETRY_SECONDS = 30


def _is_zero_cost_model(model: str) -> bool:
    lower = str(model or "").strip().lower()
    return (
        lower == "openrouter/openrouter/free"
        or (
            lower.startswith("openrouter/")
            and lower.endswith(":free")
        )
    )


def _fetch_omniroute_catalog(
    *,
    base_url: str,
    api_key: str,
    timeout: int = 10,
) -> tuple[str, ...]:
    """Return model IDs advertised by the live OmniRoute OpenAI API."""
    url = base_url.rstrip("/") + "/models"
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                return ()
            body = json.loads(response.read().decode("utf-8", "replace") or "{}")
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        json.JSONDecodeError,
    ):
        return ()

    data = body.get("data")
    if not isinstance(data, list):
        return ()
    models: list[str] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        model_id = str(row.get("id") or "").strip()
        if model_id and model_id not in models:
            models.append(model_id)
    return tuple(models)


def _rank_catalog_candidates(
    catalog: Iterable[str],
    preferred: Iterable[str],
    *,
    allow_paid: bool = False,
) -> tuple[str, ...]:
    """Rank live OmniRoute IDs; paid models require explicit opt-in."""
    live = tuple(
        dict.fromkeys(
            str(model).strip()
            for model in catalog
            if str(model).strip()
        )
    )
    live_set = set(live)
    ordered: list[str] = []

    def eligible(model: str) -> bool:
        return _is_zero_cost_model(model) or allow_paid

    def priority(model: str) -> tuple[int, str]:
        lower = model.lower()
        if lower == "openrouter/openrouter/free":
            return (0, lower)
        if _is_zero_cost_model(model):
            coding_markers = (
                "nemotron",
                "north-mini-code",
                "laguna",
                "deepseek",
                "gpt-oss",
            )
            return (
                1 if any(marker in lower for marker in coding_markers) else 2,
                lower,
            )
        return (8, lower)

    for model in preferred:
        model = str(model).strip()
        if (
            model
            and model in live_set
            and model not in ordered
            and eligible(model)
        ):
            ordered.append(model)

    discovered = [
        model
        for model in live
        if model not in ordered and eligible(model)
    ]
    discovered.sort(key=priority)
    ordered.extend(discovered)

    return tuple(ordered[:MAX_DISCOVERED_MODEL_CANDIDATES])


def _probe_omniroute_model(
    *,
    base_url: str,
    api_key: str,
    model: str,
    timeout: int = 15,
) -> tuple[bool, str]:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": "Reply exactly OK.",
                }
            ],
            "max_tokens": 8,
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    request = urllib.request.Request(
        url,
        data=payload,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
            if response.status != 200:
                return False, f"http_{response.status}"
            try:
                body = json.loads(raw or "{}")
            except json.JSONDecodeError:
                return False, "invalid_json"
            choices = body.get("choices")
            if not isinstance(choices, list) or not choices:
                return False, "missing_choices"
            return True, "ok"
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        safe = re.sub(
            r"(?i)(api[_-]?key|token|secret)[^\s,;]*",
            "[REDACTED]",
            raw,
        )
        return False, f"http_{exc.code}:{safe[:240]}"
    except (urllib.error.URLError, TimeoutError) as exc:
        return False, f"network:{type(exc).__name__}"


def _select_omniroute_model(
    env: Mapping[str, str],
) -> tuple[str, list[dict[str, str]]]:
    base_url = str(env.get("OPENAI_BASE_URL") or "").strip()
    api_key = str(env.get("OPENAI_API_KEY") or "").strip()
    configured = str(
        os.environ.get("EMPIRE_HERMES_MODEL_CANDIDATES") or ""
    ).strip()
    preferred = tuple(
        item.strip()
        for item in configured.split(",")
        if item.strip()
    ) or DEFAULT_OMNIROUTE_MODEL_CANDIDATES

    allow_paid = str(
        os.environ.get("EMPIRE_HERMES_ALLOW_PAID_MODELS") or ""
    ).strip().lower() in {"1", "true", "yes", "on"}

    catalog = _fetch_omniroute_catalog(
        base_url=base_url,
        api_key=api_key,
    )
    if catalog:
        candidates = _rank_catalog_candidates(
            catalog,
            preferred,
            allow_paid=allow_paid,
        )
    else:
        candidates = tuple(
            model
            for model in preferred
            if allow_paid or _is_zero_cost_model(model)
        )

    if not candidates:
        raise HermesControlError(
            "OmniRoute has no eligible zero-cost Hermes model candidates; "
            "paid inference remains disabled"
        )

    def cooldown_seconds(reason: str) -> int | None:
        if "http_429" not in reason or "model_cooldown" not in reason:
            return None
        match = re.search(r'"reset_seconds"\s*:\s*(\d+)', reason)
        if not match:
            return 5
        return max(
            1,
            min(int(match.group(1)), MAX_COOLDOWN_RETRY_SECONDS),
        )

    attempts: list[dict[str, str]] = []
    for index, model in enumerate(candidates):
        ok, reason = _probe_omniroute_model(
            base_url=base_url,
            api_key=api_key,
            model=model,
        )
        attempts.append(
            {
                "model": model,
                "ok": "true" if ok else "false",
                "reason": reason,
            }
        )
        if ok:
            return model, attempts

        # openrouter/free already routes across the available free pool. If
        # OmniRoute says that router is cooling down, hammering every concrete
        # :free model immediately just cascades the same cooldown across the
        # catalog. Honor one bounded retry, then fail fast if the router remains
        # in model_cooldown. Specific free fallbacks are still used for genuine
        # non-cooldown failures such as timeouts.
        if index == 0 and model == "openrouter/openrouter/free":
            delay = cooldown_seconds(reason)
            if delay is not None:
                time.sleep(delay + 1)
                retry_ok, retry_reason = _probe_omniroute_model(
                    base_url=base_url,
                    api_key=api_key,
                    model=model,
                )
                attempts.append(
                    {
                        "model": model,
                        "ok": "true" if retry_ok else "false",
                        "reason": retry_reason,
                        "retry": "cooldown_once",
                    }
                )
                if retry_ok:
                    return model, attempts
                if cooldown_seconds(retry_reason) is not None:
                    raise HermesControlError(
                        "OpenRouter free router remains in model cooldown after "
                        "one bounded retry; skipped free-model fan-out to avoid "
                        "extending provider cooldowns"
                    )

    raise HermesControlError(
        "no healthy OmniRoute model candidate; "
        + "; ".join(
            f"{row['model']}={row['reason']}"
            for row in attempts
        )
    )


def _write_isolated_hermes_config(
    *,
    production_repo: Path,
    env: Mapping[str, str],
    model: str,
) -> Path | None:
    """Create a worker-only Hermes home for the local OmniRoute endpoint.

    Hermes' global user config may point at an unrelated provider. The resident
    worker must be deterministic, so when the systemd service supplies the local
    OpenAI-compatible endpoint we write a minimal config under protected runtime
    storage and set HERMES_HOME to it. The API key never enters Git.
    """
    base_url = str(env.get("OPENAI_BASE_URL") or "").strip()
    api_key = str(env.get("OPENAI_API_KEY") or "").strip()
    if not base_url:
        return None

    hermes_home = production_repo / "runtime/hermes_control/hermes_home"
    hermes_home.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(hermes_home, 0o700)
    except OSError:
        pass

    config_path = hermes_home / "config.yaml"
    payload = {
        "model": {
            "provider": "custom",
            "default": model,
            "base_url": base_url,
            "api_mode": "chat_completions",
            # Bound governed worker generations. Older Hermes builds honor
            # max_tokens directly; context_length also prevents an accidental
            # 131k output ceiling from being inferred through custom gateways.
            "context_length": 32768,
            "max_tokens": 4096,
        }
    }
    if api_key:
        payload["model"]["api_key"] = api_key

    config_path.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        os.chmod(config_path, 0o600)
    except OSError:
        pass
    return hermes_home


def _redact_hermes_output(text: str, env: Mapping[str, str]) -> str:
    clean = str(text or "")
    for key in ("OPENAI_API_KEY",):
        secret = str(env.get(key) or "")
        if secret:
            clean = clean.replace(secret, "[REDACTED]")
    return clean


def run_hermes(
    job: HermesJob,
    *,
    production_repo: Path,
    worktree: Path,
) -> dict[str, Any]:
    hermes_bin = (
        os.environ.get("EMPIRE_HERMES_BIN")
        or shutil.which("hermes")
    )
    if not hermes_bin:
        raise HermesControlError("hermes executable not found")

    env = _hermes_environment()
    env["PYTHONUNBUFFERED"] = "1"

    base_url = str(env.get("OPENAI_BASE_URL") or "").strip()
    # OmniRoute is itself the quota-aware routing layer. Do not pre-probe
    # provider models here: that duplicates routing, consumes free-tier quota,
    # and can extend provider cooldowns. One governed Hermes request goes to
    # OmniRoute model=auto and OmniRoute owns provider/model fallback.
    model_attempts: list[dict[str, str]] = []
    selected_model = str(
        os.environ.get("EMPIRE_HERMES_MODEL") or "auto"
    ).strip() or "auto"

    isolated_home = _write_isolated_hermes_config(
        production_repo=production_repo,
        env=env,
        model=selected_model,
    )
    if isolated_home is not None:
        env["HERMES_HOME"] = str(isolated_home)
        provider = "custom"
        model = selected_model
        endpoint_mode = "isolated_omniroute_auto"
    else:
        provider = str(
            os.environ.get("EMPIRE_HERMES_PROVIDER")
            or "openai-api"
        ).strip()
        model = str(
            os.environ.get("EMPIRE_HERMES_MODEL")
            or "auto"
        ).strip()
        endpoint_mode = "ambient_provider"

        if (
            provider == "custom"
            and str(os.environ.get("OPENAI_BASE_URL") or "").strip()
        ):
            provider = "openai-api"

    args = [
        hermes_bin,
        "chat",
        "--provider",
        provider,
        "--model",
        model,
        "--oneshot",
        "--source",
        "tool",
        "--toolsets",
        "terminal,skills",
        "-q",
        build_hermes_prompt(
            job,
            production_repo=production_repo,
            worktree=worktree,
        ),
    ]

    started = _utc_now()
    process = subprocess.Popen(
        args,
        cwd=str(worktree),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        output, _ = process.communicate(
            timeout=job.max_runtime_seconds
        )
    except subprocess.TimeoutExpired as exc:
        process.terminate()
        try:
            output, _ = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            output, _ = process.communicate(timeout=10)
        raise HermesControlError(
            f"Hermes timed out after {job.max_runtime_seconds}s; "
            f"output_tail={_redact_hermes_output(output, env)[-4000:]}"
        ) from exc

    clean_output = _redact_hermes_output(output, env)
    return {
        "started_at": started,
        "completed_at": _utc_now(),
        "returncode": process.returncode,
        "output_tail": clean_output[-12000:],
        "endpoint_mode": endpoint_mode,
        "provider": provider,
        "model": model,
        "hermes_home_isolated": isolated_home is not None,
        "model_probe_attempts": model_attempts,
    }

def run_verification(
    job: HermesJob,
    *,
    production_repo: Path,
    worktree: Path,
    changed_paths: Iterable[str],
) -> dict[str, Any]:
    changed = list(changed_paths)
    checks: list[dict[str, Any]] = []

    python_bin = str(production_repo / ".venv/bin/python")
    verify_env = dict(os.environ)
    verify_env["PYTHONPATH"] = str(worktree)

    python_files = [
        path for path in changed if path.endswith(".py")
    ]
    if python_files:
        result = _run(
            [
                python_bin,
                "-m",
                "py_compile",
                *python_files,
            ],
            cwd=worktree,
            env=verify_env,
            timeout=180,
            check=False,
        )
        checks.append({
            "name": "py_compile",
            "returncode": result.returncode,
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-4000:],
        })

    if job.pytest_targets:
        result = _run(
            [
                python_bin,
                "-m",
                "pytest",
                "-q",
                *job.pytest_targets,
            ],
            cwd=worktree,
            env=verify_env,
            timeout=min(job.max_runtime_seconds, 900),
            check=False,
        )
        checks.append({
            "name": "pytest",
            "targets": list(job.pytest_targets),
            "returncode": result.returncode,
            "stdout": result.stdout[-8000:],
            "stderr": result.stderr[-8000:],
        })

    passed = all(
        check["returncode"] == 0 for check in checks
    )
    return {
        "passed": passed,
        "checks": checks,
    }


def _add_explicit_paths(
    worktree: Path,
    changed_paths: Iterable[str],
) -> None:
    for path in changed_paths:
        _git(
            worktree,
            "add",
            "-A",
            "--",
            path,
        )


def publish_proposal_branch(
    job: HermesJob,
    *,
    worktree: Path,
    changed_paths: Iterable[str],
    remote: str = DEFAULT_REMOTE,
) -> dict[str, Any]:
    branch = f"hermes/job-{job.job_id}"
    _git(
        worktree,
        "switch",
        "-C",
        branch,
    )
    _add_explicit_paths(worktree, changed_paths)
    _git(
        worktree,
        "-c",
        "user.name=Empire Hermes",
        "-c",
        "user.email=hermes@empire-ai.co.uk",
        "commit",
        "-m",
        f"Hermes proposal: {job.job_id}",
    )
    sha = _git(worktree, "rev-parse", "HEAD").stdout.strip()
    _git(
        worktree,
        "push",
        remote,
        f"HEAD:refs/heads/{branch}",
        timeout=180,
    )
    return {
        "proposal_branch": branch,
        "proposal_commit": sha,
    }


def _publish_result_once(
    repo_root: Path,
    result_payload: Mapping[str, Any],
    *,
    control_branch: str,
    remote: str,
    runtime_root: Path,
) -> None:
    job_id = str(result_payload["job_id"])
    result_root = Path(
        tempfile.mkdtemp(
            prefix="control-result-",
            dir=runtime_root,
        )
    )
    worktree = result_root / "worktree"
    try:
        _git(
            repo_root,
            "fetch",
            remote,
            f"{control_branch}:refs/remotes/{remote}/{control_branch}",
        )
        _git(
            repo_root,
            "worktree",
            "add",
            "--detach",
            str(worktree),
            f"{remote}/{control_branch}",
        )
        path = worktree / RESULT_PATH_PREFIX / f"{job_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                dict(result_payload),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        _git(
            worktree,
            "add",
            "--",
            str(
                Path(RESULT_PATH_PREFIX) / f"{job_id}.json"
            ),
        )
        _git(
            worktree,
            "-c",
            "user.name=Empire Hermes",
            "-c",
            "user.email=hermes@empire-ai.co.uk",
            "commit",
            "-m",
            f"Hermes result: {job_id}",
        )
        _git(
            worktree,
            "push",
            remote,
            f"HEAD:refs/heads/{control_branch}",
            timeout=180,
        )
    finally:
        _git(
            repo_root,
            "worktree",
            "remove",
            "--force",
            str(worktree),
            check=False,
        )
        shutil.rmtree(result_root, ignore_errors=True)


def publish_result(
    repo_root: Path,
    result_payload: Mapping[str, Any],
    *,
    control_branch: str = DEFAULT_CONTROL_BRANCH,
    remote: str = DEFAULT_REMOTE,
    runtime_root: Path,
) -> None:
    last_error: Exception | None = None
    for _ in range(3):
        try:
            _publish_result_once(
                repo_root,
                result_payload,
                control_branch=control_branch,
                remote=remote,
                runtime_root=runtime_root,
            )
            return
        except Exception as exc:  # retry only publication race/errors
            last_error = exc
    raise HermesControlError(
        f"failed to publish result after retries: {last_error}"
    )


def process_job(
    repo_root: Path,
    job_path: str,
    *,
    runtime_root: Path,
    control_branch: str = DEFAULT_CONTROL_BRANCH,
    remote: str = DEFAULT_REMOTE,
) -> dict[str, Any]:
    raw = read_control_json(
        repo_root,
        job_path,
        control_branch=control_branch,
        remote=remote,
    )
    job = HermesJob.from_mapping(raw)

    result_path = (
        RESULT_PATH_PREFIX + f"{job.job_id}.json"
    )
    if control_path_exists(
        repo_root,
        result_path,
        control_branch=control_branch,
        remote=remote,
    ):
        return {
            "job_id": job.job_id,
            "skipped": True,
            "reason": "result_already_exists",
        }

    job_root = runtime_root / "jobs" / job.job_id
    worktree = job_root / "worktree"
    _prepare_worktree_slot(repo_root, worktree)
    shutil.rmtree(job_root, ignore_errors=True)
    job_root.mkdir(parents=True, exist_ok=True)

    lease = None
    result: dict[str, Any] = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "job_id": job.job_id,
        "job_path": job_path,
        "kind": job.kind,
        "authority": job.authority,
        "base_branch": job.base_branch,
        "started_at": _utc_now(),
        "status": "FAILED",
        "proposal_branch": None,
        "proposal_commit": None,
        "changed_paths": [],
        "verification": None,
        "hermes": None,
        "lease_id": None,
        "founder_gate_required": False,
        "external_commercial_action_performed": False,
        "git_remote_io_performed": True,
        "database_mutation_performed": False,
        "payment_action_performed": False,
        "execution_authority": "none",
    }

    try:
        lease_manager = ExecutionLeaseManager()
        lease = lease_manager.acquire(
            owner="hermes",
            job_id=job.job_id,
            resources=job.lease_resources,
            ttl_seconds=job.max_runtime_seconds + 300,
        )
        result["lease_id"] = lease.lease_id

        fetch_control_refs(
            repo_root,
            control_branch=control_branch,
            base_branch=job.base_branch,
            remote=remote,
        )
        _git(
            repo_root,
            "worktree",
            "add",
            "--detach",
            str(worktree),
            f"{remote}/{job.base_branch}",
        )

        hermes_result = run_hermes(
            job,
            production_repo=repo_root,
            worktree=worktree,
        )
        result["hermes"] = hermes_result

        changed = validate_changed_paths(
            _changed_paths(worktree),
            allowed_paths=job.allowed_paths,
        )
        result["changed_paths"] = changed

        if hermes_result["returncode"] != 0:
            result["status"] = "HERMES_FAILED"
        elif not changed:
            result["status"] = "COMPLETED_NO_CHANGES"
        else:
            verification = run_verification(
                job,
                production_repo=repo_root,
                worktree=worktree,
                changed_paths=changed,
            )
            result["verification"] = verification
            if not verification["passed"]:
                result["status"] = "VERIFICATION_FAILED"
            else:
                proposal = publish_proposal_branch(
                    job,
                    worktree=worktree,
                    changed_paths=changed,
                    remote=remote,
                )
                result.update(proposal)
                result["status"] = "PROPOSAL_READY"

    except ExecutionLeaseError as exc:
        result["error"] = f"ExecutionLeaseError: {exc}"
        result["status"] = "LEASE_BLOCKED"
    except Exception as exc:
        result["error"] = (
            f"{type(exc).__name__}: {exc}"
        )[-10_000:]
        result["status"] = "FAILED"
    finally:
        if lease is not None:
            try:
                ExecutionLeaseManager().release(lease.lease_id)
            except Exception:
                pass
        result["completed_at"] = _utc_now()
        _git(
            repo_root,
            "worktree",
            "remove",
            "--force",
            str(worktree),
            check=False,
        )
        shutil.rmtree(job_root, ignore_errors=True)

    publish_result(
        repo_root,
        result,
        control_branch=control_branch,
        remote=remote,
        runtime_root=runtime_root,
    )
    return result


def run_worker(
    repo_root: Path,
    *,
    control_branch: str = DEFAULT_CONTROL_BRANCH,
    remote: str = DEFAULT_REMOTE,
    max_jobs: int = 1,
) -> dict[str, Any]:
    runtime_root = repo_root / "runtime/hermes_control"
    runtime_root.mkdir(parents=True, exist_ok=True)

    fetch_control_refs(
        repo_root,
        control_branch=control_branch,
        base_branch=DEFAULT_BASE_BRANCH,
        remote=remote,
    )
    paths = list_pending_job_paths(
        repo_root,
        control_branch=control_branch,
        remote=remote,
    )

    processed: list[dict[str, Any]] = []
    skipped = 0
    for path in paths:
        raw = read_control_json(
            repo_root,
            path,
            control_branch=control_branch,
            remote=remote,
        )
        job_id = str(raw.get("job_id") or "").strip()
        if (
            job_id
            and control_path_exists(
                repo_root,
                RESULT_PATH_PREFIX + f"{job_id}.json",
                control_branch=control_branch,
                remote=remote,
            )
        ):
            skipped += 1
            continue
        processed.append(
            process_job(
                repo_root,
                path,
                runtime_root=runtime_root,
                control_branch=control_branch,
                remote=remote,
            )
        )
        if len(processed) >= max(1, min(int(max_jobs), 3)):
            break

    summary = {
        "schema_version": "empire.hermes.worker_run.v1",
        "generated_at": _utc_now(),
        "control_branch": control_branch,
        "job_path_count": len(paths),
        "already_completed_count": skipped,
        "processed_count": len(processed),
        "processed": processed,
        "external_commercial_action_performed": False,
        "git_remote_io_performed": True,
        "production_merge_performed": False,
        "database_mutation_performed": False,
        "payment_action_performed": False,
        "execution_authority": "none",
    }
    (runtime_root / "latest.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary
