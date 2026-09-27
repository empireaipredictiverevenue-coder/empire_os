"""OBSERVE-only company operating API."""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from empire_os.company_operating_system import (
    build_founder_brief,
    rank_initiatives,
    review_marketing_brief,
    review_rd_candidate,
)


class InitiativesRequest(BaseModel):
    initiatives: list[dict[str, Any]] = Field(default_factory=list)


class FounderBriefRequest(BaseModel):
    date: str
    verified_outcomes: list[dict[str, Any]] = Field(default_factory=list)
    initiatives: list[dict[str, Any]] = Field(default_factory=list)
    decisions_needed: list[dict[str, Any]] = Field(default_factory=list)
    risks: list[dict[str, Any]] = Field(default_factory=list)
    max_priorities: int = 3


class ReviewRequest(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


def create_company_operating_router() -> APIRouter:
    router = APIRouter(prefix="/v1/company-ops", tags=["company-operating-system"])

    @router.get("/health")
    def health():
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "marketing_execution": False,
            "rd_production_deployment": False,
            "staffing_execution": False,
            "commercial_mutation": False,
        }

    @router.post("/initiatives/rank/preview")
    def initiatives(req: InitiativesRequest):
        try:
            return rank_initiatives(req.initiatives)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/founder-brief/preview")
    def founder_brief(req: FounderBriefRequest):
        try:
            return build_founder_brief(
                date=req.date,
                verified_outcomes=req.verified_outcomes,
                initiatives=req.initiatives,
                decisions_needed=req.decisions_needed,
                risks=req.risks,
                max_priorities=req.max_priorities,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/marketing/brief/review")
    def marketing_review(req: ReviewRequest):
        return review_marketing_brief(req.data)

    @router.post("/rd/candidate/review")
    def rd_review(req: ReviewRequest):
        return review_rd_candidate(req.data)

    return router
