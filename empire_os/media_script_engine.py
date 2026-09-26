"""Evidence-constrained Media OS script contracts.

This module creates deterministic script briefs for the existing model routing
layer. It does not call a provider directly and does not publish.
"""
from __future__ import annotations

from typing import Any, Mapping

from empire_os.media_os_foundation import CanonicalContentObject


SCRIPT_FORMATS: dict[str, tuple[str, ...]] = {
    "tutorial": (
        "HOOK",
        "PROMISE",
        "PROBLEM",
        "DEMO",
        "STEPS",
        "RESULT",
        "COMMON_FAILURE",
        "BETTER_METHOD",
        "CTA",
    ),
    "build_in_public": (
        "GOAL",
        "PROBLEM",
        "WHAT_WE_TRIED",
        "WHAT_FAILED",
        "WHAT_WE_BUILT",
        "LIVE_DEMO",
        "RESULT",
        "LESSON",
        "NEXT_STEP",
    ),
    "documentary": (
        "HOOK",
        "CONTEXT",
        "CONFLICT",
        "DISCOVERY",
        "ESCALATION",
        "TURN",
        "RESULT",
        "LESSON",
    ),
    "rapid_intelligence": (
        "WHAT_HAPPENED",
        "WHY_IT_MATTERS",
        "EVIDENCE",
        "IMPLICATIONS",
        "WHAT_TO_WATCH",
        "CTA",
    ),
}


def build_script_brief(
    content: CanonicalContentObject,
    *,
    script_format: str,
    target_duration_seconds: int | None = None,
) -> dict[str, Any]:
    content_row = content.as_dict()
    key = str(script_format or "").strip().lower()
    if key not in SCRIPT_FORMATS:
        raise ValueError("unsupported script_format")

    duration = None
    if target_duration_seconds is not None:
        duration = max(15, int(target_duration_seconds))

    claim_catalog = {
        f"claim-{index + 1}": {
            "text": claim["claim"],
            "claim_type": claim["claim_type"],
            "evidence_refs": list(claim["evidence_refs"]),
            "freshness_class": claim["freshness_class"],
            "uncertainty": claim["uncertainty"],
        }
        for index, claim in enumerate(content_row["claims"])
    }

    return {
        "schema_version": "empire.media.script_brief.v1",
        "mode": "OBSERVE",
        "content_id": content_row["content_id"],
        "topic": content_row["topic"],
        "thesis": content_row["thesis"],
        "audience": content_row["audience"],
        "script_format": key,
        "required_sections": list(SCRIPT_FORMATS[key]),
        "target_duration_seconds": duration,
        "claim_catalog": claim_catalog,
        "allowed_evidence_refs": sorted({
            *content_row["evidence_refs"],
            *[
                ref
                for claim in claim_catalog.values()
                for ref in claim["evidence_refs"]
            ],
        }),
        "stories": content_row["stories"],
        "examples": content_row["examples"],
        "visual_ideas": content_row["visual_ideas"],
        "cta": content_row["cta"],
        "uncertainty": content_row["uncertainty"],
        "instructions": {
            "factual_claims_must_reference_claim_ids": True,
            "invented_statistics_allowed": False,
            "invented_product_results_allowed": False,
            "unknown_remains_unknown": True,
            "counterarguments_should_be_preserved": True,
            "deceptive_manipulation_allowed": False,
            "premium_originality_required": True,
        },
        "provider_owner": "model_registry_and_intelligence_router",
        "public_publish_authorized": False,
        "execution_authority": "none",
    }


def validate_script_draft(
    brief: Mapping[str, Any],
    draft: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate structure and factual-claim lineage of a generated draft."""
    required = list(brief.get("required_sections") or [])
    sections = (
        dict(draft.get("sections"))
        if isinstance(draft.get("sections"), Mapping)
        else {}
    )
    missing_sections = [
        section
        for section in required
        if not str(sections.get(section) or "").strip()
    ]

    catalog = (
        dict(brief.get("claim_catalog"))
        if isinstance(brief.get("claim_catalog"), Mapping)
        else {}
    )
    cited_claim_ids = [
        str(value).strip()
        for value in (draft.get("claim_ids") or [])
        if str(value).strip()
    ]
    unknown_claim_ids = sorted({
        claim_id
        for claim_id in cited_claim_ids
        if claim_id not in catalog
    })

    unsupported_factual_claims = [
        str(value).strip()
        for value in (
            draft.get("unsupported_factual_claims") or []
        )
        if str(value).strip()
    ]

    ready = (
        not missing_sections
        and not unknown_claim_ids
        and not unsupported_factual_claims
    )

    return {
        "schema_version": "empire.media.script_validation.v1",
        "mode": "OBSERVE",
        "ready_for_storyboard_candidate": ready,
        "missing_sections": missing_sections,
        "unknown_claim_ids": unknown_claim_ids,
        "unsupported_factual_claims": unsupported_factual_claims,
        "claim_lineage_valid": (
            not unknown_claim_ids
            and not unsupported_factual_claims
        ),
        "public_publish_authorized": False,
        "execution_authority": "none",
    }
