"""OBSERVE-only Quantitative Intelligence API."""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from empire_os.quant_brain import (
    brier_score, expected_economics, monte_carlo_economics,
    portfolio_concentration, rank_candidates, update_beta_posterior,
    value_of_information,
)

class Payload(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)

def create_quant_brain_router() -> APIRouter:
    router=APIRouter(prefix="/v1/quant-brain",tags=["quantitative-intelligence"])

    def run(fn, **kwargs):
        try:
            return fn(**kwargs)
        except (TypeError,ValueError) as exc:
            raise HTTPException(status_code=422,detail=str(exc)) from exc

    @router.get("/health")
    def health():
        return {
            "mode":"OBSERVE","execution_authority":"none",
            "prediction_is_actual":False,"simulation_is_actual":False,
            "model_weight_mutation":False,"capital_execution":False,
        }

    @router.post("/bayes/beta/preview")
    def bayes(req:Payload):
        return run(update_beta_posterior,**req.data)

    @router.post("/economics/preview")
    def economics(req:Payload):
        return run(expected_economics,**req.data).as_dict()

    @router.post("/calibration/brier/preview")
    def calibration(req:Payload):
        return run(brier_score,**req.data)

    @router.post("/rank/preview")
    def rank(req:Payload):
        try:
            return {"candidates":rank_candidates(req.data.get("candidates",[])),
                    "execution_authority":"none"}
        except (TypeError,ValueError) as exc:
            raise HTTPException(status_code=422,detail=str(exc)) from exc

    @router.post("/monte-carlo/preview")
    def monte(req:Payload):
        return run(monte_carlo_economics,**req.data)

    @router.post("/value-of-information/preview")
    def voi(req:Payload):
        return run(value_of_information,**req.data)

    @router.post("/portfolio/concentration/preview")
    def portfolio(req:Payload):
        try:
            return portfolio_concentration(req.data.get("weights",{}))
        except (TypeError,ValueError) as exc:
            raise HTTPException(status_code=422,detail=str(exc)) from exc

    return router
