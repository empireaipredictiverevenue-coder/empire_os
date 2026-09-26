from empire_os.buyer_scout_promotion_plan import (
    build_promotion_plan,
)


def candidate(**overrides):
    row = {
        "id": "candidate-1",
        "domain": "roof.example",
        "business_name": "Roof Co",
        "website": "https://roof.example",
        "buyer_type": "qualified_end_buyer",
        "review_state": "review_ready",
        "reconciliation_state": "REVIEW_READY",
        "target_buyer_pools": ["local_and_smb_buyers"],
        "target_product_codes": ["local_search_grid"],
        "target_corridor_keys": [
            "corridor:v1:roofing:austin_tx:qualified_lead:lead"
        ],
        "site_evidence": {
            "first_party_phones": ["+15125550123"],
            "first_party_emails": ["sales@roof.example"],
            "first_party_people": [
                {"name": "Jane Smith", "title": "Owner"}
            ],
        },
    }
    row.update(overrides)
    return row


def test_review_ready_candidate_gets_raw_prospect_proposal():
    result = build_promotion_plan([candidate()])

    assert result["proposal_count"] == 1
    row = result["proposals"][0]
    payload = row["proposed_prospect_payload"]

    assert payload["business_name"] == "Roof Co"
    assert payload["niche"] == "roofing"
    assert payload["metro"] == "austin tx"
    assert payload["buy_signal_score"] is None
    assert payload["contact_name"] == "Jane Smith"
    assert payload["contact_title"] == "Owner"
    assert payload["contact_source"] == "first_party_site"
    assert row["first_party_emails_preserved_for_identity_resolution"] == [
        "sales@roof.example"
    ]
    assert row["outreach_authorized"] is False
    assert result["database_write_performed"] is False
    assert result["canonical_promotion_performed"] is False


def test_contact_source_preserves_observed_identity_provenance():
    row = candidate(
        site_evidence={
            "first_party_phones": ["+15125550123"],
            "first_party_emails": [],
            "first_party_people": [
                {
                    "name": "Alex Founder",
                    "title": "Founder",
                    "identity_source": "corroborated_public_profile",
                }
            ],
        },
    )

    result = build_promotion_plan([row])
    payload = result["proposals"][0]["proposed_prospect_payload"]

    assert payload["contact_name"] == "Alex Founder"
    assert payload["contact_source"] == "corroborated_public_profile"


def test_explicit_person_source_takes_precedence():
    row = candidate(
        site_evidence={
            "first_party_phones": ["+15125550123"],
            "first_party_emails": [],
            "first_party_people": [
                {
                    "name": "Alex Founder",
                    "title": "Founder",
                    "source": "public_company_post_and_first_party_site",
                    "identity_source": "corroborated_public_profile",
                }
            ],
        },
    )

    result = build_promotion_plan([row])
    payload = result["proposals"][0]["proposed_prospect_payload"]

    assert payload["contact_source"] == (
        "public_company_post_and_first_party_site"
    )


def test_ambiguous_market_and_contact_fail_closed_to_unknown():
    row = candidate(
        target_corridor_keys=[
            "corridor:v1:roofing:austin_tx:qualified_lead:lead",
            "corridor:v1:roofing:dallas_tx:qualified_lead:lead",
        ],
        site_evidence={
            "first_party_phones": ["1", "2"],
            "first_party_emails": ["a@x.example"],
            "first_party_people": [
                {"name": "A", "title": "Owner"},
                {"name": "B", "title": "Sales"},
            ],
        },
    )

    result = build_promotion_plan([row])
    payload = result["proposals"][0]["proposed_prospect_payload"]

    assert payload["niche"] is None
    assert payload["metro"] is None
    assert payload["phone"] is None
    assert payload["contact_name"] is None
    assert payload["contact_title"] is None
    assert payload["buy_signal_score"] is None


def test_non_review_ready_candidate_is_not_proposed():
    result = build_promotion_plan([
        candidate(review_state="discovered")
    ])

    assert result["proposal_count"] == 0
    assert result["blocked_reason_counts"] == {
        "not_review_ready": 1
    }


def test_stale_review_ready_generic_name_is_rejected_at_promotion():
    row = candidate(
        business_name="Step 1",
        review_state="review_ready",
        reconciliation_state="REVIEW_READY",
    )

    result = build_promotion_plan([row])

    assert result["proposal_count"] == 0
    assert result["blocked_reason_counts"] == {
        "business_name_not_verified": 1
    }
