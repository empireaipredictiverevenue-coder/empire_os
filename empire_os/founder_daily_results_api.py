"""Read-only Founder API for daily EmpireOS operating results."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

ROOT = Path("/srv/empire_os")
LATEST = ROOT / "runtime" / "daily_results" / "latest.json"
HISTORY = ROOT / "runtime" / "daily_results" / "history"


def _read(path: Path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def create_founder_daily_results_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/founder-daily-results",
        tags=["founder-daily-results"],
    )

    @router.get("/latest")
    def latest():
        payload = _read(LATEST)
        if payload is None:
            raise HTTPException(404, "daily results unavailable")
        return payload

    @router.get("/history")
    def history(limit: int = 14):
        safe_limit = max(1, min(int(limit), 90))
        files = sorted(HISTORY.glob("*.json"), reverse=True)[:safe_limit]
        items = [value for path in files if (value := _read(path)) is not None]
        return {
            "schema_version": "empire.daily_results_history.v1",
            "count": len(items),
            "items": items,
            "execution_authority": "none",
        }

    return router
