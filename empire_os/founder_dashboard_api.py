"""Founder dashboard read-only API."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from empire_os.founder_dashboard import build_founder_dashboard


def create_founder_dashboard_router(
    repo_root: Path | None = None,
) -> APIRouter:
    root = repo_root or Path(__file__).resolve().parents[1]
    router = APIRouter(
        prefix="/v1/founder-dashboard",
        tags=["founder-dashboard"],
    )

    @router.get("/overview")
    def overview():
        return build_founder_dashboard(root)

    return router
