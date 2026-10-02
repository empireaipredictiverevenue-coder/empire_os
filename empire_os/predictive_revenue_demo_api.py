"""Read-only live Predictive Revenue demo API."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from empire_os.predictive_revenue_demo import (
    build_predictive_revenue_demo,
    render_predictive_revenue_demo_html,
)


def create_predictive_revenue_demo_router(
    repo_root: Path | None = None,
) -> APIRouter:
    root = repo_root or Path(__file__).resolve().parents[1]
    router = APIRouter(
        prefix="/v1/predictive-revenue",
        tags=["predictive-revenue-demo"],
    )

    @router.get("/demo")
    def demo():
        return build_predictive_revenue_demo(root)

    @router.get("/demo/live", response_class=HTMLResponse)
    def demo_live():
        payload = build_predictive_revenue_demo(root)
        return HTMLResponse(render_predictive_revenue_demo_html(payload))

    return router
