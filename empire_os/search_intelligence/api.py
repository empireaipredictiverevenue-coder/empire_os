"""FastAPI routes for the Search Intelligence foundation."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .commander import SearchCommanderAgent
from .health import search_health
from .metadata import generate_metadata
from .models import SearchOpportunity, SearchPage
from .quality import ContentQualityEvaluator
from .schema import generate_schema_preview

router = APIRouter(prefix="/v1/search", tags=["search-intelligence"])


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


@router.get("/health")
def health():
    return search_health()


@router.get("/summary")
def summary():
    return {
        **search_health(),
        "stored_metrics": "unavailable_until_canonical_repository_activation",
    }


def _repository_unavailable():
    raise HTTPException(
        status_code=503,
        detail="canonical_search_repository_not_activated",
    )


@router.get("/pages")
def pages():
    return _repository_unavailable()


@router.get("/opportunities")
def opportunities():
    return _repository_unavailable()


@router.get("/indexation")
def indexation():
    return _repository_unavailable()


@router.get("/decay")
def decay():
    return _repository_unavailable()


@router.get("/cannibalisation")
def cannibalisation():
    return _repository_unavailable()


@router.get("/alerts")
def alerts():
    return _repository_unavailable()


@router.get("/revenue")
def revenue():
    return _repository_unavailable()


@router.post("/analyse")
def analyse(req: AnalyseRequest):
    page = SearchPage(**req.page)
    opportunity = SearchOpportunity(**req.opportunity) if req.opportunity else None
    return SearchCommanderAgent().analyse(
        page=page,
        quality_factors=req.quality_factors,
        opportunity=opportunity,
    )


@router.post("/page/validate")
def page_validate(req: PageValidateRequest):
    return asdict(ContentQualityEvaluator().evaluate(req.quality_factors))


@router.post("/schema/preview")
def schema_preview(req: SchemaPreviewRequest):
    return asdict(generate_schema_preview(req.schema_type, req.visible_content))


@router.post("/metadata/preview")
def metadata_preview(req: MetadataPreviewRequest):
    page = SearchPage(**req.page)
    quality = ContentQualityEvaluator().evaluate(req.quality_factors)
    return asdict(generate_metadata(page, quality=quality))
