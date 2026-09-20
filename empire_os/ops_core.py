"""Core policy and audited operations for Empire Ops MCP."""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path("/srv/empire_os").resolve()
RUNTIME = REPO / "runtime" / "ops_mcp"
AUDIT = RUNTIME / "audit.jsonl"
PROTECTED = (
    (REPO / "recovery").resolve(),
    (REPO / "toop").resolve(),
)
ALLOWED_UNITS = frozenset({
    "empire-autonomous-execution.service",
    "empire-coder-worker.service",
    "empire-coder-worker.timer",
    "empire-desktop-commander.service",
    "empire-acquisition.service",
    "empire-acquisition.timer",
    "empire-public-gateway.service",
})


class OpsPolicyError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_repo_path(relative_path: str) -> Path:
    raw = str(relative_path or "").strip()
    if not raw:
        raise OpsPolicyError("path required")
    p = Path(raw)
    if p.is_absolute():
        raise OpsPolicyError("absolute paths are not allowed")
    resolved = (REPO / p).resolve()
    if resolved != REPO and REPO not in resolved.parents:
        raise OpsPolicyError("path escapes repository")
    for protected in PROTECTED:
        if resolved == protected or protected in resolved.parents:
            raise OpsPolicyError("protected path")
    return resolved


def audit(tool: str, *, request_id: str, arguments: dict[str, Any], outcome: str) -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    safe_args = {
        key: ("[REDACTED]" if "secret" in key.lower() or "token" in key.lower() else value)
        for key, value in arguments.items()
    }
    record = {
        "ts": utc_now(),
        "request_id": request_id,
        "tool": tool,
        "arguments": safe_args,
        "outcome": outcome,
        "pid": os.getpid(),
    }
    with AUDIT.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\n")


def run_command(args: list[str], *, timeout: int = 30) -> dict[str, Any]:
    completed = subprocess.run(
        args,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return {
        "returncode": completed.returncode,
        "stdout": (completed.stdout or "")[-20000:],
        "stderr": (completed.stderr or "")[-10000:],
        "ok": completed.returncode == 0,
    }


def git_status() -> dict[str, Any]:
    return run_command(["git", "status", "--short", "--branch"])


def git_log(limit: int = 8) -> dict[str, Any]:
    limit = max(1, min(int(limit), 50))
    return run_command(["git", "log", f"-{limit}", "--oneline", "--decorate"])


def git_diff(path: str | None = None, *, staged: bool = False) -> dict[str, Any]:
    args = ["git", "diff"]
    if staged:
        args.append("--cached")
    if path:
        safe = safe_repo_path(path)
        args.extend(["--", str(safe.relative_to(REPO))])
    return run_command(args)


def read_repo_file(path: str, *, offset: int = 0, limit: int = 40000) -> dict[str, Any]:
    p = safe_repo_path(path)
    if not p.is_file():
        raise OpsPolicyError("file not found")
    text = p.read_text(encoding="utf-8", errors="replace")
    start = max(0, int(offset))
    size = max(1, min(int(limit), 100000))
    return {
        "path": str(p.relative_to(REPO)),
        "content": text[start:start + size],
        "offset": start,
        "returned_chars": len(text[start:start + size]),
        "total_chars": len(text),
    }


def write_repo_file(path: str, content: str, *, append: bool = False) -> dict[str, Any]:
    p = safe_repo_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with p.open(mode, encoding="utf-8") as fh:
        fh.write(str(content))
    return {
        "path": str(p.relative_to(REPO)),
        "bytes": len(str(content).encode("utf-8")),
        "append": bool(append),
    }


def service_status(unit: str) -> dict[str, Any]:
    if unit not in ALLOWED_UNITS:
        raise OpsPolicyError("unit not allowlisted")
    return run_command(
        ["systemctl", "show", unit, "--property=ActiveState,SubState,UnitFileState"],
        timeout=10,
    )


def env_key_status(keys: list[str]) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for raw in keys[:50]:
        key = str(raw or "").strip()
        if not key or not key.replace("_", "").isalnum():
            raise OpsPolicyError("invalid environment key")
        out[key] = bool(os.environ.get(key))
    return out
