"""Strategic partnership portfolio review.

No outreach, contracting, exclusivity, spend, or commercial activation.
"""
from __future__ import annotations
from typing import Any, Iterable, Mapping


PARTNER_TYPES={
    "agency",
    "data_provider",
    "platform",
    "trade_group",
    "affiliate",
    "software_integration",
    "distribution",
    "research",
    "technology",
}

DIMENSIONS=(
    "strategic_fit",
    "distribution_reach",
    "data_synergy",
    "product_synergy",
    "commercial_economics",
    "brand_trust",
    "learning_value",
    "switching_cost_value",
    "execution_feasibility",
)


def _text(v: Any)->str:
    return str(v or "").strip()


def _prob(v: Any,name:str)->float|None:
    if v is None or v=="":
        return None
    try:
        x=float(v)
    except (TypeError,ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not 0<=x<=1:
        raise ValueError(f"{name} must be between 0 and 1")
    return x


def review_partner_candidate(raw: Mapping[str,Any])->dict[str,Any]:
    partner_key=_text(raw.get("partner_key"))
    partner_type=_text(raw.get("partner_type")).lower()
    blockers=[]
    if not partner_key: blockers.append("partner_key_required")
    if partner_type not in PARTNER_TYPES: blockers.append("unsupported_partner_type")
    if not _text(raw.get("strategic_thesis")): blockers.append("strategic_thesis_required")
    if not raw.get("evidence_refs"): blockers.append("evidence_refs_required")

    vals={k:_prob(raw.get(k),k) for k in DIMENSIONS}
    exclusivity_risk=_prob(raw.get("exclusivity_risk"),"exclusivity_risk")
    dependency_risk=_prob(raw.get("dependency_risk"),"dependency_risk")
    missing=[k for k,v in vals.items() if v is None]
    if exclusivity_risk is None: missing.append("exclusivity_risk")
    if dependency_risk is None: missing.append("dependency_risk")

    score=None
    if not missing:
        weights={
            "strategic_fit":.18,
            "distribution_reach":.14,
            "data_synergy":.13,
            "product_synergy":.13,
            "commercial_economics":.13,
            "brand_trust":.08,
            "learning_value":.08,
            "switching_cost_value":.07,
            "execution_feasibility":.06,
        }
        positive=sum(vals[k]*w for k,w in weights.items())
        risk_penalty=.08*exclusivity_risk + .08*dependency_risk
        score=max(0.0,positive-risk_penalty)

    return {
        "schema_version":"strategic_partner_review.v1",
        "partner_key":partner_key or None,
        "partner_type":partner_type or None,
        "review_ready":not blockers,
        "blockers":blockers,
        "score_available":score is not None,
        "strategic_score":round(score,6) if score is not None else None,
        "missing_dimensions":missing,
        "outreach_enabled":False,
        "contracting_enabled":False,
        "exclusivity_enabled":False,
        "spend_enabled":False,
        "execution_authority":"none",
    }


def build_partnership_portfolio(rows: Iterable[Mapping[str,Any]])->dict[str,Any]:
    reviewed=[]
    seen=set()
    for raw in rows:
        item=review_partner_candidate(raw)
        key=item["partner_key"]
        if key:
            if key in seen:
                raise ValueError("duplicate partner_key")
            seen.add(key)
        reviewed.append(item)
    reviewed.sort(
        key=lambda x:(
            x["score_available"],
            x["strategic_score"] if x["strategic_score"] is not None else -1,
            x["partner_key"] or "",
        ),
        reverse=True,
    )
    for i,item in enumerate(reviewed,1):
        item["portfolio_rank"]=i
    return {
        "schema_version":"strategic_partnership_portfolio.v1",
        "partners":reviewed,
        "winner_selected":False,
        "outreach_enabled":False,
        "contracting_enabled":False,
        "execution_authority":"none",
    }


def partnership_gap_map(rows: Iterable[Mapping[str,Any]])->dict[str,Any]:
    portfolio=build_partnership_portfolio(rows)
    coverage={ptype:0 for ptype in sorted(PARTNER_TYPES)}
    for item in portfolio["partners"]:
        if item["review_ready"] and item["partner_type"] in coverage:
            coverage[item["partner_type"]]+=1
    gaps=[ptype for ptype,count in coverage.items() if count==0]
    return {
        "schema_version":"strategic_partnership_gap_map.v1",
        "coverage":coverage,
        "gaps":gaps,
        "recommended_only":True,
        "outreach_enabled":False,
        "execution_authority":"none",
    }
