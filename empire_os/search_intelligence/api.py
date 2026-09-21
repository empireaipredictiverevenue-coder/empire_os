"""FastAPI routes for the Search Intelligence foundation."""
from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .attribution import preview_search_revenue_attribution
from .attribution_review import review_search_attribution
from .ai_visibility import AiCitationObservation, analyse_ai_visibility
from .backlinks import BacklinkObservation, analyse_backlink_graph
from .citation_gap import analyse_citation_gap
from .commander import SearchCommanderAgent
from .competitor_gap import analyse_competitor_gap
from .crawler_product import crawl_search_site
from .health import search_health
from .local_visibility import (
    LocalGridObservation,
    analyse_local_grid,
)
from .metadata import generate_metadata
from .models import SearchOpportunity, SearchPage
from .performance import lighthouse_parser_status, parse_lighthouse_report
from .quality import ContentQualityEvaluator
from .rank_history import RankObservation, analyse_rank_history
from .reports import build_search_product_report
from .products import (
    get_search_product,
    product_catalog,
    product_portfolio_readiness,
)
from .repository import SearchRepository, bounded_limit, collection_payload
from .postgres_repository import configured_search_repository_from_env
from .schema import generate_schema_preview
from .search_console import (
    SearchConsoleAdapter,
    configured_search_console_adapter,
)
from .serp import SearchFabricSerpAdapter, SerpResultEvidence, SerpSnapshot
from empire_os.search_traffic_forecast import (
    aggregate_search_console_daily,
    forecast_search_traffic,
)
from empire_os.timesfm_shadow import configured_timesfm_provider




class AiCitationObservationRequest(BaseModel):
    query: str
    engine: str
    observed_at: str
    cited_url: str
    source_url: str | None = None
    citation_position: int | None = Field(default=None, ge=1)
    mention_text: str | None = None
    provenance: list[str] = Field(min_length=1)


class AiVisibilityPreviewRequest(BaseModel):
    query: str
    engine: str
    empire_domains: list[str] = Field(min_length=1)
    observations: list[AiCitationObservationRequest] = Field(default_factory=list)

class CitationGapPreviewRequest(BaseModel):
    query: str
    engine: str
    empire_domains: list[str] = Field(min_length=1)
    competitor_domains: list[str] = Field(min_length=1)
    observations: list[AiCitationObservationRequest] = Field(
        default_factory=list
    )


class BacklinkObservationRequest(BaseModel):
    source_url: str
    target_url: str
    observed_at: str
    anchor_text: str | None = None
    rel: str | None = None
    source: str = "observed_backlink"
    provenance: list[str] = Field(min_length=1)


class BacklinkGraphPreviewRequest(BaseModel):
    empire_domains: list[str] = Field(min_length=1)
    observations: list[BacklinkObservationRequest] = Field(
        default_factory=list
    )


class SearchProductReportRequest(BaseModel):
    site: str
    generated_at: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class LocalGridObservationRequest(BaseModel):
    query: str
    latitude: float
    longitude: float
    observed_at: str
    engine: str
    provenance: list[str] = Field(min_length=1)
    position: int | None = Field(default=None, ge=1)


class LocalGridPreviewRequest(BaseModel):
    query: str
    engine: str | None = None
    observations: list[LocalGridObservationRequest] = Field(
        default_factory=list
    )


class RankObservationRequest(BaseModel):
    query: str
    url: str
    observed_at: str
    position: int = Field(ge=1)
    engine: str
    source: str
    provenance: list[str] = Field(min_length=1)


class RankHistoryPreviewRequest(BaseModel):
    query: str
    url: str | None = None
    engine: str | None = None
    observations: list[RankObservationRequest] = Field(default_factory=list)


class LighthouseReportRequest(BaseModel):
    report: dict[str, Any]


class CrawlPreviewRequest(BaseModel):
    url: str
    max_pages: int = Field(default=6, ge=1, le=12)
    request_timeout_seconds: float = Field(default=8.0, ge=1.0, le=30.0)
    time_budget_seconds: float = Field(default=30.0, ge=1.0, le=120.0)


class AnalyseRequest(BaseModel):
    page: dict[str, Any]
    quality_factors: dict[str, float | None] = Field(default_factory=dict)
    opportunity: dict[str, Any] | None = None


class PageValidateRequest(BaseModel):
    quality_factors: dict[str, float | None] = Field(default_factory=dict)


class SchemaPreviewRequest(BaseModel):
    schema_type: str
    visible_content: dict[str, Any] = Field(default_factory=dict)


