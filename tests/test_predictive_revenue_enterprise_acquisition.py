from empire_os.candidate_quality import assess_candidate
from empire_os.predictive_revenue_enterprise_acquisition import (
    TARGET_ACQUISITION,
    build_enterprise_acquisition_review,
    build_enterprise_lead_candidates,
)


def test_enterprise_candidates_are_real_identity_sources():
    candidates = build_enterprise_lead_candidates()
    assert len(candidates) == 9

    for candidate in candidates:
        quality = assess_candidate(candidate)
        assert quality.accepted is True
        assert quality.entity_kind == "business"
        assert quality.source_role == "identity_or_direct"
        assert candidate.source == "public_enterprise_target"
        assert candidate.lead_score == 50
        assert candidate.raw["business_website"].startswith("https://")
        assert candidate.raw["outreach_authorized"] is False
        assert candidate.raw["actual_revenue"] is False


def test_enterprise_company_routes_never_claim_person_binding():
    assert len(TARGET_ACQUISITION) == 9
    for account in TARGET_ACQUISITION.values():
        routes = account["company_contact_routes"]
        assert routes
        for route in routes:
            assert route["verified"] is True
            assert route["person_bound"] is False
            assert route["evidence_url"].startswith("https://")


def test_enterprise_acquisition_review_preserves_truth_boundaries():
    review = build_enterprise_acquisition_review()
    assert review["candidate_count"] == 9
    assert review["public_fit_is_buyer_intent"] is False
    assert review["person_name_is_contact_verification"] is False
    assert review["company_route_is_person_bound"] is False
    assert review["outreach_authorized"] is False
    assert review["payment_action"] is False
    assert review["actual_revenue"] is False
    assert review["execution_authority"] == "none"
