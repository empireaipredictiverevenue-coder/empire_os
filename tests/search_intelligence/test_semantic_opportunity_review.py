"""Commercial semantics: many negative controls before recommendations."""
import pytest

from empire_os.search_intelligence.semantic_opportunity_review import (
    review_semantic_opportunity,
)


def test_explicit_service_request_not_a_verified_buyer_or_payment():
    r = review_semantic_opportunity(
        "Need a commercial roofing contractor in Chicago for a quote",
        ranked_results=[{"product_key": "roofing"}],
        source_kind="GSC_QUERY_PAGE", evidence_refs=["gsc:synthetic:1"],
    )
    assert r["intent_label"] == "SERVICE_REQUEST_TEXT_HYPOTHESIS"
    assert r["territory_review"]["geography_claim"] == "USA"
    assert r["recommended_review_action"] == "REVIEW_COMMERCIAL_FIT"
    assert r["source_kind"] == "GSC_QUERY_PAGE"
    assert r["original_evidence_refs"] == ["gsc:synthetic:1"]
    for gate in (
        "buyer_willingness_to_pay_verified", "buyer_identity_verified",
        "conversion_verified", "revenue_verified", "outbound_authorized",
        "publication_authorized", "search_volume_verified",
    ):
        assert r[gate] is False
    assert r["commercial_value_estimate"] is None


@pytest.mark.parametrize("query", [
    "roofing jobs chicago", "solar installer vacancies London",
    "hvac apprenticeship vacancies", "roofer salary Dallas",
    "apply for job as a commercial roofer",
    "roofing company hiring now",
])
def test_employment_queries_never_enter_buyer_lane(query):
    r = review_semantic_opportunity(query)
    assert r["intent_label"] == "EMPLOYMENT_OR_TRAINING_REVIEW"
    assert r["recommended_review_action"] == "EXCLUDE_AUTOMATIC_BUYER_ROUTING"


@pytest.mark.parametrize("query", [
    "what is a heat pump", "how does solar photovoltaic work",
    "how to repair a roof myself", "hvac installation course",
    "solar installer training and certification",
])
def test_educational_queries_avoid_false_commercial_claims(query):
    r = review_semantic_opportunity(query)
    assert r["intent_label"] == "INFORMATIONAL_HYPOTHESIS"
    assert r["recommended_review_action"] == "EDUCATIONAL_CONTENT_REVIEW_ONLY"
    assert r["buyer_willingness_to_pay_verified"] is False


@pytest.mark.parametrize("query", [
    "best solar installation companies in London",
    "compare HVAC contractor prices",
    "roof replacement cost",
    "solar panel financing ROI",
    "commercial roofing versus repair",
])
def test_commercial_research_is_not_a_confirmed_sales_lead(query):
    r = review_semantic_opportunity(query)
    assert r["intent_label"] == "COMMERCIAL_RESEARCH_HYPOTHESIS"
    assert r["recommended_review_action"] == "REVIEW_COMPARISON_OR_PRICING_CONTENT"
    assert r["conversion_verified"] is False


@pytest.mark.parametrize("query", [
    "need a heat pump installer in Bolton",
    "looking for roofing company in Dallas",
    "book a solar installation consultation",
    "get a quote for HVAC service",
])
def test_possible_service_enquiry_is_still_unverified(query):
    r = review_semantic_opportunity(query)
    assert r["intent_label"] == "SERVICE_REQUEST_TEXT_HYPOTHESIS"
    assert r["buyer_identity_verified"] is False
    assert r["outbound_authorized"] is False


@pytest.mark.parametrize(("query", "territory"), [
    ("solar installation Manchester UK", "UK"),
    ("rooftop solar in Bolton", "UK"),
    ("heat pump service Houston Texas", "USA"),
    ("commercial roofers Dallas", "USA"),
    ("solar installers in Chicago", "USA"),
])
def test_explicit_territory_hints_have_no_proof_of_customer_location(query, territory):
    r = review_semantic_opportunity(query)
    assert r["territory_review"]["geography_claim"] == territory
    assert r["territory_review"]["actual_customer_location_verified"] is False