class MetadataPreviewRequest(BaseModel):
    page: dict[str, Any]
    quality_factors: dict[str, float | None] = Field(default_factory=dict)


class SerpQueryRequest(BaseModel):
    query: str
    num: int = Field(default=10, ge=1, le=20)
    engine: str | None = None


class SerpResultRequest(BaseModel):
    title: str
    url: str
    snippet: str = ""
    position: int = Field(ge=1)
    engine: str
    relevance_score: float | None = None
    provenance: list[str] = Field(default_factory=list)


class SerpSnapshotRequest(BaseModel):
    query: str
    observed_at: str
    engine: str
    quality_gate: str | None = None
    cache: bool | None = None
    available: bool
    results: list[SerpResultRequest] = Field(default_factory=list)
    error: str | None = None


class CompetitorGapPreviewRequest(BaseModel):
    snapshot: SerpSnapshotRequest
    empire_domains: list[str] = Field(min_length=1)


class RevenueAttributionReviewRequest(BaseModel):
    site_id: str
    page_id: str | None = None
    query: str | None = None
    external_session_id: str | None = None
    prospect_id: str | None = None
    opportunity_id: str | None = None
    attribution_kind: str = "observed_search_touch"
    commercial_event: dict[str, Any]
    search_touch_observed_at: str
    touch_evidence_ref: str
    observed_cost_cents: int | None = Field(default=None, ge=0)
    cost_evidence_ref: str | None = None
    max_attribution_lag_seconds: int = Field(default=2592000, gt=0)


class RevenueAttributionPreviewRequest(BaseModel):
    site_id: str
    page_id: str | None = None
    query: str | None = None
    external_session_id: str | None = None
    prospect_id: str | None = None
    opportunity_id: str | None = None
    attribution_kind: str = "observed_search_touch"
    commercial_event: dict[str, Any]


def _repository_unavailable() -> None:
    raise HTTPException(
        status_code=503,
        detail="canonical_search_repository_not_activated",
    )


