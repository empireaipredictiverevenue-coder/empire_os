"""FastAPI routes for the Search Intelligence foundation."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .commander import SearchCommanderAgent
from .health import search_health
from .metadata import generate_metadata
from .models import SearchOpportunity, SearchPage
from .quality import ContentQualityEvaluator
from .repository import SearchRepository, bounded_limit, collection_payload
from .postgres_repository import configured_search_repository_from_env
from .schema import generate_schema_preview


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


def _repository_unavailable() -> None:
    raise HTTPException(
        status_code=503,
        detail="canonical_search_repository_not_activated",
    )


def create_search_router(
    repository: SearchRepository | None = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/search",
        tags=["search-intelligence"],
    )

    @router.get("/health")
    def health():
        return {
            **search_health(),
            "repository_available": repository is not None,
            "api_contract_version": "search-v1",
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
