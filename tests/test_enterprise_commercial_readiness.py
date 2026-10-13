"""Enterprise research is never implicitly promoted to a commercial buyer."""
from empire_os.predictive_revenue_enterprise_pool import (
    assess_commercial_readiness,
    build_rolling_enterprise_pool,
)


def proposal(*, products=None, person_url="https://example.com/about"):
    return {
        "candidate_id": "sample",
        "domain": "example.com",
        "buyer_type": "enterprise_buyer",
        "target_buyer_pools": ["enterprise_and_data_buyers"],
        "target_product_codes": products if products is not None else ["predictive_revenue_diagnostic"],
        "first_party_emails_preserved_for_identity_resolution": ["hello@example.com"],
        "target_people_for_enrichment": [
            {"name": "Alex Example", "evidence_url": person_url}
        ],
        "commercial_research_profile": {
            "research_routes": [{"classification": "INFERRED_RESEARCH_FIT"}],
            "customer_state": "UNKNOWN", "demand_state": "UNKNOWN",
        },
        "proposed_prospect_payload": {
            "business_name": "Example Industries", "website": "https://example.com/"
        },
    }


def test_first_party_person_and_product_are_fit_review_not_a_buyer():
    result = assess_commercial_readiness(proposal())
    assert result["state"] == "FIT_REVIEW"
    assert result["first_party_person_observed"] is True
    assert result["commercially_qualified"] is False
    assert result["verified_buying_intent"] is False
    assert result["outreach_authorized"] is False
    assert "BUYING_INTENT_NOT_VERIFIED" in result["missing_evidence"]


def test_external_person_page_does_not_corroborate_company():
    result = assess_commercial_readiness(
        proposal(person_url="https://unrelated.example.org/people")
    )
    assert result["state"] == "RESEARCH_ONLY"
    assert "FIRST_PARTY_PERSON_EVIDENCE_REQUIRED" in result["missing_evidence"]


def test_missing_product_keeps_research_candidate_without_commercial_promotion():
    result = assess_commercial_readiness(proposal(products=[]))
    assert result["state"] == "RESEARCH_ONLY"
    assert "PRODUCT_MAPPING_REQUIRED" in result["missing_evidence"]
    pool = build_rolling_enterprise_pool({"proposals": [proposal(products=[])]})
    assert pool["rolling_addition_count"] == 1
    assert pool["commercially_qualified_count"] == 0
    assert pool["rolling_candidates"][0]["commercial_readiness"]["state"] == "RESEARCH_ONLY"


def test_inferred_fit_never_grants_send_or_payment_authority():
    pool = build_rolling_enterprise_pool({"proposals": [proposal()]})
    assert pool["fit_review_count"] == 1
    assert pool["commercially_qualified_count"] == 0
    assert pool["outreach_authorized"] is False
    assert pool["payment_action"] is False
    assert pool["rolling_candidates"][0]["commercial_readiness"]["state"] == "FIT_REVIEW"


def test_malformed_fields_and_non_http_person_urls_fail_closed():
    row = proposal(person_url="ftp://example.com/people")
    assert assess_commercial_readiness(row)["state"] == "RESEARCH_ONLY"
    row["target_product_codes"] = "predictive_revenue_diagnostic"
    row["target_people_for_enrichment"] = "Alex Example"
    result = assess_commercial_readiness(row)
    assert result["state"] == "RESEARCH_ONLY"
    assert result["product_mapping_present"] is False
    assert result["first_party_person_observed"] is False
