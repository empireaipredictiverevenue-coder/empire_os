"""Read-only Founder Console surface for control-fabric health."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from empire_os.executive_founder_status import (
    DEFAULT_EXECUTIVE,
    read_executive_founder_status,
)

DEFAULT_SNAPSHOT = Path("/srv/empire_os/runtime/ops_control/latest.json")


def read_ops_snapshot(path: Path = DEFAULT_SNAPSHOT) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "schema_version": "empire.ops_control_cycle.v1",
            "available": False,
            "healthy": None,
            "business_blocker": None,
            "sentinel": {"findings": [], "repair_plan": []},
            "healer": {"proposed": 0, "executed": 0, "results": []},
            "incident_manager": {
                "incident_count": 0,
                "diagnoses": [],
                "requires_escalation": False,
            },
            "conveyor": {
                "loop_complete": False,
                "current_blocker": None,
                "owner_component": None,
                "authority": "none",
                "stages": [],
            },
        }
    if not isinstance(value, dict):
        return {"available": False}
    return {"available": True, **value}


def create_founder_ops_router(
    snapshot_path: Path = DEFAULT_SNAPSHOT,
    executive_snapshot_path: Path = DEFAULT_EXECUTIVE,
) -> APIRouter:
    router = APIRouter(prefix="/v1/founder-ops", tags=["founder-ops"])

    @router.get("/status")
    def status():
        return read_ops_snapshot(snapshot_path)

    @router.get("/executive-roles/status")
    def executive_roles_status():
        # Read from the existing Astra plan snapshot, never run an agent or
        # perform a live mailbox/production action from a Founder Console GET.
        return read_executive_founder_status(executive_snapshot_path)

    return router
