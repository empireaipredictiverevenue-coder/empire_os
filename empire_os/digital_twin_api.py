"""Simulation-only Digital Twin preview API."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from empire_os.digital_twin import MarketBaseline, MarketScenario
from empire_os.digital_twin_analysis import compare_market_scenario
from empire_os.digital_twin_registry import (
    DigitalTwinRealizationRecord,
    DigitalTwinRegistryRecord,
)
from empire_os.digital_twin_realization import (
    ObservedMarketOutcome,
    review_scenario_realization,
)


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


class ScenarioRealizationRequest(BaseModel):
    baseline: MarketBaselineRequest
    scenario: MarketScenarioRequest
    observed_served_units: int = Field(ge=0)
    observed_revenue_cents: int | None = Field(default=None, ge=0)
    revenue_recognized: bool = False
    observed_at: str
    evidence_refs: list[str] = Field(min_length=1)


class ScenarioRealizationRegistryRequest(ScenarioRealizationRequest):
    realization_key: str
    scenario_key: str
    evidence: dict = Field(default_factory=dict)


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


    @router.post("/realization/preview")
    def realization_preview(req: ScenarioRealizationRequest):
        baseline = MarketBaseline(**req.baseline.model_dump())
        scenario = MarketScenario(**req.scenario.model_dump())
        try:
            comparison = compare_market_scenario(
                baseline=baseline,
                scenario=scenario,
            )
            observed = ObservedMarketOutcome(
                observed_served_units=req.observed_served_units,
                observed_revenue_cents=req.observed_revenue_cents,
                revenue_recognized=req.revenue_recognized,
                observed_at=req.observed_at,
                evidence_refs=tuple(req.evidence_refs),
            )
            review = review_scenario_realization(
                scenario=comparison.scenario,
                observed=observed,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return {
            "mode": "OBSERVE",
            "simulation_only": True,
            "creates_actual_revenue": False,
            "execution_authority": "none",
            "capital_execution": False,
            "campaign_execution": False,
            "pricing_execution": False,
            "review": review.as_dict(),
        }

    @router.post("/realizations/register")
    def register_realization(req: ScenarioRealizationRegistryRequest):
        if registry is None or not hasattr(registry, "record_realization"):
            raise HTTPException(
                status_code=503,
                detail="digital_twin_realization_registry_not_activated",
            )
        baseline = MarketBaseline(**req.baseline.model_dump())
        scenario = MarketScenario(**req.scenario.model_dump())
        try:
            comparison = compare_market_scenario(
                baseline=baseline,
                scenario=scenario,
            )
            observed = ObservedMarketOutcome(
                observed_served_units=req.observed_served_units,
                observed_revenue_cents=req.observed_revenue_cents,
                revenue_recognized=req.revenue_recognized,
                observed_at=req.observed_at,
                evidence_refs=tuple(req.evidence_refs),
            )
            review = review_scenario_realization(
                scenario=comparison.scenario,
                observed=observed,
            )
            item = DigitalTwinRealizationRecord(
                realization_key=req.realization_key,
                scenario_key=req.scenario_key,
                scenario_id=req.scenario.scenario_id,
                observed=observed,
                review=review,
                evidence=dict(req.evidence),
            )
            item.validate()
            row = registry.record_realization(item)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "simulation_only": True,
            "creates_actual_revenue": False,
            "execution_authority": "none",
            "capital_execution": False,
            "campaign_execution": False,
            "pricing_execution": False,
            "status": str(row.get("status") or "recorded"),
            "realization_record": item.as_dict(),
            "result": dict(row),
        }

    @router.get("/realizations")
    def list_realizations(limit: int = 100):
        if registry is None or not hasattr(registry, "list_realizations"):
            raise HTTPException(
                status_code=503,
                detail="digital_twin_realization_registry_not_activated",
            )
        rows = list(registry.list_realizations(limit=max(1, min(limit, 500))))
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "simulation_only": True,
            "creates_actual_revenue": False,
            "execution_authority": "none",
            "capital_execution": False,
            "campaign_execution": False,
            "pricing_execution": False,
            "count": len(rows),
            "items": [dict(row) for row in rows],
        }

    @router.post("/scenarios/register")
    def register_scenario(req: ScenarioRegistryRequest):
        if registry is None or not hasattr(registry, "record"):
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
