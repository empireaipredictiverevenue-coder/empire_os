"""Empire Remote Commander core.

One audited, transport-independent command surface for EmpireOS.

Primary transport: Empire Ops MCP.
Fallback transport: governed GitHub/Hermes control branch.
No unrestricted shell is exposed. All operations are typed and allowlisted.
"""
from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Any

from empire_os.founder_directives import FounderDirectiveStore
from empire_os.ops_core import (
    ALLOWED_UNITS,
    OpsPolicyError,
    env_key_status,
    git_diff,
    git_log,
    git_status,
    read_repo_file,
    run_command,
    safe_repo_path,
    service_status,
    write_repo_file,
)

REPO = Path("/srv/empire_os").resolve()

READ_OPERATIONS = frozenset({
    "health",
    "repo_status",
    "repo_log",
    "repo_diff",
    "directory_list",
    "repo_search",
    "file_read",
    "run_check",
    "service_status",
    "journal_tail",
    "runtime_health",
    "env_key_status",
})
WRITE_OPERATIONS = frozenset({
    "file_write",
    "founder_directive_ingest",
})
OPERATIONS = READ_OPERATIONS | WRITE_OPERATIONS

ALLOWED_CHECKS = frozenset({
    "git_diff_check",
    "pytest_file",
    "python_compile",
})

SEARCH_SUFFIXES = frozenset({
    ".py", ".md", ".json", ".toml", ".yaml", ".yml",
    ".service", ".timer", ".sh", ".sql", ".txt",
})
MAX_SEARCH_FILES = 4000
MAX_SEARCH_MATCHES = 200


