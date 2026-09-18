"""Fail-closed workspace and command policy for Empire Coder."""
from __future__ import annotations

import os
import re
import shlex
from pathlib import Path
from typing import Iterable

from .models import ToolDecision


_SECRET_KEY_RE = re.compile(
    r"(TOKEN|SECRET|PASSWORD|PASSWD|PRIVATE|API[_-]?KEY|SERVICE[_-]?KEY|"
    r"WALLET|SEED|MNEMONIC|DSN)$",
    re.IGNORECASE,
)

PROTECTED_NAMES = frozenset({"recovery", "toop", "tools", ".git"})
SENSITIVE_FILE_PATTERNS = (
    re.compile(r"^\.env(?:\..*)?$", re.IGNORECASE),
    re.compile(r".*\.(?:pem|key|p12|pfx)$", re.IGNORECASE),
    re.compile(r"^(?:credentials?|secrets?)\.(?:json|ya?ml|toml)$", re.IGNORECASE),
    re.compile(r"^id_(?:rsa|ed25519|ecdsa)(?:\.pub)?$", re.IGNORECASE),
)
DENIED_EXECUTABLES = frozenset({
    "rm", "rmdir", "shred", "dd", "mkfs", "mount", "umount",
    "sudo", "su", "systemctl", "service", "reboot", "shutdown",
    "scp", "rsync", "ssh", "curl", "wget", "nc", "ncat", "socat",
    "docker", "podman", "incus", "kubectl", "terraform",
})
READ_ONLY_GIT = frozenset({
    "status", "diff", "log", "show", "rev-parse", "ls-files",
    "grep", "branch",
})
APPROVAL_GIT = frozenset({
    "add", "commit", "push", "merge", "cherry-pick", "rebase",
    "checkout", "switch", "tag",
})
DENIED_GIT = frozenset({"reset", "clean", "gc", "prune"})


class PolicyError(RuntimeError):
    pass



def is_sensitive_path(path: str | Path) -> bool:
    candidate = Path(path)
    return any(
        pattern.fullmatch(candidate.name)
        for pattern in SENSITIVE_FILE_PATTERNS
    )


def resolve_workspace(workspace: str | Path) -> Path:
    root = Path(workspace).expanduser().resolve()
    if not root.is_dir():
        raise PolicyError(f"workspace does not exist: {root}")
    if not (root / ".git").exists() and not _is_git_worktree(root):
        raise PolicyError(f"workspace is not a git worktree: {root}")
    return root


def _is_git_worktree(root: Path) -> bool:
    git_marker = root / ".git"
    return git_marker.is_file()


def resolve_path(
    workspace: str | Path,
    candidate: str | Path,
    *,
    allow_missing: bool = False,
) -> Path:
    root = resolve_workspace(workspace)
    raw = Path(candidate)
    path = raw if raw.is_absolute() else root / raw
    resolved = path.resolve(strict=not allow_missing)
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise PolicyError("path escapes workspace") from exc
    if any(part in PROTECTED_NAMES for part in relative.parts):
        raise PolicyError(f"protected path denied: {relative}")
    if is_sensitive_path(relative):
        raise PolicyError(f"sensitive file denied: {relative}")
    return resolved



def resolve_runtime_root(
    workspace: str | Path,
    runtime_root: str | Path | None = None,
) -> Path:
    root = resolve_workspace(workspace)
    candidate = Path(runtime_root or root / "runtime" / "coder").expanduser()
    resolved = candidate.resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise PolicyError("runtime root must stay inside workspace") from exc
    if any(part in PROTECTED_NAMES for part in relative.parts):
        raise PolicyError("runtime root intersects protected path")
    return resolved


def filtered_environment(
    source: dict[str, str] | None = None,
    *,
    extra_allow: Iterable[str] = (),
) -> dict[str, str]:
    source = dict(source or os.environ)
    allow = {
        "PATH", "HOME", "USER", "LANG", "LC_ALL", "TERM",
        "PYTHONPATH", "VIRTUAL_ENV",
        *extra_allow,
    }
    clean: dict[str, str] = {}
    for key in allow:
        if key in source and not _SECRET_KEY_RE.search(key):
            clean[key] = source[key]
    clean["EMPIRE_EXECUTION_MODE"] = "observe"
    clean["EMPIRE_CODER_MODE"] = "OBSERVE"
    return clean


def classify_command(argv: Iterable[str]) -> ToolDecision:
    args = tuple(str(x) for x in argv)
    if not args:
        return ToolDecision.DENY
    exe = Path(args[0]).name.lower()
    if exe in DENIED_EXECUTABLES:
        return ToolDecision.DENY
    if exe == "git":
        if len(args) < 2:
            return ToolDecision.DENY
        sub = args[1].lower()
        if sub in DENIED_GIT:
            return ToolDecision.DENY
        if sub in APPROVAL_GIT:
            return ToolDecision.REQUIRE_APPROVAL
        if sub == "branch":
            rest = args[2:]
            read_only_flags = {
                "-a", "--all", "-r", "--remotes", "-v", "-vv",
                "--show-current", "--list", "--contains", "--no-contains",
                "--merged", "--no-merged", "--points-at",
            }
            if not rest:
                return ToolDecision.ALLOW
            if all(
                item.startswith("-") or item in read_only_flags
                for item in rest
            ):
                return ToolDecision.ALLOW
            return ToolDecision.REQUIRE_APPROVAL
        return ToolDecision.ALLOW if sub in READ_ONLY_GIT else ToolDecision.DENY
    if exe in {"pytest", "ruff", "mypy", "pyright"}:
        return ToolDecision.ALLOW
    if exe in {"python", "python3"}:
        if len(args) >= 3 and args[1] == "-m":
            module = args[2]
            return (
                ToolDecision.ALLOW
                if module in {"pytest", "py_compile", "compileall"}
                else ToolDecision.REQUIRE_APPROVAL
            )
        return ToolDecision.REQUIRE_APPROVAL
    if exe == "node":
        return (
            ToolDecision.ALLOW
            if len(args) >= 2 and args[1] == "--check"
            else ToolDecision.REQUIRE_APPROVAL
        )
    if exe in {"npm", "pnpm", "yarn"}:
        if len(args) >= 2 and args[1] == "test":
            return ToolDecision.ALLOW
        if len(args) >= 3 and args[1] == "run":
            script = args[2].lower()
            safe_scripts = {
                "test",
                "test:unit",
                "test:integration",
                "lint",
                "typecheck",
                "check",
                "build:check",
            }
            return (
                ToolDecision.ALLOW
                if script in safe_scripts
                else ToolDecision.REQUIRE_APPROVAL
            )
        return ToolDecision.REQUIRE_APPROVAL
    if exe == "npx":
        return ToolDecision.REQUIRE_APPROVAL
    return ToolDecision.DENY


def parse_command(command: str) -> tuple[str, ...]:
    return tuple(shlex.split(command, posix=True))