def create_search_router(
    repository: SearchRepository | None = None,
    search_console_adapter: SearchConsoleAdapter | None = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/search",
        tags=["search-intelligence"],
    )
    search_console = (
        search_console_adapter
        if search_console_adapter is not None
        else configured_search_console_adapter()
    )

    @router.get("/health")
    def health():
        return {
            **search_health(),
            "repository_available": repository is not None,
            "api_contract_version": "search-v1",
        }

    @router.get("/search-console/status")
    def search_console_status():
        return search_console.status().as_dict()

    @router.get("/search-console/observations")
    def search_console_observations(
        start_date: date,
        end_date: date,
        limit: int = Query(default=1000, ge=1, le=25000),
    ):
        status = search_console.status()
        if not status.available:
            raise HTTPException(status_code=503, detail=status.reason)
        if end_date < start_date:
            raise HTTPException(status_code=422, detail="invalid_date_range")
        rows = [dict(row) for row in search_console.observations(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            limit=limit,
        )]
        return {
            "available": True,
            "source": "google_search_console",
            "site_url": status.site_url,
            "count": len(rows),
            "limit": limit,
            "items": rows,
        }

    @router.get("/search-console/daily")
    def search_console_daily(
        start_date: date,
        end_date: date,
        limit: int = Query(default=1000, ge=1, le=25000),
    ):
        status = search_console.status()
        if not status.available:
            raise HTTPException(status_code=503, detail=status.reason)
        if end_date < start_date:
            raise HTTPException(status_code=422, detail="invalid_date_range")
        daily_method = getattr(search_console, "daily_observations", None)
        if daily_method is None:
            raise HTTPException(
                status_code=503,
                detail="daily_search_console_observations_unavailable",
            )
        rows = [
            dict(row)
            for row in daily_method(
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                limit=limit,
            )
        ]
        return {
            "available": True,
            "source": "google_search_console",
            "dimensions": ["date"],
            "site_url": status.site_url,
            "count": len(rows),
            "limit": limit,
            "items": rows,
        }

    @router.get("/forecast/traffic")
    def search_traffic_forecast(
        start_date: date,
        end_date: date,
        horizon_days: int = Query(default=30, ge=1, le=365),
        limit: int = Query(default=1000, ge=1, le=25000),
    ):
        status = search_console.status()
        if not status.available:
            raise HTTPException(status_code=503, detail=status.reason)
        if end_date < start_date:
            raise HTTPException(status_code=422, detail="invalid_date_range")
        daily_method = getattr(search_console, "daily_observations", None)
        if daily_method is None:
            raise HTTPException(
                status_code=503,
                detail="daily_search_console_observations_unavailable",
            )
        raw_rows = [
            dict(row)
            for row in daily_method(
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                limit=limit,
            )
        ]
        observations = aggregate_search_console_daily(raw_rows)
        forecast = forecast_search_traffic(
            observations,
            horizon_days=horizon_days,
            timesfm_provider=configured_timesfm_provider(),
        )
        return {
            "schema_version": "empire.search_traffic_forecast.v1",
            "mode": "SHADOW_COMPARE",
            "execution_authority": "none",
            "search_console_site": status.site_url,
            "observed_rows": len(observations),
            "forecast": forecast.as_dict(),
        }

    @router.get("/summary")
    def summary():
        base = {
            **search_health(),
            "repository_available": repository is not None,
            "api_contract_version": "search-v1",
        }
        if repository is None:
            return {
                **base,
                "stored_metrics": (
                    "unavailable_until_canonical_repository_activation"
                ),
            }
        return {
            **base,
            "stored_metrics": dict(repository.summary()),
        }

    def _collection(name: str, limit: int):
        if repository is None:
            _repository_unavailable()
        method = getattr(repository, name)
        bounded = bounded_limit(limit)
        return collection_payload(
            method(limit=bounded),
            limit=bounded,
        )


    def _product_capabilities() -> dict[str, bool | None]:
        repo = repository is not None
        console_status = search_console.status()
        return {
            "native_crawler": True,
            "lighthouse_parser": True,
            "lighthouse_runner": False,
            "rank_history": True,
            "local_grid": True,
            "pages": repo,
            "indexation": repo,
            "opportunities": repo,
            "decay": repo,
            "cannibalisation": repo,
            "internal_links": repo,
            "ai_visibility": repo,
            "backlinks": repo,
            "revenue": repo,
            "search_console": bool(console_status.available),
            "serp": True,
            "competitor_gap": True,
            "citation_gap": True,
            "traffic_forecast": True,
            "timesfm_shadow": bool(
                configured_timesfm_provider().status().get("available")
            ),
        }

    @router.get("/products")
    def products():
        return {
            "schema_version": "empire.search.products.v1",
            "mode": "OBSERVE",
            "commercial_terms_required": True,
            "pricing_observed": False,
            "execution_allowed": False,
            "count": len(product_catalog()),
            "items": product_catalog(),
        }

    @router.get("/products/readiness")
    def products_readiness():
        capabilities = _product_capabilities()
        return {
            "schema_version": "empire.search.product-readiness.v1",
            "mode": "OBSERVE",
            "execution_allowed": False,
            "capabilities": capabilities,
            "items": product_portfolio_readiness(capabilities),
        }

    @router.get("/products/{product_key}")
    def product_detail(product_key: str):
        product = get_search_product(product_key)
        if product is None:
            raise HTTPException(status_code=404, detail="search_product_not_found")
        capabilities = _product_capabilities()
        readiness = next(
            row
            for row in product_portfolio_readiness(capabilities)
            if row["product_key"] == product.key
        )
        return {
            "schema_version": "empire.search.product.v1",
            "mode": "OBSERVE",
            "execution_allowed": False,
            "product": product.as_dict(),
            "readiness": readiness,
        }

    @router.post("/local-grid/preview")
    def local_grid_preview(req: LocalGridPreviewRequest):
        try:
            observations = tuple(
                LocalGridObservation(
                    query=item.query,
                    latitude=item.latitude,
                    longitude=item.longitude,
                    observed_at=item.observed_at,
                    engine=item.engine,
                    provenance=tuple(item.provenance),
                    position=item.position,
                )
                for item in req.observations
            )
            analysis = analyse_local_grid(
                observations,
                query=req.query,
                engine=req.engine,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "schema_version": "empire.search.local-grid.v1",
            "mode": "OBSERVE",
            "execution_allowed": False,
            "analysis": analysis,
        }

    @router.post("/rank-history/preview")
    def rank_history_preview(req: RankHistoryPreviewRequest):
        try:
            observations = tuple(
                RankObservation(
                    query=item.query,
                    url=item.url,
                    observed_at=item.observed_at,
                    position=item.position,
                    engine=item.engine,
                    source=item.source,
                    provenance=tuple(item.provenance),
                )
                for item in req.observations
            )
            analysis = analyse_rank_history(
                observations,
                query=req.query,
                url=req.url,
                engine=req.engine,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "schema_version": "empire.search.rank-history.v1",
            "mode": "OBSERVE",
            "execution_allowed": False,
            "analysis": analysis,
        }

    @router.get("/performance/status")
    def performance_status():
        return lighthouse_parser_status()

    @router.post("/performance/lighthouse/parse")
    def performance_lighthouse_parse(req: LighthouseReportRequest):
        try:
            return parse_lighthouse_report(req.report)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/products/{product_key}/report/preview")
    def product_report_preview(
        product_key: str,
        req: SearchProductReportRequest,
    ):
        try:
            return build_search_product_report(
                product_key=product_key,
                site=req.site,
                generated_at=req.generated_at,
                evidence=req.evidence,
            )
        except ValueError as exc:
            detail = str(exc)
            status = 404 if detail == "search product not found" else 422
            raise HTTPException(status_code=status, detail=detail) from exc

    @router.post("/crawl/preview")
    def crawl_preview(req: CrawlPreviewRequest):
        try:
            return crawl_search_site(
                req.url,
                max_pages=req.max_pages,
                request_timeout=req.request_timeout_seconds,
                time_budget_seconds=req.time_budget_seconds,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get("/pages")
    def pages(limit: int = Query(default=100, ge=1, le=500)):
        return _collection("pages", limit)

    @router.get("/opportunities")
    def opportunities(limit: int = Query(default=100, ge=1, le=500)):
        return _collection("opportunities", limit)

    @router.get("/indexation")
    def indexation(limit: int = Query(default=100, ge=1, le=500)):
        return _collection("indexation", limit)

    @router.get("/decay")
    def decay(limit: int = Query(default=100, ge=1, le=500)):
        return _collection("decay", limit)

    @router.get("/cannibalisation")
    def cannibalisation(limit: int = Query(default=100, ge=1, le=500)):
        return _collection("cannibalisation", limit)

    @router.get("/alerts")
    def alerts(limit: int = Query(default=100, ge=1, le=500)):
        return _collection("alerts", limit)

    @router.get("/revenue")
    def revenue(limit: int = Query(default=100, ge=1, le=500)):
        return _collection("revenue", limit)

    @router.get("/internal-links")
    def internal_links(limit: int = Query(default=200, ge=1, le=500)):
        return _collection("internal_links", limit)

    @router.get("/ai-visibility")
    def ai_visibility(limit: int = Query(default=200, ge=1, le=500)):
        return _collection("ai_visibility", limit)

    @router.post("/citation-gap/preview")
    def citation_gap_preview(req: CitationGapPreviewRequest):
        try:
            observations = tuple(
                AiCitationObservation(
                    query=item.query,
                    engine=item.engine,
                    observed_at=item.observed_at,
                    cited_url=item.cited_url,
                    source_url=item.source_url,
                    citation_position=item.citation_position,
                    mention_text=item.mention_text,
                    provenance=tuple(item.provenance),
                )
                for item in req.observations
            )
            analysis = analyse_citation_gap(
                observations,
                query=req.query,
                engine=req.engine,
                empire_domains=tuple(req.empire_domains),
                competitor_domains=tuple(req.competitor_domains),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "recommendation_only": True,
            "execution_allowed": False,
            "analysis": analysis.as_dict(),
        }

    @router.get("/backlinks")
    def backlinks(limit: int = Query(default=200, ge=1, le=500)):
        return _collection("backlinks", limit)

    @router.post("/backlinks/preview")
    def backlinks_preview(req: BacklinkGraphPreviewRequest):
        try:
            observations = tuple(
                BacklinkObservation(
                    source_url=item.source_url,
                    target_url=item.target_url,
                    observed_at=item.observed_at,
                    anchor_text=item.anchor_text,
                    rel=item.rel,
                    source=item.source,
                    provenance=tuple(item.provenance),
                )
                for item in req.observations
            )
            analysis = analyse_backlink_graph(
                observations,
                empire_domains=tuple(req.empire_domains),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "recommendation_only": True,
            "execution_allowed": False,
            "link_building_execution": False,
            "authority_score_invented": False,
            "analysis": analysis.as_dict(),
        }

    @router.post("/ai-visibility/preview")
    def ai_visibility_preview(req: AiVisibilityPreviewRequest):
        try:
            observations = tuple(
                AiCitationObservation(
                    query=item.query,
                    engine=item.engine,
                    observed_at=item.observed_at,
                    cited_url=item.cited_url,
                    source_url=item.source_url,
                    citation_position=item.citation_position,
                    mention_text=item.mention_text,
                    provenance=tuple(item.provenance),
                )
                for item in req.observations
            )
            analysis = analyse_ai_visibility(
                observations,
                empire_domains=tuple(req.empire_domains),
                query=req.query,
                engine=req.engine,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "recommendation_only": True,
            "execution_allowed": False,
            "analysis": analysis.as_dict(),
        }

    @router.post("/revenue/preview")
    def revenue_attribution_preview(req: RevenueAttributionPreviewRequest):
        try:
            preview = preview_search_revenue_attribution(
                site_id=req.site_id,
                page_id=req.page_id,
                query=req.query,
                external_session_id=req.external_session_id,
                prospect_id=req.prospect_id,
                opportunity_id=req.opportunity_id,
                attribution_kind=req.attribution_kind,
                commercial_event=req.commercial_event,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "recommendation_only": True,
            "execution_allowed": False,
            "preview": preview.as_dict(),
        }

    @router.post("/revenue/review/preview")
    def revenue_attribution_review_preview(
        req: RevenueAttributionReviewRequest,
    ):
        try:
            review = review_search_attribution(
                site_id=req.site_id,
                page_id=req.page_id,
                query=req.query,
                external_session_id=req.external_session_id,
                prospect_id=req.prospect_id,
                opportunity_id=req.opportunity_id,
                attribution_kind=req.attribution_kind,
                commercial_event=req.commercial_event,
                search_touch_observed_at=req.search_touch_observed_at,
                touch_evidence_ref=req.touch_evidence_ref,
                observed_cost_cents=req.observed_cost_cents,
                cost_evidence_ref=req.cost_evidence_ref,
                max_attribution_lag_seconds=(
                    req.max_attribution_lag_seconds
                ),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "recommendation_only": True,
            "execution_allowed": False,
            "publishing_execution": False,
            "indexation_execution": False,
            "revenue_mutation": False,
            "accounting_mutation": False,
            "review": review.as_dict(),
        }

    @router.post("/serp/snapshot")
    def serp_snapshot(req: SerpQueryRequest):
        try:
            snapshot = SearchFabricSerpAdapter().snapshot(
                req.query,
                num=req.num,
                engine=req.engine,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"serp_snapshot_unavailable:{type(exc).__name__}",
            ) from exc
        return {
            "schema_version": "empire.search.serp-snapshot.v1",
            "mode": "OBSERVE",
            "execution_allowed": False,
            "commercial_product": "serp_intelligence_api",
            "snapshot": snapshot.as_dict(),
        }

    @router.post("/competitor-gap/preview")
    def competitor_gap_preview(req: CompetitorGapPreviewRequest):
        snapshot = SerpSnapshot(
            query=req.snapshot.query,
            observed_at=req.snapshot.observed_at,
            engine=req.snapshot.engine,
            quality_gate=req.snapshot.quality_gate,
            cache=req.snapshot.cache,
            available=req.snapshot.available,
            results=tuple(
                SerpResultEvidence(
                    title=item.title,
                    url=item.url,
                    snippet=item.snippet,
                    position=item.position,
                    engine=item.engine,
                    relevance_score=item.relevance_score,
                    provenance=tuple(item.provenance),
                )
                for item in req.snapshot.results
            ),
            error=req.snapshot.error,
        )
        analysis = analyse_competitor_gap(
            snapshot,
            empire_domains=req.empire_domains,
        )
        return {
            "mode": "OBSERVE",
            "recommendation_only": True,
            "execution_allowed": False,
            "analysis": analysis.as_dict(),
            "opportunity_inputs": analysis.opportunity_inputs(),
        }

    @router.post("/analyse")
    def analyse(req: AnalyseRequest):
        page = SearchPage(**req.page)
        opportunity = (
            SearchOpportunity(**req.opportunity)
            if req.opportunity
            else None
        )
        return SearchCommanderAgent().analyse(
            page=page,
            quality_factors=req.quality_factors,
            opportunity=opportunity,
        )

    @router.post("/page/validate")
    def page_validate(req: PageValidateRequest):
        return asdict(
            ContentQualityEvaluator().evaluate(req.quality_factors)
        )

    @router.post("/schema/preview")
    def schema_preview(req: SchemaPreviewRequest):
        return asdict(
            generate_schema_preview(
                req.schema_type,
                req.visible_content,
            )
        )

    @router.post("/metadata/preview")
    def metadata_preview(req: MetadataPreviewRequest):
        page = SearchPage(**req.page)
        quality = ContentQualityEvaluator().evaluate(
            req.quality_factors
        )
        return asdict(
            generate_metadata(page, quality=quality)
        )

    return router


router = create_search_router(
    configured_search_repository_from_env()
)
