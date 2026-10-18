"""Explicit evidence checks for cross-sector semantic retrieval risk."""
import pytest

from empire_os.search_intelligence.semantic_sector_review import (
    review_query_sector,
)


def ranks(top):
    return [{"product_key": top, "retrieval_score": .88}]


def test_heat_pump_misclassification_is_flagged_not_silently_reranked():
    d = review_query_sector(
        "Heat pump installers looking for customers", ranks("solar")
    )
    assert d["status"] == "SEMANTIC_SECTOR_CONFLICT_REVIEW"
    assert d["suggested_sector_for_review"] == "hvac"
    assert d["semantic_top_product"] == "solar"
    assert d["candidate_sectors"] == ["hvac"]
    assert d["automatic_product_assignment"] is False
    assert d["purchase_intent_verified"] is False
    assert "heat pump" in d["matched_evidence"][0]["matched_terms"]
    assert d["matched_evidence"][0]["source_url"].startswith("https://www.energy.gov/")


def test_same_sector_explicit_terminology_agrees_but_does_not_verify_purchase():
    d = review_query_sector(
        "How can HVAC contractors find customers?", ranks("hvac")
    )
    assert d["status"] == "EXPLICIT_TERMINOLOGY_AGREES"
    assert d["purchase_intent_verified"] is False
    assert d["search_volume_verified"] is False


def test_solar_and_roofing_collisions_abstain_instead_of_guess():
    for query in [
        "solar panels on flat roof",
        "solar installer and commercial roofing contractor",
        "solar PV heat pumps",
        "rooftop solar and roof replacement",
    ]:
        d = review_query_sector(query, ranks("solar"))
        assert d["status"] == "ABSTAIN_MULTI_SECTOR_QUERY"
        assert d["suggested_sector_for_review"] is None
        assert len(d["candidate_sectors"]) >= 2
        assert d["automatic_product_assignment"] is False


def test_generic_commercial_terms_not_false_qualified_intent():
    for query in [
        "installers looking for customers",
        "marketing agency help",
        "book a restaurant table",
        "what does a forecast mean",
        "how does AI find clients",
    ]:
        d = review_query_sector(query, ranks("roofing"))
        assert d["status"] == "UNKNOWN_NO_EXPLICIT_SECTOR_EVIDENCE"
        assert d["suggested_sector_for_review"] is None
        assert d["purchase_intent_verified"] is False


def test_substrings_and_unrelated_terms_do_not_trigger_entities():
    for query in ["blue roofscape artwork", "solarize metals",
                  "heat pumping station", "HVAC", "PV returns"]:
        d = review_query_sector(query, ranks("solar"))
        if query == "HVAC":
            assert d["candidate_sectors"] == ["hvac"]
        else:
            assert d["candidate_sectors"] == []


def test_invisible_sector_ranking_can_still_return_review_hypothesis():
    d = review_query_sector("commercial roof restoration", [])
    assert d["suggested_sector_for_review"] == "roofing"
    assert d["status"] == "SECTOR_HYPOTHESIS_NO_RANKING"
    assert d["automatic_product_assignment"] is False


def test_source_receipts_are_explanations_not_verified_metrics():
    d = review_query_sector(
        "Air-source heat pump installers", ranks("hvac")
    )
    assert d["status"] == "EXPLICIT_TERMINOLOGY_AGREES"
    for evidence in d["matched_evidence"]:
        assert evidence["source_url"].startswith("https://")
        assert evidence["source_asserts_search_volume"] is False
        assert evidence["source_asserts_buyer_intent"] is False


@pytest.mark.parametrize("query", ["", "   ", 123, "a" * 501])
def test_invalid_query_rejected(query):
    with pytest.raises(ValueError, match="query"):
        review_query_sector(query)


def test_bad_ranked_results_are_rejected():
    with pytest.raises(ValueError, match="bounded"):
        review_query_sector("roofing", [{}] * 101)
    with pytest.raises(ValueError, match="product_key"):
        review_query_sector("roofing", [{"not_product": "roofing"}])


def test_query_results_not_mutated():
    original = ranks("solar")
    copy = [x.copy() for x in original]
    review_query_sector("heat pump installers", original)
    assert original == copy
