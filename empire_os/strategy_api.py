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
from empire_os.market_domination import (
    analyse_market_capture,
    compare_adjacent_corridors,
    rank_market_portfolio,
)
from empire_os.competitive_intelligence import (
    build_competitive_landscape,
    observed_ai_citation_share,
    observed_search_presence_share,
    review_competitor_profile,
)
from empire_os.keyword_universe import (
    build_asset_backlog,
    build_keyword_universe,
    keyword_coverage_matrix,
    review_keyword_record,
)
from empire_os.ai_strategy_portfolio import (
    ai_portfolio_gaps,
    build_ai_capability_portfolio,
    compare_ai_options,
    review_ai_portfolio_item,
)
from empire_os.strategic_scenarios import (
    build_scenario_set,
    review_scenario,
    scenario_gaps,
    stress_test_strategy,
)
from empire_os.jev_strategy import (
    CANDIDATE_TASKS as JEV_CANDIDATE_TASKS,
    build_jev_eval_plan,
    compare_decision_providers,
    review_jev_use_case,
)


class DataRequest(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class KeywordPortfolioRequest(BaseModel):
    keywords: list[dict[str, Any]] = Field(default_factory=list)


class MarketPortfolioRequest(BaseModel):
    markets: list[dict[str, Any]] = Field(default_factory=list)


class AdjacentCorridorRequest(BaseModel):
    current: dict[str, Any] = Field(default_factory=dict)
    candidates: list[dict[str, Any]] = Field(default_factory=list)


class CompetitiveLandscapeRequest(BaseModel):
    competitor_profiles: list[dict[str, Any]] = Field(default_factory=list)
    search_observations: list[dict[str, Any]] = Field(default_factory=list)
    ai_citation_observations: list[dict[str, Any]] = Field(default_factory=list)
    empire_domains: list[str] = Field(default_factory=list)


class PresenceShareRequest(BaseModel):
    observations: list[dict[str, Any]] = Field(default_factory=list)
    empire_domains: list[str] = Field(default_factory=list)
    competitor_domains: list[str] = Field(default_factory=list)


class KeywordUniverseRequest(BaseModel):
    keywords: list[dict[str, Any]] = Field(default_factory=list)


class AiPortfolioRequest(BaseModel):
    capabilities: list[dict[str, Any]] = Field(default_factory=list)


class AiOptionComparisonRequest(BaseModel):
    capability_key: str
    options: list[dict[str, Any]] = Field(default_factory=list)


class ScenarioSetRequest(BaseModel):
    scenarios: list[dict[str, Any]] = Field(default_factory=list)


class StressTestRequest(BaseModel):
    baseline: dict[str, Any] = Field(default_factory=dict)
    scenarios: list[dict[str, Any]] = Field(default_factory=list)


class BenchmarkRowsRequest(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)


class JevUseCasesRequest(BaseModel):
    use_cases: list[dict[str, Any]] = Field(default_factory=list)


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

    @router.post("/market-domination/review")
    def market_domination(req: DataRequest):
        try:
            return analyse_market_capture(req.data)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/market-domination/portfolio/preview")
    def market_domination_portfolio(req: MarketPortfolioRequest):
        try:
            return rank_market_portfolio(req.markets)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/market-domination/adjacent/preview")
    def market_domination_adjacent(req: AdjacentCorridorRequest):
        try:
            return compare_adjacent_corridors(
                current=req.current,
                candidates=req.candidates,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/competitive/profile/review")
    def competitive_profile(req: DataRequest):
        try:
            return review_competitor_profile(req.data)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/competitive/search-presence/preview")
    def competitive_search_presence(req: PresenceShareRequest):
        try:
            return observed_search_presence_share(
                req.observations,
                empire_domains=req.empire_domains,
                competitor_domains=req.competitor_domains,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/competitive/ai-citation-share/preview")
    def competitive_ai_citations(req: PresenceShareRequest):
        try:
            return observed_ai_citation_share(
                req.observations,
                empire_domains=req.empire_domains,
                competitor_domains=req.competitor_domains,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/competitive/landscape/preview")
    def competitive_landscape(req: CompetitiveLandscapeRequest):
        try:
            return build_competitive_landscape(
                competitor_profiles=req.competitor_profiles,
                search_observations=req.search_observations,
                ai_citation_observations=req.ai_citation_observations,
                empire_domains=req.empire_domains,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/keyword-universe/review")
    def keyword_review(req: DataRequest):
        try:
            return review_keyword_record(req.data)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/keyword-universe/preview")
    def keyword_universe(req: KeywordUniverseRequest):
        try:
            return build_keyword_universe(req.keywords)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/keyword-universe/coverage/preview")
    def keyword_coverage(req: KeywordUniverseRequest):
        try:
            return keyword_coverage_matrix(req.keywords)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/keyword-universe/assets/preview")
    def keyword_assets(req: KeywordUniverseRequest):
        try:
            return build_asset_backlog(req.keywords)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/ai-portfolio/item/review")
    def ai_portfolio_item(req: DataRequest):
        try:
            return review_ai_portfolio_item(req.data)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/ai-portfolio/preview")
    def ai_portfolio(req: AiPortfolioRequest):
        try:
            return build_ai_capability_portfolio(req.capabilities)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/ai-portfolio/gaps/preview")
    def ai_portfolio_gap_review(req: AiPortfolioRequest):
        try:
            return ai_portfolio_gaps(req.capabilities)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/ai-portfolio/options/compare/preview")
    def ai_option_compare(req: AiOptionComparisonRequest):
        try:
            return compare_ai_options(
                capability_key=req.capability_key,
                options=req.options,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/scenarios/review")
    def scenario_review(req: DataRequest):
        try:
            return review_scenario(req.data)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/scenarios/set/preview")
    def scenario_set(req: ScenarioSetRequest):
        try:
            return build_scenario_set(req.scenarios)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/scenarios/stress-test/preview")
    def scenario_stress(req: StressTestRequest):
        try:
            return stress_test_strategy(
                baseline=req.baseline,
                scenarios=req.scenarios,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/scenarios/gaps/preview")
    def scenario_gap_review(req: ScenarioSetRequest):
        try:
            return scenario_gaps(req.scenarios)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get("/jev/task-catalog")
    def jev_tasks():
        return {
            "schema_version": "jev_task_catalog.v1",
            "mode": "OBSERVE",
            "execution_authority": "none",
            "candidate_tasks": sorted(JEV_CANDIDATE_TASKS),
            "provider_activation": False,
        }

    @router.post("/jev/use-case/review")
    def jev_use_case(req: DataRequest):
        return review_jev_use_case(req.data)

    @router.post("/jev/eval-plan/preview")
    def jev_eval_plan(req: JevUseCasesRequest):
        try:
            return build_jev_eval_plan(req.use_cases)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/jev/providers/compare/preview")
    def jev_provider_compare(req: BenchmarkRowsRequest):
        try:
            return compare_decision_providers(req.rows)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return router
