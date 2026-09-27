"""Title/thumbnail creative package contracts for Empire Media OS."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import re
from typing import Any, Mapping


TITLE_DIMENSIONS = (
    "clarity",
    "specificity",
    "curiosity",
    "credibility",
    "promise",
    "audience_fit",
    "search_relevance",
    "novelty",
    "emotional_interest",
    "length_fit",
)

THUMBNAIL_DIMENSIONS = (
    "clarity",
    "curiosity",
    "contrast",
    "subject_dominance",
    "emotional_signal",
    "simplicity",
    "mobile_readability",
    "brand_consistency",
    "originality",
    "relevance",
)


def _score(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return max(0.0, min(1.0, number))


def _quality(
    dimensions: tuple[str, ...],
    values: Mapping[str, Any],
) -> dict[str, Any]:
    observed = {
        key: _score(values.get(key))
        for key in dimensions
    }
    known = [
        value
        for value in observed.values()
        if value is not None
    ]
    return {
        "dimensions": observed,
        "known_dimension_count": len(known),
        "quality_score": (
            round(sum(known) / len(known), 4)
            if known
            else None
        ),
        "classification": "CREATIVE_HEURISTIC",
    }


@dataclass(frozen=True)
class TitleCandidate:
    candidate_id: str
    text: str
    mode: str
    evidence_refs: tuple[str, ...]
    evaluator_scores: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        if not self.candidate_id.strip() or not self.text.strip():
            raise ValueError("title candidate id and text are required")
        if self.mode not in {"search_led", "browse_led", "hybrid"}:
            raise ValueError("unsupported title mode")
        if not self.evidence_refs:
            raise ValueError("title candidate evidence_refs are required")
        return {
            "candidate_id": self.candidate_id,
            "text": self.text,
            "mode": self.mode,
            "evidence_refs": list(self.evidence_refs),
            "evaluation": _quality(
                TITLE_DIMENSIONS,
                self.evaluator_scores,
            ),
        }


@dataclass(frozen=True)
class ThumbnailConcept:
    concept_id: str
    visual_question: str
    subject: str
    composition: str
    thumbnail_text: str | None
    evidence_refs: tuple[str, ...]
    rights_refs: tuple[str, ...] = ()
    evaluator_scores: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        if not self.concept_id.strip():
            raise ValueError("thumbnail concept_id is required")
        if not self.visual_question.strip():
            raise ValueError("thumbnail visual_question is required")
        if not self.subject.strip() or not self.composition.strip():
            raise ValueError("thumbnail subject/composition are required")
        if not self.evidence_refs:
            raise ValueError("thumbnail evidence_refs are required")
        return {
            "concept_id": self.concept_id,
            "visual_question": self.visual_question,
            "subject": self.subject,
            "composition": self.composition,
            "thumbnail_text": self.thumbnail_text,
            "evidence_refs": list(self.evidence_refs),
            "rights_refs": list(self.rights_refs),
            "evaluation": _quality(
                THUMBNAIL_DIMENSIONS,
                self.evaluator_scores,
            ),
        }


def _tokens(value: str | None) -> set[str]:
    return {
        token
        for token in re.findall(
            r"[a-z0-9]+",
            str(value or "").lower(),
        )
        if len(token) > 2
    }


def title_thumbnail_pair(
    title: TitleCandidate,
    thumbnail: ThumbnailConcept,
) -> dict[str, Any]:
    title_row = title.as_dict()
    thumb_row = thumbnail.as_dict()

    title_tokens = _tokens(title.text)
    thumb_tokens = _tokens(thumbnail.thumbnail_text)
    union = title_tokens | thumb_tokens
    overlap = (
        len(title_tokens & thumb_tokens) / len(union)
        if union
        else 0.0
    )
    repetition_state = (
        "HIGH_REPETITION"
        if overlap >= 0.65 and thumb_tokens
        else "COMPLEMENTARY"
    )

    title_quality = title_row["evaluation"]["quality_score"]
    thumb_quality = thumb_row["evaluation"]["quality_score"]
    known = [
        value
        for value in (title_quality, thumb_quality)
        if value is not None
    ]
    pair_quality = (
        round(sum(known) / len(known), 4)
        if known
        else None
    )

    return {
        "schema_version": "empire.media.creative_pair.v1",
        "title": title_row,
        "thumbnail": thumb_row,
        "message_token_overlap": round(overlap, 4),
        "repetition_state": repetition_state,
        "pair_quality_score": pair_quality,
        "classification": "CREATIVE_HEURISTIC",
        "experiment_required_for_causal_claim": True,
        "public_publish_authorized": False,
        "execution_authority": "none",
    }


def shortlist_creative_pairs(
    pairs: list[Mapping[str, Any]],
    *,
    limit: int = 3,
) -> dict[str, Any]:
    rows = [dict(row) for row in pairs]
    rows.sort(
        key=lambda row: (
            row.get("repetition_state") == "HIGH_REPETITION",
            -float(row.get("pair_quality_score") or -1),
        )
    )
    selected = rows[: max(1, min(int(limit), 3))]
    return {
        "schema_version": "empire.media.creative_shortlist.v1",
        "candidate_count": len(rows),
        "shortlist_count": len(selected),
        "shortlist": selected,
        "winner_declared": False,
        "experiment_required": True,
        "public_publish_authorized": False,
        "execution_authority": "none",
    }
