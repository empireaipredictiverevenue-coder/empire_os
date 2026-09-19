"""OBSERVE-only Strategy Department API."""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from empire_os.strategy_operating_system import (
    rank_keyword_portfolio,
    review_ai_capability,
    review_market_thesis,
    review_strategic_bet,
)


class DataRequest(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class KeywordPortfolioRequest(BaseModel):
    keywords: list[dict[str, Any]] = Field(default_factory=list)


def create_strategy_router() -> APIRouter:
    router = APIRouter(prefix="/v1/strategy", tags=["strategy-department"])

    @router.get("/health")
    def health():
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "market_entry_execution": False,
            "publishing_enabled": False,
            "capital_commitment": False,
            "model_promotion": False,
        }

    @router.post("/market-thesis/review")
    def market_thesis(req: DataRequest):
        try:
            return review_market_thesis(req.data)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/bets/review")
    def strategic_bet(req: DataRequest):
        try:
            return review_strategic_bet(req.data)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/keywords/rank/preview")
    def keywords(req: KeywordPortfolioRequest):
        try:
            return rank_keyword_portfolio(req.keywords)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/ai-capability/review")
    def ai_capability(req: DataRequest):
        try:
            return review_ai_capability(req.data)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return router
