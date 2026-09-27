"""Category ownership strategy for Empire.

Recommendation-only. Does not publish, claim category leadership, or mutate
marketing/search surfaces.
"""
from __future__ import annotations
from typing import Any, Iterable, Mapping


DIMENSIONS = (
    "category_clarity",
    "problem_urgency",
    "differentiation",
    "proof_strength",
    "search_presence",
    "ai_citation_presence",
    "content_authority",
    "partner_amplification",
    "customer_language_alignment",
    "commercial_conversion_evidence",
)


def _text(v: Any) -> str:
    return str(v or "").strip()


def _prob(v: Any, name: str) -> float | None:
    if v is None or v == "":
        return None
    try:
        x=float(v)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not 0 <= x <= 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return x


def review_category_position(raw: Mapping[str, Any]) -> dict[str, Any]:
    category_key=_text(raw.get("category_key"))
    category_name=_text(raw.get("category_name"))
    narrative=_text(raw.get("narrative"))
    blockers=[]
    if not category_key: blockers.append("category_key_required")
    if not category_name: blockers.append("category_name_required")
    if not narrative: blockers.append("narrative_required")
    if not raw.get("evidence_refs"): blockers.append("evidence_refs_required")
    if not raw.get("proof_refs"): blockers.append("proof_refs_required")

    values={name:_prob(raw.get(name),name) for name in DIMENSIONS}
    missing=[k for k,v in values.items() if v is None]
    score=None
    if not missing:
        weights={
            "category_clarity":.12,
            "problem_urgency":.12,
            "differentiation":.14,
            "proof_strength":.14,
            "search_presence":.08,
            "ai_citation_presence":.07,
            "content_authority":.09,
            "partner_amplification":.06,
            "customer_language_alignment":.08,
            "commercial_conversion_evidence":.10,
        }
        score=sum(values[k]*w for k,w in weights.items())

    return {
        "schema_version":"category_position_review.v1",
        "category_key":category_key or None,
        "category_name":category_name or None,
        "narrative":narrative or None,
        "review_ready":not blockers,
        "blockers":blockers,
        "category_strength_available":score is not None,
        "category_strength_score":round(score,6) if score is not None else None,
        "missing_dimensions":missing,
        "leadership_claimed":False,
        "market_share_inferred":False,
        "publishing_enabled":False,
        "execution_authority":"none",
    }


def category_gap_plan(raw: Mapping[str, Any]) -> dict[str, Any]:
    reviewed=review_category_position(raw)
    gaps=[]
    for name in DIMENSIONS:
        value=_prob(raw.get(name),name)
        if value is None:
            gaps.append({"dimension":name,"status":"unknown","priority":None})
        else:
            gaps.append({
                "dimension":name,
                "status":"observed",
                "observed_value":value,
                "gap_to_full_strength":round(1-value,6),
                "priority":round(1-value,6),
            })
    gaps.sort(key=lambda x:(x.get("priority") is not None,x.get("priority") or -1),reverse=True)
    return {
        "schema_version":"category_gap_plan.v1",
        "category":reviewed,
        "gaps":gaps,
        "recommended_workstreams":[
            "category_vocabulary",
            "proof_system",
            "search_topic_authority",
            "ai_citation_authority",
            "research_led_content",
            "comparison_education",
            "partner_amplification",
            "customer_language_feedback",
        ],
        "publishing_enabled":False,
        "execution_authority":"none",
    }


def compare_category_snapshots(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    snapshots=[]
    for raw in rows:
        item=review_category_position(raw)
        snapshots.append(item)
    snapshots.sort(
        key=lambda x:(
            x["category_strength_available"],
            x["category_strength_score"] if x["category_strength_score"] is not None else -1,
            x["category_key"] or "",
        ),
        reverse=True,
    )
    for i,row in enumerate(snapshots,1):
        row["review_rank"]=i
    return {
        "schema_version":"category_portfolio_review.v1",
        "categories":snapshots,
        "winner_selected":False,
        "leadership_claimed":False,
        "execution_authority":"none",
    }
