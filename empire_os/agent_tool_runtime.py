"""Runtime discovery/health for execution-plane external tools.

Health is observational only. A healthy tool does not receive authority and does
not prove the quality/freshness of any data it returns.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Mapping


@dataclass(frozen=True)
class ToolHealth:
    key: str
    installed: bool
    ready: bool
    version: str | None = None
    detail: str | None = None
    authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _run(
    argv: list[str],
    *,
    env: Mapping[str, str] | None = None,
    timeout: int = 15,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd is not None else None,
        env=dict(env or os.environ),
        capture_output=True,
        text=True,
        timeout=max(1, min(int(timeout), 60)),
        check=False,
    )


def pi_health(
    binary: str | Path = "/opt/empire/pi-agent/bin/pi",
) -> ToolHealth:
    path = Path(binary)
    if not path.exists():
        return ToolHealth(
            key="pi",
            installed=False,
            ready=False,
            detail="pi_binary_missing",
        )
    try:
        result = _run(
            [str(path), "--version"],
            env={
                **os.environ,
                "PI_OFFLINE": "1",
                "PI_TELEMETRY": "0",
                "PI_CODING_AGENT_DIR": (
                    "/etc/empire_os/pi-agent"
                ),
            },
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ToolHealth(
            key="pi",
            installed=True,
            ready=False,
            detail=type(exc).__name__,
        )
    version = (result.stdout or result.stderr).strip().splitlines()
    return ToolHealth(
        key="pi",
        installed=True,
        ready=result.returncode == 0,
        version=version[-1][:120] if version else None,
        detail=None if result.returncode == 0 else "version_check_failed",
    )


def agent_reach_health(
    binary: str | Path = (
        "/opt/empire/agent-reach/venv/bin/agent-reach"
    ),
) -> dict[str, Any]:
    path = Path(binary)
    if not path.exists():
        return {
            "tool": ToolHealth(
                key="agent_reach",
                installed=False,
                ready=False,
                detail="agent_reach_binary_missing",
            ).as_dict(),
            "doctor": None,
            "probe_performed": False,
            "truth_authority": "none",
        }

    argv = [str(path), "doctor", "--json"]
    try:
        result = _run(
            argv,
            env={
                **os.environ,
                "HOME": "/var/lib/empire/agent-reach/home",
                "PATH": (
                    "/opt/empire/agent-reach/venv/bin:"
                    "/opt/empire/pi-agent/bin:"
                    "/usr/local/bin:/usr/bin:/bin"
                ),
            },
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "tool": ToolHealth(
                key="agent_reach",
                installed=True,
                ready=False,
                detail=type(exc).__name__,
            ).as_dict(),
            "doctor": None,
            "probe_performed": False,
            "truth_authority": "none",
        }

    payload: Any = None
    if result.returncode == 0:
        try:
            payload = json.loads(result.stdout or "{}")
        except json.JSONDecodeError:
            payload = None

    return {
        "tool": ToolHealth(
            key="agent_reach",
            installed=True,
            ready=result.returncode == 0 and isinstance(payload, dict),
            detail=(
                None
                if result.returncode == 0 and isinstance(payload, dict)
                else "doctor_failed_or_invalid_json"
            ),
        ).as_dict(),
        "doctor": payload if isinstance(payload, dict) else None,
        "probe_performed": False,
        "health_is_not_source_truth": True,
        "per_observation_provenance_required": True,
        "truth_authority": "none",
    }


def space_agent_health(
    source_dir: str | Path = "/opt/empire/space-agent/source",
) -> ToolHealth:
    root = Path(source_dir)
    package = root / "package.json"
    cli = root / "space"
    if not package.exists() or not cli.exists():
        return ToolHealth(
            key="space_agent",
            installed=False,
            ready=False,
            detail="space_agent_source_missing",
        )

    try:
        raw = json.loads(package.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = {}
    version = str(raw.get("version") or "").strip() or None
    node = Path("/opt/empire/space-agent/bin/node")
    return ToolHealth(
        key="space_agent",
        installed=True,
        ready=node.exists(),
        version=version,
        detail=None if node.exists() else "node_missing",
    )


def execution_tool_health_snapshot() -> dict[str, Any]:
    reach = agent_reach_health()
    return {
        "schema_version": "empire.execution-tool-health.v1",
        "pi": pi_health().as_dict(),
        "agent_reach": reach,
        "space_agent": space_agent_health().as_dict(),
        "health_grants_authority": False,
        "execution_authority": "none",
    }
