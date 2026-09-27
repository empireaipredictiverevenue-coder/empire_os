"""Safe JSON-LD preview generation from visible-content data only."""
from __future__ import annotations

from typing import Any, Mapping

from .models import SchemaPreview

ALLOWED_TYPES = {
    "Organization",
    "WebSite",
    "WebPage",
    "BreadcrumbList",
    "Article",
    "BlogPosting",
    "Service",
    "Product",
    "SoftwareApplication",
    "LocalBusiness",
    "Person",
    "VideoObject",
    "Event",
    "Offer",
    "FAQPage",
    "Dataset",
}
FORBIDDEN_KEYS = {
    "review",
    "reviews",
    "reviewRating",
    "aggregateRating",
    "award",
    "awards",
    "testimonial",
    "testimonials",
    "rating",
    "ratingValue",
    "ratingCount",
    "reviewCount",
}

def _sanitize_visible(value: Any, warnings: list[str], path: str = "") -> Any:
    if isinstance(value, Mapping):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            if key in FORBIDDEN_KEYS:
                label = f"{path}.{key}" if path else key
                warnings.append(f"blocked_unverified_field:{label}")
                continue
            cleaned = _sanitize_visible(
                item, warnings, f"{path}.{key}" if path else key
            )
            if cleaned not in (None, "", [], {}, ()):
                clean[key] = cleaned
        return clean
    if isinstance(value, (list, tuple)):
        return [
            cleaned
            for index, item in enumerate(value)
            if (cleaned := _sanitize_visible(
                item, warnings, f"{path}[{index}]"
            )) not in (None, "", [], {}, ())
        ]
    return value



def generate_schema_preview(
    schema_type: str,
    visible_content: Mapping[str, Any],
) -> SchemaPreview:
    if schema_type not in ALLOWED_TYPES:
        raise ValueError("unsupported schema type")

    warnings: list[str] = []
    body: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": schema_type,
    }
    for key, value in visible_content.items():
        if key in FORBIDDEN_KEYS:
            warnings.append(f"blocked_unverified_field:{key}")
            continue
        cleaned = _sanitize_visible(value, warnings, key)
        if cleaned in (None, "", [], {}, ()):
            continue
        body[key] = cleaned

    if schema_type == "FAQPage" and "mainEntity" not in body:
        warnings.append("faq_requires_visible_mainEntity")
    if schema_type == "Person" and "name" not in body:
        warnings.append("person_requires_visible_name")
    if schema_type == "Product" and "name" not in body:
        warnings.append("product_requires_visible_name")
    if schema_type == "LocalBusiness" and "name" not in body:
        warnings.append("local_business_requires_visible_name")

    return SchemaPreview(
        schema_type=schema_type,
        json_ld=body,
        warnings=tuple(warnings),
    )
