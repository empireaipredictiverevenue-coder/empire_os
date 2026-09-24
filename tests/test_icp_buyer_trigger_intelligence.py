from empire_os.icp_buyer_trigger_intelligence import (
    assess_icp_candidate,
    build_icp_priority_targets,
    icp_learning_contract,
)


def test_icp_targets_prioritize_profiles_without_claiming_budget():
    rows = build_icp_priority_targets(
        corridor_targets=[
            {
                "territory": "austin_tx",
                "niche_family": "roofing",
            }
        ],
        product_targets=[
            {"product_code": "tag_intelligence_monitor"},
            {"product_code": "managed_service"},
        ],
    )

    assert rows
    assert rows[0]["rank"] == 1
    assert all(row["budget_verified"] is False for row in rows)
    assert all(
        row["binding_intent_verified"] is False for row in rows
    )
    assert any(
        row["icp_profile_key"] == "high_ticket_home_service"
        for row in rows
    )


def test_candidate_fit_uses_observed_trigger_and_role_evidence():
    result = assess_icp_candidate(
        {
            "business_name": "Peak Roofing",
            "description": (
                "Roofing contractor expanding into a new service area. "
                "Free estimates available."
            ),
            "notes": "Owner-led roofing company.",
            "buyer_type": "qualified_end_buyer",
            "target_buyer_pools": ["end_service_buyers"],
            "target_product_codes": ["managed_service"],
            "first_party_people": [
                {"name": "Jane Doe", "title": "Owner"}
            ],
            "direct_signal_hits": [],
            "reseller_signal_hits": [],
        },
        target_profile_keys=["high_ticket_home_service"],
    )

    assert result["best_profile_key"] == "high_ticket_home_service"
    assert result["model_fit_score"] > 0
    assert result["score_classification"] == "MODEL_HEURISTIC"
    assert result["why_now_state"] == "OBSERVED_TRIGGER"
    assert result["decision_maker_state"] == "OBSERVED_ROLE_MATCH"
    assert result["budget_verified"] is False
    assert result["binding_intent_verified"] is False
    assert result["qualification_created"] is False
    assert result["outreach_authorized"] is False
    assert result["actual_revenue"] is False


def test_no_trigger_or_capacity_evidence_stays_unknown():
    result = assess_icp_candidate(
        {
            "business_name": "Acme",
            "description": "Professional services.",
            "target_buyer_pools": [],
            "target_product_codes": [],
            "first_party_people": [],
        },
        target_profile_keys=["enterprise_growth_data_team"],
    )

    assert result["why_now_state"] == "UNKNOWN"
    assert result["decision_maker_state"] == "UNKNOWN"
    assert result["economic_capacity_state"] == "UNKNOWN"
    assert result["budget_verified"] is False


def test_learning_contract_preserves_revenue_truth():
    contract = icp_learning_contract()

    assert contract["synthetic_training_outcomes_allowed"] is False
    assert contract["forecast_is_revenue"] is False
    assert contract["reply_is_revenue"] is False
    assert contract["meeting_is_revenue"] is False
    assert contract["payment_request_is_revenue"] is False
    assert contract["payment_verified_is_recognized_revenue"] is False
    assert contract["execution_authority"] == "none"


def test_predictive_revenue_enterprise_profiles_are_continuously_targeted():
    rows = build_icp_priority_targets()

    by_key = {
        row["icp_profile_key"]: row
        for row in rows
    }
    expected = {
        "predictive_revenue_home_services_platform",
        "predictive_revenue_franchise_network",
        "predictive_revenue_portfolio_value_creation",
    }

    assert expected <= set(by_key)
    for key in expected:
        row = by_key[key]
        assert row["priority_score"] >= 99
        assert row["research_queries"]
        assert row["budget_verified"] is False
        assert row["binding_intent_verified"] is False
        assert any(
            code.startswith("predictive_revenue_")
            for code in row["product_codes"]
        )


def test_legal_and_insurance_profiles_are_continuously_targeted():
    rows = build_icp_priority_targets()
    by_key = {
        row["icp_profile_key"]: row
        for row in rows
    }
    expected = {
        "legal_mass_tort_plaintiff_firm",
        "legal_plaintiff_growth_firm",
        "insurance_distribution_growth",
    }

    assert expected <= set(by_key)
    assert by_key["legal_mass_tort_plaintiff_firm"][
        "priority_score"
    ] >= 100
    assert by_key["legal_plaintiff_growth_firm"][
        "priority_score"
    ] >= 98
    assert by_key["insurance_distribution_growth"][
        "priority_score"
    ] >= 98

    for key in expected:
        row = by_key[key]
        assert row["research_queries"]
        assert row["budget_verified"] is False
        assert row["binding_intent_verified"] is False
