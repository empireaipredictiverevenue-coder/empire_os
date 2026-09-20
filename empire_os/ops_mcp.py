"""Empire-owned remote operations MCP.

Loopback by default. Exposes narrow, audited tools instead of a general shell.
Privileged system actions are intentionally not implemented here; they belong
behind the separate root-owned helper.
"""
from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from empire_os.lead_sources.overpass import METRO_COORDS
from empire_os.ops_core import (
    audit,
    env_key_status,
    git_diff,
    git_log,
    git_status,
    read_repo_file,
    run_command,
    service_status,
    write_repo_file,
)

server = MCPServer(
    name="empire_ops_mcp",
    title="Empire Ops MCP",
    description="Audited server-native operations for EmpireOS.",
    version="0.1.0",
    instructions=(
        "Operate only within the EmpireOS repository and explicit allowlists. "
        "Never treat tool output as commercial truth unless backed by canonical evidence."
    ),
)


def _request_id() -> str:
    return uuid.uuid4().hex


def _record(tool: str, args: dict[str, Any], fn):
    rid = _request_id()
    try:
        result = fn()
        audit(tool, request_id=rid, arguments=args, outcome="ok")
        if isinstance(result, dict):
            return {"request_id": rid, **result}
        return {"request_id": rid, "result": result}
    except Exception as exc:
        audit(tool, request_id=rid, arguments=args, outcome=f"error:{type(exc).__name__}")
        raise


@server.tool(name="empire_ops_health", structured_output=True)
def ops_health() -> dict[str, Any]:
    return _record(
        "empire_ops_health",
        {},
        lambda: {
            "ok": True,
            "service": "empire-ops-mcp",
            "version": "0.1.0",
            "repo": "/srv/empire_os",
            "privileged_helper": False,
            "general_shell": False,
        },
    )


@server.tool(name="empire_repo_status", structured_output=True)
def repo_status() -> dict[str, Any]:
    return _record("empire_repo_status", {}, git_status)


@server.tool(name="empire_repo_log", structured_output=True)
def repo_log(limit: int = 8) -> dict[str, Any]:
    return _record(
        "empire_repo_log",
        {"limit": limit},
        lambda: git_log(limit),
    )


@server.tool(name="empire_repo_diff", structured_output=True)
def repo_diff(path: str = "", staged: bool = False) -> dict[str, Any]:
    return _record(
        "empire_repo_diff",
        {"path": path, "staged": staged},
        lambda: git_diff(path or None, staged=staged),
    )


@server.tool(name="empire_file_read", structured_output=True)
def file_read(path: str, offset: int = 0, limit: int = 40000) -> dict[str, Any]:
    return _record(
        "empire_file_read",
        {"path": path, "offset": offset, "limit": limit},
        lambda: read_repo_file(path, offset=offset, limit=limit),
    )


@server.tool(name="empire_file_write", structured_output=True)
def file_write(path: str, content: str, append: bool = False) -> dict[str, Any]:
    return _record(
        "empire_file_write",
        {"path": path, "append": append, "content_chars": len(content)},
        lambda: write_repo_file(path, content, append=append),
    )


@server.tool(name="empire_service_status", structured_output=True)
def system_service_status(unit: str) -> dict[str, Any]:
    return _record(
        "empire_service_status",
        {"unit": unit},
        lambda: service_status(unit),
    )


@server.tool(name="empire_env_key_status", structured_output=True)
def environment_key_status(keys: list[str]) -> dict[str, Any]:
    return _record(
        "empire_env_key_status",
        {"keys": keys},
        lambda: {"keys": env_key_status(keys)},
    )


@server.tool(name="empire_run_check", structured_output=True)
def run_check(check: str, target: str = "") -> dict[str, Any]:
    allowed = {
        "git_diff_check": lambda: run_command(["git", "diff", "--check"]),
        "pytest_file": lambda: run_command(
            [
                "/srv/empire_os/.venv/bin/python",
                "-m",
                "pytest",
                "-q",
                str(Path(target)),
            ],
            timeout=120,
        ),
        "python_compile": lambda: run_command(
            [
                "/srv/empire_os/.venv/bin/python",
                "-m",
                "py_compile",
                str(Path(target)),
            ],
            timeout=30,
        ),
    }
    if check not in allowed:
        raise ValueError("check not allowlisted")
    if check in {"pytest_file", "python_compile"}:
        from empire_os.ops_core import safe_repo_path
        safe_repo_path(target)
    return _record(
        "empire_run_check",
        {"check": check, "target": target},
        allowed[check],
    )


@server.tool(name="empire_acquisition_run", structured_output=True)
def acquisition_run(
    metro: str,
    max_candidates: int = 10,
    dry_run: bool = False,
) -> dict[str, Any]:
    if metro not in METRO_COORDS:
        raise ValueError("unsupported metro")
    if max_candidates < 1 or max_candidates > 25:
        raise ValueError("max_candidates must be between 1 and 25")
    args = [
        "/srv/empire_os/.venv/bin/python",
        "-m",
        "empire_os.crawler_runner",
        "--source",
        "overpass",
        "--metro",
        metro,
        "--max-candidates",
        str(max_candidates),
    ]
    if dry_run:
        args.append("--dry-run")
    return _record(
        "empire_acquisition_run",
        {
            "metro": metro,
            "max_candidates": max_candidates,
            "dry_run": dry_run,
        },
        lambda: run_command(args, timeout=600),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="streamable-http",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if args.transport == "stdio":
        server.run(transport="stdio")
        return

    server.run(
        transport="streamable-http",
        host=args.host,
        port=args.port,
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
    )


if __name__ == "__main__":
    main()
