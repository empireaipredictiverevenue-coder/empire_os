"""Loopback-only Founder API for lead counts, sources, lanes and seats."""
from __future__ import annotations

from pathlib import Path
import json

from fastapi import APIRouter


DEFAULT_REPORT = Path("/srv/empire_os/runtime/lead_supply/niche_counts_latest.json")


def read_lead_supply_report(path: Path = DEFAULT_REPORT) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {
            "available": False,
            "mode": "OBSERVE",
            "reason": "canonical_lead_supply_report_not_published",
            "lead_counts_complete": False,
            "public_self_serve_raw_lead_counts_allowed": False,
            "execution_authority": "none",
        }
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != "empire.lead_supply_intelligence.v1"
        or payload.get("canonical_backend") != "empiredb"
        or payload.get("mode") != "OBSERVE"
    ):
        return {
            "available": False,
            "mode": "OBSERVE",
            "reason": "lead_supply_report_not_canonical",
            "lead_counts_complete": False,
            "execution_authority": "none",
        }
    return {"available": True, **payload}


def create_founder_lead_supply_router(
    report_path: Path = DEFAULT_REPORT,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/founder-lead-supply",
        tags=["founder-lead-supply"],
    )

    @router.get("/overview")
    def overview():
        return read_lead_supply_report(report_path)

    return router
