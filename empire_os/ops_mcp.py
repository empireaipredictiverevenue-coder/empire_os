"""Empire-owned remote operations MCP.

Loopback by default. Exposes narrow, audited tools instead of a general shell.
Privileged system actions are intentionally not implemented here; they belong
behind the separate root-owned helper.
"""
from __future__ import annotations

import argparse
import hmac
import json
import os
import uuid
from pathlib import Path
from typing import Any

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from pydantic import AnyHttpUrl

from empire_os.lead_sources.overpass import METRO_COORDS
from empire_os.ops_privileged_client import (
    PrivilegedHelperUnavailable,
    privileged_request,
)
from empire_os.ops_privileged_helper import (
    ALLOWED_UNITS as PRIVILEGED_ALLOWED_UNITS,
    SOCKET_PATH as PRIVILEGED_SOCKET,
)
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

class StaticOpsTokenVerifier(TokenVerifier):
    def __init__(self, token: str, resource: str) -> None:
        self._token = token
        self._resource = resource

    async def verify_token(self, token: str) -> AccessToken | None:
        if not hmac.compare_digest(str(token), self._token):
            return None
        return AccessToken(
            token=token,
            client_id="empire-ops-client",
            scopes=["empire:ops"],
            resource=self._resource,
        )


def _build_server() -> MCPServer:
    common = {
        "name": "empire_ops_mcp",
        "title": "Empire Ops MCP",
        "description": "Audited server-native operations for EmpireOS.",
        "version": "0.2.0",
        "instructions": (
            "Operate only within the EmpireOS repository and explicit allowlists. "
            "Never treat tool output as commercial truth unless backed by canonical evidence."
        ),
    }
    token = os.getenv("EMPIRE_OPS_MCP_BEARER_TOKEN", "").strip()
    if not token:
        return MCPServer(**common)

    resource = os.getenv(
        "EMPIRE_OPS_MCP_RESOURCE_URL",
        "http://127.0.0.1:8765/mcp",
    ).strip()
    issuer = os.getenv(
        "EMPIRE_OPS_MCP_ISSUER_URL",
        "https://empire-ai.co.uk",
    ).strip()
    return MCPServer(
        **common,
        token_verifier=StaticOpsTokenVerifier(token, resource),
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(issuer),
            resource_server_url=AnyHttpUrl(resource),
            required_scopes=["empire:ops"],
            validate_token_resource=True,
        ),
    )


server = _build_server()


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
            "version": "0.2.0",
            "repo": "/srv/empire_os",
            "http_bearer_auth": bool(
                os.getenv("EMPIRE_OPS_MCP_BEARER_TOKEN", "").strip()
            ),
            "privileged_helper": PRIVILEGED_SOCKET.exists(),
            "privileged_units": sorted(PRIVILEGED_ALLOWED_UNITS),
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


@server.tool(name="empire_service_control", structured_output=True)
def service_control(
    unit: str,
    action: str = "restart",
    execute: bool = False,
) -> dict[str, Any]:
    action = str(action or "").strip().lower()
    if action not in {"restart", "start"}:
        raise ValueError("service action not allowlisted")
    if unit not in PRIVILEGED_ALLOWED_UNITS:
        raise ValueError("unit not allowlisted")
    helper_action = (
        "service_restart" if action == "restart" else "service_start"
    )
    if not execute:
        return _record(
            "empire_service_control",
            {"unit": unit, "action": action, "execute": False},
            lambda: {
                "ok": True,
                "decision": "PREVIEW",
                "unit": unit,
                "action": action,
                "executed": False,
                "privileged_helper_required": True,
            },
        )

    def _execute() -> dict[str, Any]:
        try:
            result = privileged_request(helper_action, unit)
        except PrivilegedHelperUnavailable as exc:
            return {
                "ok": False,
                "decision": "HELPER_UNAVAILABLE",
                "unit": unit,
                "action": action,
                "executed": False,
                "error": str(exc),
            }
        return {
            **result,
            "decision": "EXECUTED" if result.get("ok") else "FAILED",
            "executed": True,
        }

    return _record(
        "empire_service_control",
        {"unit": unit, "action": action, "execute": True},
        _execute,
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
