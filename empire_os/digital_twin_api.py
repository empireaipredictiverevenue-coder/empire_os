"""Simulation-only Digital Twin preview API."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from empire_os.digital_twin import MarketBaseline, MarketScenario
from empire_os.digital_twin_analysis import compare_market_scenario
from empire_os.digital_twin_registry import DigitalTwinRegistryRecord


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




class ScenarioRegistryRequest(BaseModel):
    scenario_key: str
    baseline: MarketBaselineRequest
    scenario: MarketScenarioRequest
    evidence: dict = Field(default_factory=dict)

class ScenarioPreviewRequest(BaseModel):
    baseline: MarketBaselineRequest
    scenario: MarketScenarioRequest


def create_digital_twin_router(registry=None) -> APIRouter:
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
            "registry_available": registry is not None,
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


    @router.post("/scenarios/register")
    def register_scenario(req: ScenarioRegistryRequest):
        if registry is None:
            raise HTTPException(
                status_code=503,
                detail="digital_twin_registry_not_activated",
            )
        baseline = MarketBaseline(**req.baseline.model_dump())
        scenario = MarketScenario(**req.scenario.model_dump())
        try:
            comparison = compare_market_scenario(
                baseline=baseline,
                scenario=scenario,
            )
            item = DigitalTwinRegistryRecord(
                scenario_key=req.scenario_key,
                baseline=baseline,
                scenario=scenario,
                comparison=comparison,
                evidence=dict(req.evidence),
            )
            item.validate()
            row = registry.record(item)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "SIMULATION",
            "simulation_only": True,
            "actual_revenue": False,
            "execution_authority": "none",
            "capital_execution": False,
            "campaign_execution": False,
            "pricing_execution": False,
            "status": str(row.get("status") or "recorded"),
            "registry_record": item.as_dict(),
            "result": dict(row),
        }

    @router.get("/scenarios")
    def list_scenarios(limit: int = 100):
        if registry is None or not hasattr(registry, "list_scenarios"):
            raise HTTPException(
                status_code=503,
                detail="digital_twin_registry_not_activated",
            )
        rows = list(registry.list_scenarios(limit=max(1, min(limit, 500))))
        return {
            "mode": "SIMULATION",
            "read_only": True,
            "simulation_only": True,
            "actual_revenue": False,
            "execution_authority": "none",
            "capital_execution": False,
            "campaign_execution": False,
            "pricing_execution": False,
            "count": len(rows),
            "items": [dict(row) for row in rows],
        }

    return router
