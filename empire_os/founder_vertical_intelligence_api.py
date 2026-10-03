"""Loopback-only Founder read surface for vertical product runtime truth."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from empire_os.permit_intelligence_runtime import build_permit_intelligence_runtime
from empire_os.vertical_intelligence_runtime import (
    build_private_capital_intelligence_runtime,
    build_property_intelligence_runtime,
)


def create_founder_vertical_intelligence_router(
    repo_root: Path | None = None,
) -> APIRouter:
    root = Path(repo_root or "/srv/empire_os")
    router = APIRouter(
        prefix="/v1/founder-vertical-intelligence",
        tags=["founder-vertical-intelligence"],
    )

    @router.get("/permit")
    def permit_runtime():
        return build_permit_intelligence_runtime(root)

    @router.get("/property")
    def property_runtime():
        return build_property_intelligence_runtime(root)

    @router.get("/private-capital")
    def private_capital_runtime():
        return build_private_capital_intelligence_runtime(root)

    return router
