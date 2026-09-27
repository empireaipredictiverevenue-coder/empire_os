from empire_os.category_strategy import (
    category_gap_plan,
    compare_category_snapshots,
    review_category_position,
)


def row(score=.8):
    return {
        "category_key":"predictive-revenue",
        "category_name":"Predictive Revenue Operating System",
        "narrative":"See revenue earlier and close the loop to realized GP.",
        "evidence_refs":["strategy:1"],
        "proof_refs":["proof:1"],
        "category_clarity":score,
        "problem_urgency":score,
        "differentiation":score,
        "proof_strength":score,
        "search_presence":score,
        "ai_citation_presence":score,
        "content_authority":score,
        "partner_amplification":score,
        "customer_language_alignment":score,
        "commercial_conversion_evidence":score,
    }


def test_category_review_never_claims_leadership():
    r=review_category_position(row())
    assert r["review_ready"] is True
    assert r["category_strength_available"] is True
    assert r["leadership_claimed"] is False
    assert r["publishing_enabled"] is False


def test_unknown_dimension_stays_unknown():
    x=row()
    x["search_presence"]=None
    r=review_category_position(x)
    assert r["category_strength_available"] is False
    assert "search_presence" in r["missing_dimensions"]


def test_gap_plan_is_recommendation_only():
    r=category_gap_plan(row(.5))
    assert r["gaps"][0]["gap_to_full_strength"] == .5
    assert r["publishing_enabled"] is False


def test_category_compare_selects_no_winner():
    a=row(.9)
    b=row(.5)
    b["category_key"]="market-intelligence"
    b["category_name"]="Market Intelligence"
    r=compare_category_snapshots([b,a])
    assert r["categories"][0]["category_key"]=="predictive-revenue"
    assert r["winner_selected"] is False
    assert r["leadership_claimed"] is False
