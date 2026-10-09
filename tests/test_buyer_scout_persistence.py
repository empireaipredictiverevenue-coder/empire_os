from empire_os.buyer_scout_persistence import (
    persist_new_external_candidates,
)


def test_persistence_requires_current_first_party_purchase_receipt():
    from empire_os.buyer_claim_provenance import classify_buyer_source_pages
    calls = []
    def rpc(method, path, payload):
        calls.append(payload)
        return {"decision": "candidate_recorded", "candidate_id": "id-1",
                "domain": "buyer.example", "outreach_authorized": False}
    buyer = {
        "domain": "buyer.example", "website": "https://buyer.example",
        "business_name": "Buyer Company", "buyer_type": "direct_lead_buyer",
        "direct_buyer_score": 90, "explicit_direct_buyer_evidence": True,
        "target_buyer_pools": ["direct_demand_buyers"],
    }
    rec = {"results": [{"domain": "buyer.example",
                        "reconciliation_state": "NEW_EXTERNAL_BUYER_CANDIDATE"}]}
    claim = classify_buyer_source_pages(
        [{"url": "https://buyer.example/partners",
          "visible_text": "We buy calls from publishers."}],
        company_website="https://buyer.example",
    )
    buyer["buyer_claim_provenance"] = claim
    result = persist_new_external_candidates(
        {"candidates": [buyer]}, rec, rpc_call=rpc,
    )
    assert result["persisted_candidate_count"] == 1
    assert calls[0]["p_explicit_direct_buyer_evidence"] is True
    assert calls[0]["p_site_evidence"]["buyer_claim_provenance"] == claim
    assert calls[0]["p_site_evidence"]["buyer_relationship"] == "direct_inventory_buyer"
    assert calls[0]["p_provenance"]["outreach_authorized"] is False


