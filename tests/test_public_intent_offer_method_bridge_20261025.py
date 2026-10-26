"""No fictitious keyword metrics, no second Search Intelligence subsystem."""
import pytest

from empire_os.public_intent_offer_method_bridge import (
    IntentOfferSpec, MAX_CANDIDATES, prepare_public_intent_offer_review,
)


def sample(**overrides):
    params = {
        "market_key": "us-commercial-roofing",
        "seed_keyword": "commercial roof repair",
        "icp_key": "commercial-roofing-operator",
        "buyer_problem": "Owners need a repair/replace decision before booking an inspection",
        "product_key": "search_opportunity_map",
        "glossary_terms": ("TPO roofing", "PVC roofing", "roof coating"),
        "territory_key": "united-states",
    }
    return IntentOfferSpec(**(params | overrides))


def test_keywords_flow_through_original_keyword_universe_and_asset_backlog():
    report = prepare_public_intent_offer_review(sample())
    assert report["owner"] == "empire_os.keyword_universe"
    assert report["existing_search_product"] == "search_opportunity_map"
    assert report["keyword_candidate_count"] > 14
    assert report["keyword_candidate_count"] <= MAX_CANDIDATES
    assert len(report["existing_asset_backlog"]["assets"]) == report["keyword_candidate_count"]
    assert report["universe"]["rejected"] == []
    assert report["universe"]["schema_version"] == "keyword_universe.v1"
    assert report["existing_asset_backlog"]["schema_version"] == "keyword_asset_backlog.v1"
    assert "commercial roof repair cost" in {r["keyword"] for r in report["keyword_candidates"]}
    assert "tpo roofing vs commercial roof repair" in {
        r["keyword"] for r in report["keyword_candidates"]
    }
    assert any(
        row["record"]["asset_type"] == "calculator" or
        row["record"]["asset_type"] == "guide"
        for row in report["universe"]["keywords"]
    )


def test_every_generated_query_is_unscored_until_real_data_arrives():
    report = prepare_public_intent_offer_review(sample())
    assert all(not row["opportunity"]["available"] and row["opportunity"]["score"] is None
               for row in report["universe"]["keywords"])
    assert all(not asset["opportunity_available"] and asset["opportunity_score"] is None
               and asset["draft_only"]
               for asset in report["existing_asset_backlog"]["assets"])
    assert all(x["search_demand_status"] == "NOT_OBSERVED"
               for x in report["keyword_candidates"])
    for key in ("search_volume_reported", "cpc_reported", "organic_keyword_difficulty_reported",
                "rankings_observed", "buyer_conversion_verified", "affiliate_payout_verified",
                "actual_revenue_verified", "outbound_authorized", "content_publish_authorized",
                "indexation_authorized", "paid_ad_authorized", "database_writes"):
        assert report[key] is False


def test_plain_seed_without_glossary_still_generates_useful_backlog():
    report = prepare_public_intent_offer_review(
        sample(seed_keyword="heat pump quote", glossary_terms=()))
    assert report["keyword_candidate_count"] >= 10
    assert len({row["keyword"] for row in report["keyword_candidates"]}) ==            report["keyword_candidate_count"]


def test_duplicate_glossary_or_unapproved_product_fails_closed():
    with pytest.raises(ValueError, match="duplicate_glossary"):
        prepare_public_intent_offer_review(sample(glossary_terms=("TPO", "tpo")))
    with pytest.raises(ValueError, match="not_an_existing"):
        prepare_public_intent_offer_review(sample(product_key="new_shadow_seo_product"))


@pytest.mark.parametrize("bad", ["", "x", "x" * 120, "hack<script>"])
def test_invalid_seed_rejected_without_publication(bad):
    with pytest.raises(ValueError, match="seed_keyword_invalid"):
        prepare_public_intent_offer_review(sample(seed_keyword=bad))


def test_public_method_does_not_require_provider_credentials_or_network():
    report = prepare_public_intent_offer_review(sample())
    assert report["mode"] == "OBSERVE"
    assert report["execution_authority"] == "none"
    assert "observed_serp_snapshot_and_competitor_coverage" in report["required_next_evidence"]
    assert report["keyword_candidate_count"] == 27


def test_long_user_question_is_not_multiplied_into_low_quality_keyword_spam():
    report = prepare_public_intent_offer_review(sample(
        seed_keyword="how do i know which accounts in my tam are actually ready to buy right now",
        glossary_terms=(),
    ))
    assert report["keyword_candidate_count"] == 1
    assert report["keyword_candidates"][0]["keyword"] == (
        "how do i know which accounts in my tam are actually ready to buy right now"
    )
    assert report["universe"]["keywords"][0]["record"]["intent_class"] == "problem"
    assert report["universe"]["keywords"][0]["record"]["funnel_stage"] == "consideration"
    assert report["actual_revenue_verified"] is False
