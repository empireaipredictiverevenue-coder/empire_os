"""Simulation-only Digital Twin preview API."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from empire_os.digital_twin import MarketBaseline, MarketScenario
from empire_os.digital_twin_analysis import compare_market_scenario


class MarketBaselineRequest(BaseModel):
    niche: str
    metro: str
    observed_demand_units: int = Field(ge=0)
    observed_capacity_units: int = Field(ge=0)
    observed_price_per_unit_cents: int = Field(gt=0)
    observed_at: str
    evidence_ref: str


class MarketScenarioRequest(BaseModel):
    scenario_id: str
    demand_multiplier: float = Field(default=1.0, ge=0)
    capacity_multiplier: float = Field(default=1.0, ge=0)
    price_multiplier: float = Field(default=1.0, ge=0)


class ScenarioPreviewRequest(BaseModel):
    baseline: MarketBaselineRequest
    scenario: MarketScenarioRequest


def create_digital_twin_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/digital-twin",
        tags=["digital-twin"],
    )

    @router.get("/health")
    def health():
        return {
            "mode": "SIMULATION",
            "simulation_only": True,
            "actual_revenue": False,
            "execution_authority": "none",
        }

    @router.post("/preview")
    def preview(req: ScenarioPreviewRequest):
        baseline = MarketBaseline(**req.baseline.model_dump())
        scenario = MarketScenario(**req.scenario.model_dump())
        try:
            comparison = compare_market_scenario(
                baseline=baseline,
                scenario=scenario,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return {
            "mode": "SIMULATION",
            "simulation_only": True,
            "actual_revenue": False,
            "execution_authority": "none",
            "comparison": comparison.as_dict(),
        }

    return router
