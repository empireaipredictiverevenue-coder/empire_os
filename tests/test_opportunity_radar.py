from empire_os.opportunity_radar import build_opportunity_radar


def test_radar_aggregates_observed_sources_without_inventing_truth():
    payload = build_opportunity_radar(
        generated_at="2026-09-22T21:00:00+00:00",
        market_gps={
            "generated_at": "2026-09-22T20:00:00+00:00",
            "research_queue": [{
                "niche": "roofing",
                "metro": "denver, co",
                "research_priority_score": 72,
                "evidence_refs": ["canonical:prospect_acquisitions"],
                "recommended_next_action": "deepen_market_research",
            }],
            "markets": [{
                "niche": "roofing",
                "metro": "denver, co",
                "commercial_demand_state": "not_observed",
                "product_candidate": None,
            }],
        },
        community_intent={
            "observed_at": "2026-09-22T20:15:00+00:00",
            "pain_solution_briefs": [{
                "pain_point": "search_visibility",
                "observed_mentions": 3,
                "average_intent_score": 65,
                "high_intent_mentions": 2,
                "evidence_urls": ["https://example.com/1"],
                "offer_key": "search_growth_command",
                "products": ["geo_ai_visibility"],
                "next_actions": ["collect_serp_evidence"],
                "opportunity_event": "opportunity_candidate_created",
                "evidence_strength": "moderate",
            }],
        },
        competitor_market={
            "generated_at": "2026-09-22T20:30:00+00:00",
            "market_key": "roofing-denver",
            "niche": "roofing",
            "metro": "denver, co",
            "research_gap_company_count": 1,
            "underserved_audience_candidates": [{
                "entity_id": "company:1",
            }],
        },
    )
    assert payload["candidate_count"] == 3
    assert payload["factory_ready_count"] == 0
    assert payload["automatic_research_allowed"] is True
    assert payload["automatic_external_execution_allowed"] is False
    assert payload["execution_authority"] == "none"
    assert all(
        row["revenue_inferred"] is False
        for row in payload["candidates"]
    )


def test_missing_sources_stay_unavailable():
    payload = build_opportunity_radar(
        market_gps=None,
        community_intent=None,
        competitor_market=None,
    )
    assert payload["candidate_count"] == 0
    assert payload["source_status"]["market_gps"]["available"] is False
    assert payload["source_status"]["community_intent"]["available"] is False
    assert payload["source_status"]["competitor_market"]["available"] is False


def test_radar_attaches_decay_evidence_without_reordering():
    payload = build_opportunity_radar(
        generated_at="2026-10-01T12:00:00+00:00",
        market_gps={
            "generated_at": "2026-10-01T11:00:00+00:00",
            "research_queue": [{
                "niche": "roofing",
                "metro": "denver, co",
                "research_priority_score": 72,
                "evidence_refs": ["market:roofing:denver"],
                "recommended_next_action": "deepen_market_research",
            }],
            "markets": [{
                "niche": "roofing",
                "metro": "denver, co",
                "commercial_demand_state": "observed",
                "product_candidate": "permit_intelligence",
            }],
        },
        community_intent=None,
        competitor_market=None,
        decay_evidence_by_opportunity={
            "market:roofing:denver, co": {
                "revalidated_at": "2026-10-01T11:30:00+00:00",
                "freshness_window_seconds": 86400,
                "evidence_refs": ["revalidation:market:roofing:denver"],
            }
        },
    )

    assert payload["decay_evidence_count"] == 1
    assert payload["decay_changes_ranking"] is False
    candidate = payload["candidates"][0]
    assert candidate["opportunity_decay"]["state"] == "ACTIVE"
    assert candidate["opportunity_decay"]["execution_authority"] == "none"


def test_radar_without_decay_evidence_preserves_candidate_behavior():
    payload = build_opportunity_radar(
        generated_at="2026-10-01T12:00:00+00:00",
        market_gps=None,
        community_intent=None,
        competitor_market=None,
    )

    assert payload["decay_evidence_count"] == 0
    assert payload["decay_changes_ranking"] is False
    assert payload["candidates"] == []


def radar_with(evidence, duplicate=False):
    rows = [{"pain_point": pain, "opportunity_event": "observed"}
            for pain in (["one", "one", "two"] if duplicate else ["one", "two"])]
    return build_opportunity_radar(
        generated_at="2026-10-01T12:00:00Z", market_gps=None, competitor_market=None,
        community_intent={"pain_solution_briefs": rows},
        decay_evidence_by_opportunity=evidence,
    )


def valid_decay():
    return {"source_expires_at": "2026-10-02T12:00:00Z", "evidence_refs": ["source:1"],
            "commercial_value": {
                "source_expires_at": "2026-10-02T12:00:00Z", "evidence_refs": ["terms:1"],
                "retained_value_ratio": 0.8, "basis": "explicit_commercial_terms", "basis_ref": "terms:1",
                "effective_from": "2026-10-01T12:00:00Z", "effective_until": "2026-10-02T12:00:00Z"}}


def test_duplicate_identities_receive_no_usable_decay():
    result = radar_with({"community_pain:one": valid_decay(), "community_pain:two": valid_decay()}, True)
    for row in result["candidates"]:
        if row["opportunity_key"] == "community_pain:one":
            assert row["opportunity_decay"]["state"] == "UNKNOWN"
            assert row["opportunity_decay"]["recency_factor_candidate"] is None
            assert row["predictive_revenue_inputs"] == {}
        else:
            assert row["opportunity_decay"]["recency_factor_candidate"] == 0.8


def test_mismatched_identity_fails_closed():
    evidence = valid_decay()
    evidence["opportunity_key"] = "community_pain:two"
    row = radar_with({"community_pain:one": evidence})["candidates"][0]
    assert row["opportunity_decay"]["state"] == "UNKNOWN"
    assert row["opportunity_decay"]["recency_factor_candidate"] is None


def test_malformed_candidate_does_not_abort_radar_or_transport_factors():
    for malformed in (42, [], "bad", {"observed_at": "naive"}, {"freshness_window_seconds": float("inf")}):
        result = radar_with({"community_pain:one": malformed, "community_pain:two": valid_decay()})
        first, second = result["candidates"]
        assert first["opportunity_decay"]["state"] == "UNKNOWN"
        assert second["opportunity_decay"]["recency_factor_candidate"] == 0.8
        assert second["predictive_revenue_inputs"] == {}
        assert result["decay_changes_ranking"] is False
        assert result["revenue_recognition_authority"] == "none"


def test_radar_offer_scope_is_bound_to_candidate():
    evidence = valid_decay()
    evidence["commercial_value"]["offer_key"] = "wrong-offer"
    result = build_opportunity_radar(
        generated_at="2026-10-01T12:00:00Z", market_gps=None, competitor_market=None,
        community_intent={"pain_solution_briefs": [{"pain_point": "one", "opportunity_event": "observed",
                                                    "offer_key": "actual-offer"}]},
        decay_evidence_by_opportunity={"community_pain:one": evidence},
    )
    decay = result["candidates"][0]["opportunity_decay"]
    assert decay["commercial_value"]["state"] == "UNKNOWN"
    assert decay["recency_factor_candidate"] is None
