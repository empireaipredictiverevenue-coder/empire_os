import pytest
from empire_os.strategic_partnerships import (
    build_partnership_portfolio,
    partnership_gap_map,
    review_partner_candidate,
)


def partner(key="agency-1",ptype="agency",score=.8):
    return {
        "partner_key":key,
        "partner_type":ptype,
        "strategic_thesis":"Extend distribution and product reach.",
        "evidence_refs":[f"partner:{key}"],
        "strategic_fit":score,
        "distribution_reach":score,
        "data_synergy":score,
        "product_synergy":score,
        "commercial_economics":score,
        "brand_trust":score,
        "learning_value":score,
        "switching_cost_value":score,
        "execution_feasibility":score,
        "exclusivity_risk":.2,
        "dependency_risk":.2,
    }


def test_partner_review_never_enables_outreach_or_contracting():
    r=review_partner_candidate(partner())
    assert r["review_ready"] is True
    assert r["outreach_enabled"] is False
    assert r["contracting_enabled"] is False
    assert r["exclusivity_enabled"] is False


def test_partner_portfolio_ranks_but_selects_no_winner():
    r=build_partnership_portfolio([
        partner("a","agency",.9),
        partner("b","data_provider",.5),
    ])
    assert r["partners"][0]["partner_key"]=="a"
    assert r["winner_selected"] is False
    assert r["outreach_enabled"] is False


def test_partner_gap_map_exposes_missing_partner_types():
    r=partnership_gap_map([partner()])
    assert r["coverage"]["agency"]==1
    assert "data_provider" in r["gaps"]
    assert r["outreach_enabled"] is False


def test_duplicate_partner_rejected():
    with pytest.raises(ValueError,match="duplicate"):
        build_partnership_portfolio([partner(),partner()])
