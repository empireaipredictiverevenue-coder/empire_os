"""Founder-only bounded research API candidate.

This router does not grant identities, editorial approval, send, money, or
publication authority. Default identity adapter fails closed without a
cryptographically verified existing Cloudflare Access Founder session.
"""
from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from threading import BoundedSemaphore, Lock
from time import monotonic
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict

from empire_os.founder_research_auth import require_founder_access_jwt
from empire_os.research.research_products import product_catalog, use_product


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product: Literal["empire_research", "empire_agent"]
    country: Literal["US", "GB", "both"] = "both"
    niche: Literal["dental", "roofing", "solar", "hvac", "legal", "property"] = "dental"
    depth: Literal["speed", "balanced", "quality"] = "quality"
    fresh_discovery: bool = False


class ResearchExecutionBudget:
    """Single in-flight job and per-subject cooldown in one loopback worker."""

    def __init__(self, min_interval_seconds: float = 60):
        if min_interval_seconds < 0:
            raise ValueError("INVALID_RESEARCH_EXECUTION_COOLDOWN")
        self.min_interval_seconds = min_interval_seconds
        self._semaphore = BoundedSemaphore(1)
        self._lock = Lock()
        self._last_started: dict[str, float] = {}

    @contextmanager
    def run(self, principal: str):
        if not self._semaphore.acquire(blocking=False):
            raise HTTPException(429, "FOUNDER_RESEARCH_EXECUTION_BUSY")
        try:
            now = monotonic()
            with self._lock:
                if now - self._last_started.get(principal, -float("inf")) < self.min_interval_seconds:
                    raise HTTPException(429, "FOUNDER_RESEARCH_COOLDOWN_ACTIVE")
                self._last_started[principal] = now
            yield
        finally:
            self._semaphore.release()


def create_founder_research_products_router(
    product_runner: Callable = use_product,
    *,
    require_founder: Callable[[Request], str] = require_founder_access_jwt,
    execution_budget: ResearchExecutionBudget | None = None,
) -> APIRouter:
    budget = execution_budget or ResearchExecutionBudget()
    router = APIRouter(prefix="/v1/founder-research-products",
                       tags=["founder-research-products-private"],
                       dependencies=[Depends(require_founder)])

    @router.get("/catalog")
    def catalog(response: Response):
        response.headers["Cache-Control"] = "no-store, private"
        return {
            **product_catalog(),
            "private_execution_guardrails": {
                "max_original_pages_per_request": 6,
                "max_concurrent_requests_per_worker": 1,
                "min_seconds_between_jobs_per_founder": budget.min_interval_seconds,
                "verified_founder_session_required": True,
                "fresh_discovery_max_queries_per_request": 4,
                "source_admission_automatic": False,
                "editorial_approval_automatic": False,
            },
        }

    @router.post("/preview")
    def preview(body: PreviewRequest, response: Response,
                principal: str = Depends(require_founder)):
        response.headers["Cache-Control"] = "no-store, private"
        with budget.run(principal):
            try:
                report = product_runner(body.product, country=body.country,
                                        niche=body.niche, depth=body.depth,
                                        fresh_discovery=body.fresh_discovery)
            except Exception:
                raise HTTPException(503, "FOUNDER_RESEARCH_SOURCE_EXECUTION_UNAVAILABLE") from None
        if (not isinstance(report, dict)
            or report.get("commercial_actions_authorized") is True
            or report.get("outbound_authorized") is not False
            or report.get("customer_delivery_authorized") is not False
            or report.get("finance_authorized") is not False
            or report.get("database_writes") is not False
            or report.get("original_source_count", 0) > 6):
            raise HTTPException(503, "FOUNDER_RESEARCH_GUARDRAIL_VIOLATION")
        return report

    return router