def test_only_new_external_candidates_are_persisted():
    calls = []

    def rpc(method, path, payload):
        calls.append((method, path, payload))
        return {
            "decision": "candidate_recorded",
            "candidate_id": "candidate-1",
            "domain": "new.example",
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
                "canonical_seed_identity_corroborated": True,
                "permit_territory_state": "NYC_FIRST_PARTY_EVIDENCE",
                "permit_territory_evidence": ["nyc"],
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
                "continuous_commercial_lane": (
                    "predictive_revenue_enterprise"
                ),
                "continuous_lane_candidate": True,
                "continuous_lane_fit_score": 82,
                "intent_signal_id": "sig-roof-1",
                "intent_signal_source": "reddit_intent",
                "intent_score": 86,
                "intent_band": "high",
                "intent_observed_at": "2026-10-04T07:45:00+00:00",
                "intent_summary": (
                    "Need more qualified appointments. Google Ads has not "
                    "been consistently profitable."
                ),
                "intent_pain_points": [
                    "lead_generation",
                    "revenue_growth",
                ],
                "intent_evidence_url": (
                    "https://reddit.com/r/Roofing/comments/example"
                ),
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
    assert payload["p_direct_buyer_score"] == 0
    assert payload["p_buyer_type"] == "unknown"
    assert payload["p_site_evidence"]["buyer_relationship"] == "unknown"
    # A bare direct-buyer boolean is not sufficient without an observed
    # first-party claim receipt. The holding row remains research only.
    assert payload["p_explicit_direct_buyer_evidence"] is False
    assert payload["p_site_evidence"]["business_name_source"] == (
        "first_party_business_name"
    )
    assert payload["p_site_evidence"]["site_business_names"] == [
        "New Buyer"
    ]
    assert payload["p_site_evidence"][
        "canonical_seed_identity_corroborated"
    ] is True
    assert payload["p_site_evidence"]["permit_territory_state"] == (
        "NYC_FIRST_PARTY_EVIDENCE"
    )
    assert payload["p_site_evidence"]["permit_territory_evidence"] == [
        "nyc"
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
    assert payload["p_site_evidence"][
        "continuous_commercial_lane"
    ] == "predictive_revenue_enterprise"
    assert payload["p_site_evidence"][
        "continuous_lane_candidate"
    ] is True
    assert payload["p_site_evidence"][
        "continuous_lane_fit_score"
    ] == 82
    assert payload["p_provenance"]["target_icp_profile_keys"] == [
        "direct_demand_buyer"
    ]
    assert payload["p_provenance"]["icp_score_classification"] == (
        "MODEL_HEURISTIC"
    )
    assert payload["p_provenance"]["canonical_identity_verified"] is False
    assert payload["p_provenance"]["outreach_authorized"] is False
    assert payload["p_site_evidence"]["intent_signal_id"] == "sig-roof-1"
    assert payload["p_site_evidence"]["intent_signal_source"] == "reddit_intent"
    assert payload["p_site_evidence"]["intent_score"] == 86
    assert payload["p_site_evidence"]["intent_band"] == "high"
    assert payload["p_site_evidence"]["intent_observed_at"] == (
        "2026-10-04T07:45:00+00:00"
    )
    assert "qualified appointments" in payload["p_site_evidence"][
        "intent_summary"
    ]
    assert payload["p_site_evidence"]["intent_pain_points"] == [
        "lead_generation",
        "revenue_growth",
    ]
    assert payload["p_site_evidence"]["intent_evidence_url"] == (
        "https://reddit.com/r/Roofing/comments/example"
    )
    assert payload["p_provenance"]["intent_signal_id"] == "sig-roof-1"
    assert payload["p_provenance"]["intent_observed_at"] == (
        "2026-10-04T07:45:00+00:00"
    )


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


def test_missing_canonical_persistence_evidence_fails_closed():
    scout = {
        "candidates": [{
            "domain": "missing-proof.example",
            "website": "https://missing-proof.example",
            "business_name": "Missing Proof Buyer",
            "buyer_type": "direct_lead_buyer",
            "direct_buyer_score": 80,
            "explicit_direct_buyer_evidence": True,
            "target_buyer_pools": ["direct_demand_buyers"],
            "query_evidence": [{"query": "buy leads"}],
        }]
    }
    reconciliation = {
        "results": [{
            "domain": "missing-proof.example",
            "reconciliation_state": "NEW_EXTERNAL_BUYER_CANDIDATE",
        }]
    }
    try:
        persist_new_external_candidates(
            scout,
            reconciliation,
            rpc_call=lambda *_args: None,
        )
    except RuntimeError as exc:
        assert "persistence evidence missing" in str(exc)
    else:
        raise AssertionError("missing canonical persistence evidence must fail")


def test_verified_identity_provenance_is_preserved_in_holding_rpc():
    calls = []

    def rpc(method, path, payload):
        calls.append(
            (
                method,
                path,
                payload,
            )
        )

        return {
            "decision":
                "candidate_recorded",
            "candidate_id":
                "verified-identity-candidate",
            "domain":
                "verified.example",
            "outreach_authorized":
                False,
            "actual_revenue":
                False,
        }

    scout = {
        "candidates": [{
            "domain":
                "verified.example",
            "website":
                "https://verified.example",
            "business_name":
                "Verified Example Ltd",
            "canonical_identity_verified":
                True,
            "candidate_state":
                "RESEARCH_EVIDENCE_ONLY",
            "query_evidence": [{
                "source":
                    "verified_identity_intent",
            }],
            "query_evidence_count":
                1,
            "first_party_people": [{
                "name":
                    "Jane Example",
                "title":
                    "Owner",
                "source_url":
                    "https://verified.example/about",
                "confidence":
                    0.91,
                "first_party":
                    True,
            }],
            "people_count":
                1,
            "intent_signal_id":
                "sig-verified-1",
            "intent_signal_source":
                "reddit_intent",
            "outreach_authorized":
                False,
        }]
    }

    reconciliation = {
        "results": [{
            "domain":
                "verified.example",
            "reconciliation_state":
                "NEW_EXTERNAL_BUYER_CANDIDATE",
        }]
    }

    result = (
        persist_new_external_candidates(
            scout,
            reconciliation,
            rpc_call=rpc,
        )
    )

    assert (
        result[
            "persisted_candidate_count"
        ]
        == 1
    )

    assert (
        result[
            "canonical_promotion_performed"
        ]
        is False
    )

    assert (
        result[
            "outbound_sent"
        ]
        is False
    )

    assert len(calls) == 1

    method, path, payload = (
        calls[0]
    )

    assert method == "POST"

    assert path.endswith(
        "propose_buyer_scout_candidate"
    )

    assert (
        payload[
            "p_provenance"
        ][
            "canonical_identity_verified"
        ]
        is True
    )

    assert (
        payload[
            "p_provenance"
        ][
            "outreach_authorized"
        ]
        is False
    )
