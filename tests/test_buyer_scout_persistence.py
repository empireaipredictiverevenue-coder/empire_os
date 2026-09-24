from empire_os.buyer_scout_persistence import (
    persist_new_external_candidates,
)


def test_only_new_external_candidates_are_persisted():
    calls = []

    def rpc(method, path, payload):
        calls.append((method, path, payload))
        return {
            "decision": "candidate_recorded",
            "candidate_id": "candidate-1",
            "outreach_authorized": False,
            "actual_revenue": False,
        }

    scout = {
        "candidates": [
            {
                "domain": "new.example",
                "website": "https://new.example",
                "business_name": "New Buyer",
                "business_name_source": "first_party_business_name",
                "site_business_names": ["New Buyer"],
                "description": "We buy leads.",
                "buyer_type": "direct_lead_buyer",
                "direct_buyer_score": 90,
                "explicit_direct_buyer_evidence": True,
                "target_buyer_pools": ["direct_demand_buyers"],
                "target_product_codes": ["managed_service"],
                "target_corridor_keys": [],
                "target_icp_profile_keys": [
                    "direct_demand_buyer"
                ],
                "icp_intelligence": {
                    "best_profile_key": "direct_demand_buyer",
                    "score_classification": "MODEL_HEURISTIC",
                    "model_fit_score": 88,
                    "budget_verified": False,
                },
                "observed_buying_triggers": ["buy leads"],
                "why_now_state": "OBSERVED_TRIGGER",
                "decision_maker_state": "OBSERVED_ROLE_MATCH",
                "economic_capacity_state": "UNKNOWN",
                "query_evidence": [{"query": "buy leads"}],
                "query_evidence_count": 1,
                "site_evidence_score": 0.9,
                "first_party_email_count": 1,
                "first_party_phone_count": 1,
                "people_count": 1,
                "first_party_emails": ["sales@new.example"],
                "first_party_phones": ["+15125550123"],
                "first_party_people": [
                    {"name": "Jane Smith", "title": "CEO"}
                ],
                "direct_signal_hits": ["buy leads"],
                "reseller_signal_hits": [],
                "predictive_revenue_enterprise_candidate": True,
                "predictive_revenue_enterprise_profile": (
                    "predictive_revenue_home_services_platform"
                ),
                "predictive_revenue_enterprise_fit_score": 82,
                "candidate_state": "RESEARCH_EVIDENCE_ONLY",
            },
            {
                "domain": "known.example",
                "website": "https://known.example",
                "business_name": "Known Buyer",
            },
        ]
    }
    reconciliation = {
        "results": [
            {
                "domain": "new.example",
                "reconciliation_state": "NEW_EXTERNAL_BUYER_CANDIDATE",
            },
            {
                "domain": "known.example",
                "reconciliation_state": "EXISTING_CANONICAL_BUYER",
            },
        ]
    }

    result = persist_new_external_candidates(
        scout,
        reconciliation,
        rpc_call=rpc,
    )

    assert result["persisted_candidate_count"] == 1
    assert result["skipped_candidate_count"] == 1
    assert result["holding_area_only"] is True
    assert result["canonical_promotion_performed"] is False
    assert result["outbound_sent"] is False

    method, path, payload = calls[0]
    assert method == "POST"
    assert path.endswith("propose_buyer_scout_candidate")
    assert payload["p_domain"] == "new.example"
    assert payload["p_direct_buyer_score"] == 90
    assert payload["p_explicit_direct_buyer_evidence"] is True
    assert payload["p_site_evidence"]["business_name_source"] == (
        "first_party_business_name"
    )
    assert payload["p_site_evidence"]["site_business_names"] == [
        "New Buyer"
    ]
    assert payload["p_site_evidence"]["first_party_emails"] == [
        "sales@new.example"
    ]
    assert payload["p_site_evidence"]["first_party_people"][0]["name"] == (
        "Jane Smith"
    )
    assert payload["p_site_evidence"]["icp_intelligence"][
        "best_profile_key"
    ] == "direct_demand_buyer"
    assert payload["p_site_evidence"]["budget_verified"] is False
    assert payload["p_site_evidence"][
        "predictive_revenue_enterprise_candidate"
    ] is True
    assert payload["p_site_evidence"][
        "predictive_revenue_enterprise_profile"
    ] == "predictive_revenue_home_services_platform"
    assert payload["p_site_evidence"][
        "predictive_revenue_enterprise_fit_score"
    ] == 82
    assert payload["p_provenance"]["target_icp_profile_keys"] == [
        "direct_demand_buyer"
    ]
    assert payload["p_provenance"]["icp_score_classification"] == (
        "MODEL_HEURISTIC"
    )
    assert payload["p_provenance"]["canonical_identity_verified"] is False
    assert payload["p_provenance"]["outreach_authorized"] is False


def test_missing_scout_source_fails_closed_without_rpc():
    calls = []

    result = persist_new_external_candidates(
        {"candidates": []},
        {
            "results": [
                {
                    "domain": "missing.example",
                    "reconciliation_state": "NEW_EXTERNAL_BUYER_CANDIDATE",
                }
            ]
        },
        rpc_call=lambda *args: calls.append(args),
    )

    assert result["persisted_candidate_count"] == 0
    assert result["skipped_candidate_count"] == 1
    assert calls == []
