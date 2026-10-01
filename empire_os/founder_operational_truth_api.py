"""Read-only Founder Operational Truth API."""
from __future__ import annotations

from fastapi import APIRouter

from empire_os.founder_operational_truth import build_operational_truth


def create_founder_operational_truth_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/founder-operational-truth",
        tags=["founder-operational-truth"],
    )

    @router.get("/status")
    def status():
        return build_operational_truth()

    return router
