"""FastAPI routes for the Search Intelligence foundation."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .commander import SearchCommanderAgent
from .competitor_gap import analyse_competitor_gap
from .health import search_health
from .metadata import generate_metadata
from .models import SearchOpportunity, SearchPage
from .quality import ContentQualityEvaluator
from .repository import SearchRepository, bounded_limit, collection_payload
from .postgres_repository import configured_search_repository_from_env
from .schema import generate_schema_preview
from .search_console import (
    SearchConsoleAdapter,
    configured_search_console_adapter,
)
from .serp import SerpResultEvidence, SerpSnapshot


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
