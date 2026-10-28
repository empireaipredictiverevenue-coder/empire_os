"""Decision-grade research investment screen, not an autonomous site publisher."""
from datetime import date
from pathlib import Path
import json

import pytest

from empire_os.microsite_ranked_production_queue_v4 import (
    _executive_screen, _executive_portfolio, build_ranked_microsite_queue,
)
from empire_os.microsite_commercial_intelligence_v3 import build_microsite_commercial_review
from empire_os.predictive_microsite_factory import build_candidate


def manchester():
    # Portable schema fixture only: no GOV.UK text is asserted as fact here.
    # Real source research lives separately in original private EmpireOS stage.
    path=Path(__file__).parent/"fixtures/predictive_microsite_factory_sample_20261026.json"
    spec=json.loads(path.read_text())["candidates"][1]
    urls=[
        "https://www.gov.uk/apply-boiler-upgrade-scheme/check-if-youre-eligible",
        "https://www.manchester.gov.uk/planning-and-regeneration/planning/planning-permission/see-or-comment-on-planning-applications",
        "https://www.ofgem.gov.uk/",
    ]
    spec["local_facts"]=[
        {"statement":f"Example source-linked research claim {i}: check the original page before relying on this claim.",
         "source_ref":f"fixture-official-source-{i}","checked_at":"2026-10-28T18:00:00Z",
         "official_url":url}
        for i,url in enumerate(urls,1)
    ]
    spec["research_steps"]=[
        "Check the current government eligibility conditions for an individual home.",
        "Compare the actual Manchester council planning record with the actual property.",
        "Review the official regulator guidance before choosing a specific heating installation.",
        "Ask an appropriately certified installer to confirm the real home and project scope.",
    ]
    return spec


def screened_candidate():
    proposal, _ = build_candidate(manchester())
    return proposal


def test_source_distinct_research_without_gsc_is_demand_due_diligence():
    result = _executive_screen(
        screened_candidate(), exact_gsc=False, buyer_guidance=False,
        calibrated=False, today=date(2026,10,28))
    assert result["research_desk_qualified"] is True
    assert result["decision"] == "MEASURE_FIRST_PARTY_INTENT"
    assert result["research_evidence"]["direct_official_source_links"] == 3
    assert result["research_evidence"]["actionable_research_steps"] == 4
    assert result["research_evidence"]["source_dates_independently_verified"] is False
    assert result["independent_source_claims_verified"] is False
    assert result["expected_revenue_minor"] is None
    assert result["expected_traffic"] is None
    assert result["roi"] is None
    assert result["commercial_investment_authorized"] is False


def test_original_existing_queue_never_invents_executive_shortlist():
    sample=Path(__file__).parent/"fixtures/predictive_microsite_factory_sample_20261026.json"
    specs=json.loads(sample.read_text())["candidates"]
    commercial=build_microsite_commercial_review(specs,now="2026-10-28T18:00:00Z")
    result=build_ranked_microsite_queue(specs,commercial=commercial,as_of=date(2026,10,28))
    assert result["executive_portfolio"]["research_shortlist_max_three_markets"] == []
    assert result["executive_portfolio"]["verified_revenue_minor"] is None
    assert result["executive_portfolio"]["publication_authorized"] is False
    assert result["publishable_count"] == 0
    assert all(row["executive_screen"]["expected_revenue_minor"] is None for row in result["rows"])
    assert all(row["executive_screen"]["decision"]=="SOURCE_REPAIR_FIRST" for row in result["rows"])


def test_authored_source_date_refresh_prevents_research_shortlist():
    candidate = screened_candidate()
    result=_executive_screen(candidate,exact_gsc=False,buyer_guidance=False,calibrated=False,today=date(2027,3,30))
    assert result["decision"] == "SOURCE_REFRESH_FIRST"
    assert not result["research_desk_qualified"]
    assert result["research_evidence"]["author_dated_within_90_days"] is False


def test_future_dated_author_source_must_be_rechecked():
    candidate = screened_candidate()
    result=_executive_screen(candidate,exact_gsc=False,buyer_guidance=False,calibrated=False,today=date(2026,10,27))
    assert result["decision"]=="SOURCE_REFRESH_FIRST"


def test_no_independently_measured_demand_never_becomes_investment_approval():
    packet=screened_candidate()
    for observed,buyer,expected in [
        (False,False,"MEASURE_FIRST_PARTY_INTENT"),
        (True,False,"RESEARCH_COMMERCIAL_PATH"),
        (True,True,"EVALUATE_ONE_BOUNDED_EXPERIMENT"),
    ]:
        # True flags in this test are deliberately synthetic; in normal runs
        # they come only from the strict original GSC and buyer readers.
        result=_executive_screen(
            packet, exact_gsc=observed, buyer_guidance=buyer,
            calibrated=True, today=date(2026,10,28))
        assert result["decision"]==expected
        assert result["owner_publication_authorized"] is False
        assert result["commercial_investment_authorized"] is False
        assert result["customer_economics_verified"] is False
        assert result["expected_traffic"] is None


def test_swapped_location_copy_cannot_make_it_to_shortlist():
    packet=screened_candidate()
    packet["blockers"].append("near-duplicate location-swapped editorial content versus other")
    result=_executive_screen(packet,exact_gsc=True,buyer_guidance=True,calibrated=True,today=date(2026,10,28))
    assert result["decision"]=="SOURCE_REPAIR_FIRST"
    assert result["research_desk_qualified"] is False


def test_research_portfolio_selects_max_three_distinct_markets():
    rows=[]
    for rank,market in enumerate(["GB-MAN","GB-MAN","GB-LON","US-CO","US-TX"],1):
        rows.append({
            "market_id":market,
            "candidate_id":f"microsite_fake_{rank}",
            "research_rank":rank,
            "executive_screen":{"research_desk_qualified":True,
                                "next_best_evidence_action":"Verify exact original-source question"},
        })
    result=_executive_portfolio(rows)
    selected=result["research_shortlist_max_three_markets"]
    assert [x["market_id"] for x in selected]==["GB-MAN","GB-LON","US-CO"]
    assert len(selected)==3
    assert result["publication_authorized"] is False
    assert result["commercial_budget_authorized"] is False


def test_original_queue_rejects_invalid_as_of():
    spec=manchester()
    c=build_microsite_commercial_review([spec],now="2026-10-28T18:00:00Z")
    with pytest.raises(ValueError,match="as_of"):
        build_ranked_microsite_queue([spec],commercial=c,as_of="2026-10-28")


def test_two_fact_claims_citing_one_official_url_are_not_independent_evidence():
    proposal=screened_candidate()
    link=proposal["content_evidence"][0]["official_url"]
    for item in proposal["content_evidence"]:
        item["official_url"]=link
    screened=_executive_screen(
        proposal,exact_gsc=True,buyer_guidance=True,calibrated=True,today=date(2026,10,28))
    assert screened["research_evidence"]["direct_official_source_links"] == 1
    assert screened["decision"] == "SOURCE_REPAIR_FIRST"
    assert screened["research_desk_qualified"] is False
