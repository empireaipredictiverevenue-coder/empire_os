from empire_os.buyer_scout_reconciliation import (
    reconcile_scout_candidates,
)


def scout(domain="buyer.example"):
    return {
        "candidates": [
            {
                "domain": domain,
                "website": f"https://{domain}",
                "business_name": "Buyer Co",
                "buyer_type": "direct_lead_buyer",
                "direct_buyer_score": 80,
                "target_buyer_pools": ["direct_demand_buyers"],
                "target_product_codes": ["managed_service"],
                "target_corridor_keys": [],
            }
        ]
    }


def test_existing_buyer_wins_before_prospect_match():
    result = reconcile_scout_candidates(
        scout(),
        prospects=[
            {
                "id": "prospect-1",
                "business_name": "Buyer Co Prospect",
                "website": "https://buyer.example",
                "status": "qualified",
            }
        ],
        buyers=[
            {
                "id": "buyer-1",
                "buyer_name": "Buyer Co",
                "email": "sales@buyer.example",
                "status": "active",
                "is_active": True,
            }
        ],
    )

    row = result["results"][0]
    assert row["reconciliation_state"] == "EXISTING_CANONICAL_BUYER"
    assert row["canonical_matches"][0]["buyer_id"] == "buyer-1"
    assert result["existing_buyer_count"] == 1
    assert result["database_write_performed"] is False


def test_existing_prospect_is_reused_instead_of_new_ingest():
    result = reconcile_scout_candidates(
        scout(),
        prospects=[
            {
                "id": "prospect-1",
                "business_name": "Buyer Co",
                "website": "buyer.example",
                "status": "new",
                "niche": "marketing",
                "metro": "Austin, TX",
            }
        ],
        buyers=[],
    )

    row = result["results"][0]
    assert row["reconciliation_state"] == "EXISTING_CANONICAL_PROSPECT"
    assert row["canonical_matches"][0]["prospect_id"] == "prospect-1"
    assert result["existing_prospect_count"] == 1


def test_unknown_domain_stays_external_candidate_without_auto_ingest():
    result = reconcile_scout_candidates(
        scout("newbuyer.example"),
        prospects=[],
        buyers=[],
    )

    row = result["results"][0]
    assert row["reconciliation_state"] == "NEW_EXTERNAL_BUYER_CANDIDATE"
    assert row["automatic_ingest_authorized"] is False
    assert row["outreach_authorized"] is False
    assert result["new_external_candidate_count"] == 1
    assert result["execution_authority"] == "none"


def test_free_email_domain_does_not_create_false_buyer_domain_match():
    result = reconcile_scout_candidates(
        scout("gmail.com"),
        prospects=[],
        buyers=[
            {
                "id": "buyer-1",
                "buyer_name": "Generic Mail Buyer",
                "email": "someone@gmail.com",
                "status": "active",
                "is_active": True,
            }
        ],
    )

    row = result["results"][0]
    assert row["reconciliation_state"] == "NEW_EXTERNAL_BUYER_CANDIDATE"
    assert result["existing_buyer_count"] == 0
    assert result["new_external_candidate_count"] == 1
