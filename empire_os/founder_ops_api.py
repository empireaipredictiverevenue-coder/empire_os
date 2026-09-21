"""Read-only Founder Console surface for control-fabric health."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

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
        }
    if not isinstance(value, dict):
        return {"available": False}
    return {"available": True, **value}


def create_founder_ops_router(snapshot_path: Path = DEFAULT_SNAPSHOT) -> APIRouter:
    router = APIRouter(prefix="/v1/founder-ops", tags=["founder-ops"])

    @router.get("/status")
    def status():
        return read_ops_snapshot(snapshot_path)

    return router
