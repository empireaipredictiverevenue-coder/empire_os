"""Protect distinct operating-company and sponsor account identities."""

from empire_os.enterprise_account_relationship_review import review_related_seed_accounts
from tests.test_predictive_revenue_enterprise_commercial_review import fixtures
from empire_os.predictive_revenue_enterprise_commercial_review import build_review


def test_champions_related_blackstone_seed_is_not_a_duplicate():
    result = review_related_seed_accounts("championsgroupholdings.com")
    assert result["status"] == "RELATED_SPONSOR_HISTORY_REVIEW_REQUIRED"
    assert result["related_seed_accounts"] == [{
        "account_key": "blackstone_operating_team",
        "account_name": "Blackstone Operating Team",
        "review_relation": "ANNOUNCED_SPONSOR_TRANSACTION_LINK",
        "source_urls": [
            "https://championsgroupholdings.com/2026/02/17/excited-to-share-an-important-next-chapter-for-champions-group/"
        ],
    }]
    assert result["transaction_closing_verified"] is False
    assert result["same_company_identity_verified"] is False
    assert result["duplicate_account_merge_authorized"] is False
    assert result["cross_account_contact_history_verified"] is False
    assert result["outreach_authorized"] is False


def test_public_champions_partnership_inbox_is_not_an_authorised_ai_buyer_route():
    from empire_os.enterprise_public_market_role_review import market_role_review

    role = market_role_review("championsgroupholdings.com")
    route = role["public_contact_routes_for_review_only"][0]
    assert route["published_email"].lower() == "partnerships@championsgh.com"
    assert route["source_url"] == "https://championsgroupholdings.com/contact/"
    assert route["person_bound"] is False
    assert route["software_vendor_fit_verified"] is False
    assert route["recipient_suppression_cleared"] is False
    assert route["outreach_authorized"] is False
    assert all(p["person_email_binding_verified"] is False for p in role["observed_buyer_roles_for_review_only"])


def test_unknown_related_account_never_claims_authority():
    result = review_related_seed_accounts("example.org")
    assert result["status"] == "NO_KNOWN_CURATED_SPONSOR_OVERLAP"
    assert result["related_seed_accounts"] == []
    assert result["outreach_authorized"] is False


def test_champions_packet_requires_sponsor_history_review():
    pool, locations, promotion = fixtures()
    domain = "championsgroupholdings.com"
    pool["rolling_candidates"][0].update({
        "domain": domain, "candidate_id": "champions-id",
        "account_name": "Champions Group Holdings",
        "website": f"https://{domain}/",
    })
    locations["candidates"][0].update({
        "domain": domain, "candidate_id": "champions-id",
        "account_name": "Champions Group Holdings",
        "website": f"https://{domain}/",
    })
    promotion["proposals"][0].update({"domain": domain, "candidate_id": "champions-id"})
    packet = build_review(pool, locations, promotion)["packets"][0]
    assert packet["sponsor_account_overlap_review"]["related_seed_accounts"][0]["account_key"] == "blackstone_operating_team"
    assert "SPONSOR_ACCOUNT_HISTORY_AND_TRANSACTION_REVIEW_REQUIRED" in packet["blockers"]
    assert packet["outreach_authorized"] is False
    assert packet["commercially_qualified"] is False
