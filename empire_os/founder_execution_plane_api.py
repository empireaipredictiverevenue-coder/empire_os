"""Read-only Founder API for the Agent & Tool Execution Plane."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from empire_os.agent_execution_plane import worker_registry_snapshot
from empire_os.agent_tool_runtime import execution_tool_health_snapshot
from empire_os.execution_lease import ExecutionLeaseManager
from empire_os.predictive_coding_team_status import (
    build_predictive_coding_team_status,
)


DEFAULT_LEASE_ROOT = Path("/srv/empire_os/runtime/execution_plane")
DEFAULT_REPO_ROOT = Path("/srv/empire_os")


def build_execution_plane_status(
    *,
    lease_root: Path = DEFAULT_LEASE_ROOT,
) -> dict[str, Any]:
    registry = worker_registry_snapshot()
    leases = ExecutionLeaseManager(lease_root).active()
    return {
        "schema_version": "empire.founder-execution-plane.v1",
        "architecture_ref": (
            "docs/AGENT_TOOL_EXECUTION_PLANE_ARCHITECTURE.md"
        ),
        "registry": registry,
        "active_mutation_leases": leases,
        "active_mutation_lease_count": len(leases),
        "architecture_first_required": True,
        "read_only": True,
        "execution_authority": "none",
    }


def create_founder_execution_plane_router(
    lease_root: Path = DEFAULT_LEASE_ROOT,
    repo_root: Path = DEFAULT_REPO_ROOT,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/founder-execution-plane",
        tags=["founder-execution-plane"],
    )

    @router.get("/status")
    def status():
        return build_execution_plane_status(lease_root=lease_root)

    @router.get("/tools/health")
    def tools_health():
        return {
            **execution_tool_health_snapshot(),
            "read_only": True,
            "execution_authority": "none",
        }

    @router.get("/coding-team/status")
    def coding_team_status():
        return build_predictive_coding_team_status(repo_root)

    return router
