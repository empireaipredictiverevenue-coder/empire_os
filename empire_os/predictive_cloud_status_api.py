"""Read-only Founder surface for canonical Predictive Cloud status."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter


DEFAULT_SNAPSHOT = Path(
    "/srv/empire_os/runtime/predictive_cloud/status_latest.json"
)


def read_predictive_cloud_status(
    path: Path = DEFAULT_SNAPSHOT,
) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "schema_version": "empire.predictive_cloud.status.v1",
            "available": False,
            "mode": "OBSERVE",
            "components": {},
            "unavailable_components": [],
            "stale_components": [],
            "execution_authority": "none",
        }
    if not isinstance(value, dict):
        return {
            "schema_version": "empire.predictive_cloud.status.v1",
            "available": False,
            "mode": "OBSERVE",
            "components": {},
            "execution_authority": "none",
        }
    return {"available": True, **value}


def create_predictive_cloud_status_router(
    snapshot_path: Path = DEFAULT_SNAPSHOT,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/predictive-cloud",
        tags=["predictive-cloud"],
    )

    @router.get("/status")
    def status():
        return read_predictive_cloud_status(snapshot_path)

    return router