class RemoteCommanderError(ValueError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def health() -> dict[str, Any]:
    disk = shutil.disk_usage(REPO)
    return {
        "ok": True,
        "service": "empire-remote-commander",
        "version": "1.0.0",
        "repo": str(REPO),
        "general_shell": False,
        "typed_operations": sorted(OPERATIONS),
        "protected_paths": ["recovery/", "toop/"],
        "disk": {
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
        },
    }


def directory_list(path: str = "", limit: int = 200) -> dict[str, Any]:
    target = REPO if not str(path or "").strip() else safe_repo_path(path)
    if not target.is_dir():
        raise RemoteCommanderError("directory not found")
    rows: list[dict[str, Any]] = []
    for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if len(rows) >= max(1, min(int(limit), 1000)):
            break
        try:
            stat = item.stat()
        except OSError:
            continue
        rows.append({
            "name": item.name,
            "path": str(item.relative_to(REPO)),
            "type": "directory" if item.is_dir() else "file",
            "size_bytes": stat.st_size if item.is_file() else None,
            "modified_ns": stat.st_mtime_ns,
        })
    return {
        "ok": True,
        "path": "." if target == REPO else str(target.relative_to(REPO)),
        "entries": rows,
        "count": len(rows),
    }


def repo_search(
    query: str,
    path: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    needle = str(query or "")
    if not needle:
        raise RemoteCommanderError("search query required")
    root = REPO if not str(path or "").strip() else safe_repo_path(path)
    if not root.exists():
        raise RemoteCommanderError("search path not found")

    matches: list[dict[str, Any]] = []
    files_seen = 0
    candidates = [root] if root.is_file() else root.rglob("*")
    for candidate in candidates:
        if files_seen >= MAX_SEARCH_FILES or len(matches) >= min(int(limit), MAX_SEARCH_MATCHES):
            break
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() not in SEARCH_SUFFIXES:
            continue
        try:
            safe_repo_path(str(candidate.relative_to(REPO)))
        except OpsPolicyError:
            continue
        files_seen += 1
        try:
            lines = candidate.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line_no, line in enumerate(lines, start=1):
            if needle.lower() not in line.lower():
                continue
            matches.append({
                "path": str(candidate.relative_to(REPO)),
                "line": line_no,
                "text": line[:1200],
            })
            if len(matches) >= min(int(limit), MAX_SEARCH_MATCHES):
                break
    return {
        "ok": True,
        "query": needle,
        "path": "." if root == REPO else str(root.relative_to(REPO)),
        "files_scanned": files_seen,
        "matches": matches,
        "count": len(matches),
        "truncated": files_seen >= MAX_SEARCH_FILES or len(matches) >= min(int(limit), MAX_SEARCH_MATCHES),
    }


def file_write(
    path: str,
    content: str,
    *,
    append: bool = False,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    target = safe_repo_path(path)
    if target.exists() and target.is_file():
        current_sha = _sha256(target)
    elif target.exists():
        raise RemoteCommanderError("target is not a file")
    else:
        current_sha = None

    if expected_sha256 is not None and str(expected_sha256) != str(current_sha):
        raise RemoteCommanderError("file sha256 mismatch")

    result = write_repo_file(path, content, append=append)
    target = safe_repo_path(path)
    return {
        **result,
        "sha256": _sha256(target),
        "previous_sha256": current_sha,
    }


def run_check(check: str, target: str = "") -> dict[str, Any]:
    name = str(check or "").strip()
    if name not in ALLOWED_CHECKS:
        raise RemoteCommanderError("check not allowlisted")

    if name == "git_diff_check":
        return run_command(["git", "diff", "--check"])

    safe_repo_path(target)
    if name == "pytest_file":
        return run_command(
            [
                str(REPO / ".venv/bin/python"),
                "-m",
                "pytest",
                "-q",
                target,
            ],
            timeout=180,
        )

    return run_command(
        [
            str(REPO / ".venv/bin/python"),
            "-m",
            "py_compile",
            target,
        ],
        timeout=60,
    )


def journal_tail(unit: str, lines: int = 120) -> dict[str, Any]:
    if unit not in ALLOWED_UNITS:
        raise RemoteCommanderError("unit not allowlisted")
    count = max(1, min(int(lines), 500))
    return run_command(
        [
            "journalctl",
            "--no-pager",
            "-u",
            unit,
            "-n",
            str(count),
            "--output=short-iso",
        ],
        timeout=20,
    )


def runtime_health() -> dict[str, Any]:
    units: list[dict[str, Any]] = []
    for unit in sorted(ALLOWED_UNITS):
        result = service_status(unit)
        units.append({
            "unit": unit,
            "ok": bool(result.get("ok")),
            "state": str(result.get("stdout") or "").strip(),
        })
    branch = run_command(["git", "branch", "--show-current"])
    head = run_command(["git", "rev-parse", "HEAD"])
    dirty = git_status()
    return {
        "ok": all(row["ok"] for row in units),
        "branch": str(branch.get("stdout") or "").strip(),
        "head": str(head.get("stdout") or "").strip(),
        "git_status": str(dirty.get("stdout") or ""),
        "services": units,
        "general_shell": False,
    }


def founder_directive_ingest(
    text: str,
    *,
    title: str = "",
    priority: int = 90,
    source: str = "remote_commander",
) -> dict[str, Any]:
    if priority < 0 or priority > 100:
        raise RemoteCommanderError("priority must be between 0 and 100")
    clean = str(text or "").strip()
    if not clean:
        raise RemoteCommanderError("directive text required")
    directive, created = FounderDirectiveStore(REPO).ingest(
        clean,
        source=source,
        title=title or None,
        priority=priority,
        metadata={"ingested_via": "empire_remote_commander"},
    )
    return {
        "ok": True,
        "created": created,
        "directive": directive.as_dict(),
        "planning_automatic": True,
        "production_execution_automatic": False,
    }


def execute(
    operation: str,
    arguments: dict[str, Any] | None = None,
    *,
    allow_write: bool = False,
    allowed_paths: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    op = str(operation or "").strip()
    args = dict(arguments or {})
    if op not in OPERATIONS:
        raise RemoteCommanderError("operation not allowlisted")
    if op in WRITE_OPERATIONS and not allow_write:
        raise RemoteCommanderError("write operation requires internal_write authority")

    if op == "health":
        return health()
    if op == "repo_status":
        return git_status()
    if op == "repo_log":
        return git_log(int(args.get("limit", 8)))
    if op == "repo_diff":
        return git_diff(
            str(args.get("path") or "") or None,
            staged=bool(args.get("staged", False)),
        )
    if op == "directory_list":
        return directory_list(
            str(args.get("path") or ""),
            int(args.get("limit", 200)),
        )
    if op == "repo_search":
        return repo_search(
            str(args.get("query") or ""),
            str(args.get("path") or ""),
            int(args.get("limit", 100)),
        )
    if op == "file_read":
        return read_repo_file(
            str(args.get("path") or ""),
            offset=int(args.get("offset", 0)),
            limit=min(int(args.get("limit", 40000)), 100000),
        )
    if op == "file_write":
        path = str(args.get("path") or "")
        if allowed_paths is not None:
            relative = str(safe_repo_path(path).relative_to(REPO))
            allowed = tuple(str(p) for p in allowed_paths)
            if not any(
                relative == prefix.rstrip("/")
                or (
                    prefix.endswith("/")
                    and relative.startswith(prefix)
                )
                for prefix in allowed
            ):
                raise RemoteCommanderError("file write is outside requested job scope")
        return file_write(
            path,
            str(args.get("content") or ""),
            append=bool(args.get("append", False)),
            expected_sha256=(
                str(args["expected_sha256"])
                if args.get("expected_sha256") is not None
                else None
            ),
        )
    if op == "run_check":
        return run_check(
            str(args.get("check") or ""),
            str(args.get("target") or ""),
        )
    if op == "service_status":
        return service_status(str(args.get("unit") or ""))
    if op == "journal_tail":
        return journal_tail(
            str(args.get("unit") or ""),
            int(args.get("lines", 120)),
        )
    if op == "runtime_health":
        return runtime_health()
    if op == "env_key_status":
        keys = args.get("keys") or []
        if not isinstance(keys, list):
            raise RemoteCommanderError("keys must be a list")
        return {"keys": env_key_status([str(k) for k in keys])}
    if op == "founder_directive_ingest":
        return founder_directive_ingest(
            str(args.get("text") or ""),
            title=str(args.get("title") or ""),
            priority=int(args.get("priority", 90)),
            source="remote_commander",
        )
    raise RemoteCommanderError("operation not implemented")
