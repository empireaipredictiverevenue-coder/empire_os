"""Canonical-content repurposing and duplication guards for Media OS."""
from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable, Mapping


DERIVATIVE_TYPES = frozenset({
    "youtube_long_form",
    "youtube_short",
    "linkedin",
    "x",
    "blog",
    "newsletter",
    "sales_enablement",
    "product_education",
    "community_post",
})


def _normalize_text(value: str | None) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip().lower())
    return text


def content_fingerprint(
    *,
    topic: str,
    thesis: str,
    angle: str | None = None,
    hook: str | None = None,
) -> str:
    canonical = "||".join(
        _normalize_text(value)
        for value in (topic, thesis, angle, hook)
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_repurposing_plan(
    *,
    canonical_content_ref: str,
    derivative_types: Iterable[str],
    evidence_refs: Iterable[str],
) -> dict[str, Any]:
    content_ref = str(canonical_content_ref or "").strip()
    if not content_ref:
        raise ValueError("canonical_content_ref is required")
    refs = [str(x).strip() for x in evidence_refs if str(x).strip()]
    if not refs:
        raise ValueError("repurposing evidence_refs are required")

    derivatives = []
    for item in derivative_types:
        key = str(item).strip()
        if key not in DERIVATIVE_TYPES:
            raise ValueError(f"unsupported derivative type: {key}")
        derivatives.append({
            "content_type": key,
            "source_ref": content_ref,
            "new_factual_research_required": False,
            "source_lineage_required": True,
            "public_publish_authorized": False,
        })

    return {
        "schema_version": "empire.media.repurposing_plan.v1",
        "mode": "OBSERVE",
        "canonical_content_ref": content_ref,
        "evidence_refs": refs,
        "derivative_count": len(derivatives),
        "derivatives": derivatives,
        "independent_fact_regeneration_allowed": False,
        "public_publish_authorized": False,
        "execution_authority": "none",
    }


def duplication_guard(
    *,
    candidate: Mapping[str, Any],
    historical_items: Iterable[Mapping[str, Any]],
    similarity_threshold: float = 0.75,
) -> dict[str, Any]:
    topic = _normalize_text(candidate.get("topic"))
    title = _normalize_text(candidate.get("title"))
    hook = _normalize_text(candidate.get("hook"))
    thumb = _normalize_text(candidate.get("thumbnail_text"))

    def tokens(value: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9]+", value)
            if len(token) > 2
        }

    candidate_sets = {
        "topic": tokens(topic),
        "title": tokens(title),
        "hook": tokens(hook),
        "thumbnail_text": tokens(thumb),
    }

    matches = []
    for raw in historical_items:
        row = dict(raw)
        field_scores = {}
        for field, left in candidate_sets.items():
            right = tokens(_normalize_text(row.get(field)))
            union = left | right
            score = (
                len(left & right) / len(union)
                if union
                else 0.0
            )
            field_scores[field] = round(score, 4)
        max_score = max(field_scores.values(), default=0.0)
        if max_score >= float(similarity_threshold):
            matches.append({
                "historical_id": row.get("id"),
                "field_scores": field_scores,
                "max_similarity": round(max_score, 4),
            })

    return {
        "schema_version": "empire.media.duplication_guard.v1",
        "mode": "OBSERVE",
        "similarity_threshold": float(similarity_threshold),
        "duplicate_risk": bool(matches),
        "matches": matches,
        "machine_generated_repetition_guard": True,
        "automatic_rejection": False,
        "execution_authority": "none",
    }
