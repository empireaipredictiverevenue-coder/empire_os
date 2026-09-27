from empire_os.competitor_account_brief import (
    build_account_brief_batch,
    build_account_intelligence_brief,
    critique_claim,
)


def _company():
    return {
        "entity_id": "entity-golden",
        "company_name": "Golden Spike Roofing Inc",
        "company_website": "https://goldenspikeroofing.com",
        "unique_evidence_count": 3,
        "research_priority": {
            "research_priority_score": 84.33,
            "stack_state": "STACKED",
        },
        "evidence": [
            {
                "competitor_key": "elite-roofing-solar",
                "source_ref": "https://bestcoloradoroofers.com/denver/",
            },
            {
                "competitor_key": "elite-roofing-solar",
                "source_ref": "https://www.cedur.com/best-roofers-in-denver-co/",
            },
            {
                "competitor_key": "elite-roofing-solar",
                "source_ref": "https://www.ontoplist.com/roofing-companies/co/denver/",
            },
        ],
    }


def _research():
    return {
        "entity_id": "entity-golden",
        "company_name": "Golden Spike Roofing Inc",
        "company_domain": "goldenspikeroofing.com",
        "research_rank": 1,
        "requested_action": "deep_account_research",
        "next_step": "account_research_brief_ready_for_review",
        "observation_count": 4,
        "observations": [
            {
                "url": "https://goldenspikeroofing.com/",
                "domain": "goldenspikeroofing.com",
                "title": "Golden Spike Roofing Inc",
                "first_party_domain_match": True,
                "existing_evidence_source": False,
                "observation_type": "public_first_party_page",
                "verified_fact": False,
            },
            {
                "url": "https://bestcoloradoroofers.com/denver/",
                "domain": "bestcoloradoroofers.com",
                "title": "Denver roofers",
                "first_party_domain_match": False,
                "existing_evidence_source": True,
                "observation_type": "reobserved_public_evidence",
                "verified_fact": False,
            },
            {
                "url": "https://directory.example/golden-spike",
                "domain": "directory.example",
                "title": "Golden Spike Roofing Inc directory",
                "first_party_domain_match": False,
                "existing_evidence_source": False,
                "observation_type": "public_search_result",
                "verified_fact": False,
            },
        ],
    }


def test_claim_critic_supports_observed_sourced_claim():
    result = critique_claim({
        "claim_type": "first_party_web_presence_observed",
        "text": "Golden Spike Roofing Inc first-party web presence was observed.",
        "source_refs": ["https://goldenspikeroofing.com/"],
        "observed": True,
    })

    assert result["verdict"] == "SUPPORTED"
    assert result["blockers"] == []


def test_claim_critic_blocks_unsourced_commercial_inference():
    result = critique_claim({
        "claim_type": "buyer_state",
        "text": "Golden Spike Roofing Inc has buyer intent and is ready to buy.",
        "source_refs": [],
        "observed": False,
    })

    assert result["verdict"] == "BLOCKED"
    assert "claim_source_required" in result["blockers"]
    assert "unsupported_commercial_or_market_inference" in result["blockers"]


def test_account_brief_publishes_supported_claims_only():
    result = build_account_intelligence_brief(
        _company(),
        _research(),
    )

    assert result["company_name"] == "Golden Spike Roofing Inc"
    assert result["canonical_evidence_count"] == 3
    assert result["claim_critic"]["supported_count"] >= 2
    assert result["claim_critic"]["blocked_count"] == 0
    assert result["claim_critic"]["all_published_claims_supported"] is True
    assert result["buyer_intent"] is False
    assert result["commercial_intent"] is False
    assert result["outreach_enabled"] is False
    assert result["actual_revenue"] is False

    assert result["unverified_search_observation_count"] == 1
    assert all(
        claim["verdict"] == "SUPPORTED"
        for claim in result["claims"]
    )


def test_batch_keeps_claims_and_commercial_state_separate():
    batch = build_account_brief_batch(
        {"companies": [_company()]},
        {"actions": [_research()]},
    )

    assert batch["brief_count"] == 1
    assert batch["supported_claim_count"] >= 2
    assert batch["blocked_claim_count"] == 0
    assert batch["all_published_claims_supported"] is True
    assert batch["buyer_intent_inferred"] is False
    assert batch["commercial_intent_inferred"] is False
    assert batch["outreach_enabled"] is False
    assert batch["actual_revenue"] is False
    assert batch["execution_authority"] == "none"