@pytest.mark.parametrize("query", [
    "roofing jobs Chicago and Bolton",
    "solar installation UK and USA comparison",
    "HVAC market research London and Dallas",
])
def test_multinational_search_abstains_on_location(query):
    r = review_semantic_opportunity(query)
    assert r["territory_review"]["geography_claim"] is None
    assert r["territory_review"]["geography_state"] == "MULTIPLE_MARKETS_ABSTAIN"
    if not r["textual_signals"]["employment"]:
        assert r["recommended_review_action"] == "HUMAN_REVIEW_MULTIPLE_TERRITORIES"


def test_mixed_industry_request_escalates_conflict_instead_of_rerouting():
    r = review_semantic_opportunity(
        "Need solar panels and a roof replacement quote",
        ranked_results=[{"product_key": "solar"}],
    )
    assert r["sector_review"]["status"] == "ABSTAIN_MULTI_SECTOR_QUERY"
    assert r["recommended_review_action"] == "HUMAN_REVIEW_SECTOR_CONFLICT"
    assert r["sector_review"]["suggested_sector_for_review"] is None


def test_heat_pump_hvac_disagreement_has_actionable_review():
    r = review_semantic_opportunity(
        "Looking for heat pump installers in Manchester",
        ranked_results=[{"product_key": "solar"}],
    )
    assert r["sector_review"]["status"] == "SEMANTIC_SECTOR_CONFLICT_REVIEW"
    assert r["sector_review"]["suggested_sector_for_review"] == "hvac"
    assert r["recommended_review_action"] == "HUMAN_REVIEW_SECTOR_CONFLICT"


@pytest.mark.parametrize("query", [
    "best chocolate brownie recipe", "canary wharf restaurants",
    "weather tomorrow", "football scores", "SEO revenue moonshots",
    "data center processors", "photographic editing guide",
])
def test_noncommercial_or_generic_queries_abstain(query):
    r = review_semantic_opportunity(query)
    assert r["commercial_value_estimate"] is None
    assert r["buyer_willingness_to_pay_verified"] is False
    assert r["recommended_review_action"] in {
        "ABSTAIN_UNKNOWN_INTENT", "EDUCATIONAL_CONTENT_REVIEW_ONLY",
    }


def test_source_receipt_protection():
    with pytest.raises(ValueError, match="GSC intent review needs"):
        review_semantic_opportunity("solar installation", source_kind="GSC_QUERY_PAGE")
    with pytest.raises(ValueError, match="source_kind"):
        review_semantic_opportunity("solar", source_kind="CLAIMED_SALE")
    with pytest.raises(ValueError, match="evidence_refs"):
        review_semantic_opportunity("roofing", evidence_refs=[""])


def test_invalid_query_rejected():
    with pytest.raises(ValueError, match="query"):
        review_semantic_opportunity("")
    with pytest.raises(ValueError, match="query"):
        review_semantic_opportunity("x" * 501)


def test_ranking_does_not_change_after_review():
    results = [{"product_key": "solar", "retrieval_score": .75}]
    before = [dict(row) for row in results]
    review_semantic_opportunity("heat pump installers", ranked_results=results)
    assert results == before


def test_hiring_contractors_is_not_same_as_hiring_employees():
    buyer = review_semantic_opportunity('hiring roofing contractor for roof estimate')
    employee = review_semantic_opportunity('roofing company hiring technicians')
    assert buyer['recommended_review_action'] != 'EXCLUDE_AUTOMATIC_BUYER_ROUTING'
    assert employee['recommended_review_action'] == 'EXCLUDE_AUTOMATIC_BUYER_ROUTING'
    assert buyer['buyer_identity_verified'] is False


def test_near_me_does_not_prove_any_real_customer_geography():
    r = review_semantic_opportunity('need solar installer near me')
    assert r['territory_review']['geography_claim'] is None
    assert r['territory_review']['actual_customer_location_verified'] is False


def test_search_query_does_not_automatically_mean_user_is_buyer():
    r = review_semantic_opportunity('roof replacement quote in Bolton')
    assert r['textual_signals']['pricing'] is True
    assert r['buyer_willingness_to_pay_verified'] is False
    assert r['conversion_verified'] is False
    assert r['commercial_value_estimate'] is None
