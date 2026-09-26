import pytest

from empire_os.company_operating_system import (
    build_founder_brief,
    rank_initiatives,
    review_marketing_brief,
    review_rd_candidate,
)


def initiative(iid, department="marketing", score=0.8, gp=100000):
    return {
        "initiative_id": iid,
        "title": f"Initiative {iid}",
        "department": department,
        "owner": "owner-1",
        "state": "planned",
        "objective": "Create measurable commercial value.",
        "expected_gross_profit_cents": gp,
        "strategic_impact": score,
        "urgency": score,
        "confidence": score,
        "risk": 0.2,
        "reversibility": 0.9,
        "effort": 0.3,
        "value_of_information_cents": 10000,
        "evidence_refs": [f"e:{iid}"],
        "blockers": [],
    }


def test_ranked_portfolio_is_non_executing():
    result = rank_initiatives([
        initiative("a", score=0.9, gp=500000),
        initiative("b", score=0.5, gp=100000),
    ])
    assert result["ranked"][0]["initiative_id"] == "a"
    assert result["ranked"][0]["rank"] == 1
    assert result["portfolio_mutation"] is False
    assert result["execution_authority"] == "none"


def test_unknown_priority_inputs_are_not_invented():
    row = initiative("x")
    row["confidence"] = None
    result = rank_initiatives([row])
    assert result["ranked"] == []
    assert result["unscored"][0]["priority"]["available"] is False
    assert "confidence" in result["unscored"][0]["priority"]["missing"]


def test_founder_brief_only_accepts_verified_outcomes():
    brief = build_founder_brief(
        date="2026-09-20",
        verified_outcomes=[
            {"outcome_ref": "o1", "verified": True, "gross_profit_cents": 50000},
            {"outcome_ref": "o2", "verified": False, "gross_profit_cents": 999999},
        ],
        initiatives=[initiative("a")],
        decisions_needed=[{
            "decision_id": "d1", "tier": "weekly", "summary": "Choose launch sequence",
            "owner": "founder", "evidence_refs": ["e:d1"],
        }],
        risks=[],
    )
    assert len(brief["verified_outcomes"]) == 1
    assert brief["verified_outcomes"][0]["outcome_ref"] == "o1"
    assert brief["execution_authority"] == "none"


def test_rd_transfer_requires_independent_review_and_transfer_package():
    blocked = review_rd_candidate({
        "research_id": "r1",
        "stage": "transfer_ready",
        "hypothesis": "New model improves calibration.",
        "evidence_refs": ["e:r1"],
        "baseline_ref": "baseline:1",
        "evaluation_ref": "eval:1",
        "independent_review_passed": False,
    })
    assert blocked["review_ready"] is False
    assert "independent_review_required" in blocked["blockers"]
    assert "transfer_target_required" in blocked["blockers"]
    assert blocked["production_deployment"] is False

    ready = review_rd_candidate({
        "research_id": "r2",
        "stage": "transfer_ready",
        "hypothesis": "New model improves calibration.",
        "evidence_refs": ["e:r2"],
        "baseline_ref": "baseline:2",
        "evaluation_ref": "eval:2",
        "independent_review_passed": True,
        "transfer_target": "predictive-cloud",
        "productization_brief_ref": "brief:2",
        "synthetic_only": False,
    })
    assert ready["review_ready"] is True
    assert ready["product_launch"] is False


def test_marketing_brief_keeps_public_actions_gated():
    result = review_marketing_brief({
        "campaign_id": "c1",
        "objective": "Generate buyer demand",
        "audience": "UK roofing buyers",
        "product": "Territory Seat",
        "offer": "Evidence-backed territory review",
        "success_metric": "qualified buyer opportunities",
        "evidence_refs": ["market:1"],
        "attribution_plan": {"model": "first_party_events"},
        "public_publish": True,
        "outbound_send": True,
        "paid_spend_cents": 10000,
    })
    assert result["review_ready"] is False
    assert "public_publish_requires_separate_approval" in result["blockers"]
    assert result["publishing_enabled"] is False
    assert result["paid_spend_enabled"] is False


def test_duplicate_initiative_id_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        rank_initiatives([initiative("a"), initiative("a")])
