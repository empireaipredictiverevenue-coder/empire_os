"""Recommendation-only metadata generation."""
from __future__ import annotations

from .models import MetadataRecommendation, QualityResult, SearchPage


def generate_metadata(
    page: SearchPage,
    *,
    quality: QualityResult | None = None,
    language: str | None = None,
    author: str | None = None,
) -> MetadataRecommendation:
    robots = (
        "index,follow"
        if quality is not None and quality.eligible_for_approval
        else "noindex,follow"
    )
    warnings: list[str] = []
    if not page.title:
        warnings.append("missing_title")
    if not page.meta_description:
        warnings.append("missing_meta_description")
    if not page.canonical_url:
        warnings.append("missing_canonical")

    og = {
        key: value
        for key, value in {
            "type": page.page_type or "website",
            "title": page.title,
            "description": page.meta_description,
            "url": page.canonical_url,
        }.items()
        if value is not None
    }

    return MetadataRecommendation(
        title=page.title,
        meta_description=page.meta_description,
        canonical_url=page.canonical_url,
        robots=robots,
        open_graph=og,
        social=dict(og),
        language=language,
        author=author,
        publish_date=page.first_published_at,
        updated_date=page.last_modified_at,
        page_type=page.page_type,
        entity_context=page.entity_references,
        warnings=tuple(warnings),
    )
