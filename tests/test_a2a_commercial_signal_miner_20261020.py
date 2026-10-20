"""Bounded tests for A2A signal miner. All fixtures are synthetic."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from empire_os.a2a_commercial_signal_miner import AGENT_ID, agent_card, mine_signals

NOW = datetime(2026, 10, 20, 9, 0, tzinfo=timezone.utc)


def community(**extra):
    data = {
        "schema_version": "empire.community_intent.v2", "mode": "OBSERVE",
        "execution_authority": "none", "outreach_authority": "none",
        "observed_at": NOW.isoformat(),
        "source_status": {
            "reddit": {"ok": True}, "linkedin": {"ok": False},
        },
        "pain_solution_briefs": [
            {"pain_point": "lead_generation", "observed_mentions": 7,
             "high_intent_mentions": 1, "source_mix": ["reddit", "linkedin"],
             "offer_key": "predictive_revenue_demand_engine"},
            {"pain_point": "revenue_growth", "observed_mentions": 2,
             "high_intent_mentions": 1, "source_mix": ["reddit"]},
        ],
    }
    return {**data, **extra}


def gps(**extra):
    data = {
        "schema_version": "empire.market_sweep_revenue_gps.v1", "mode": "OBSERVE",
        "execution_authority": "none", "outreach_enabled": False,
        "revenue_inferred": False, "buyer_intent_inferred": False,
        "commercial_intent_inferred": False, "generated_at": NOW.isoformat(),
        "research_queue": [
            {"niche": "general_contractor", "metro": "nyc",
             "research_priority_score": 80,
             "external_execution_authorized": False, "mutation_authorized": False},
            {"niche": "roofing", "metro": "tampa, fl",
             "research_priority_score": 5,
             "external_execution_authorized": False, "mutation_authorized": False},
        ],
    }
    return {**data, **extra}


def review(c=None, g=None):
    return mine_signals(community=community() if c is None else c,
                        revenue_gps=gps() if g is None else g, now=NOW)


def test_ranks_realistic_data_buyers_as_research_not_verified_buyers():
    result = review()
    assert result["agent_id"] == AGENT_ID
    assert result["market_candidate_count"] == 2
    assert result["buyer_signal_research_count"] == 4
    assert result["campaign_brief_count"] == 4
    first = result["prioritized_research_signals"][0]
    assert first["niche"] == "general_contractor"
    assert first["metro"] == "nyc"
    assert first["offer_hypothesis"] == "nyc_permit_project_verification"
    assert result["verified_buyers_discovered"] == 0
    assert result["verified_money_opportunities"] == 0
    assert not result["revenue_verified"]
    assert not result["data_resale_rights_verified"]
    assert not result["network_requests"]
    assert not result["publishing_performed"]
    assert all(not x["verified_buyer"] for x in result["campaign_briefs"])
    assert all("SOURCE_RIGHTS_REVIEW" in x["gates"] for x in result["campaign_briefs"])


def test_expired_snapshots_cannot_create_current_signals():
    expired = (NOW - timedelta(days=7)).isoformat()
    result = review(community(observed_at=expired), gps(generated_at=expired))
    assert result["status"] == "SOURCE_RESEARCH_HOLD"
    assert result["campaign_briefs"] == []
    assert result["source_status"]["community_intent"]["state"] == "SOURCE_STALE_OR_INVALID_TIMESTAMP"


def test_untrusted_authority_is_rejected():
    result = review(community(outreach_authority="enabled"),
                    gps(revenue_inferred=True))
    assert result["campaign_briefs"] == []
    assert result["source_status"]["revenue_gps"]["state"] == "REJECT_EXCESS_AUTHORITY"


def test_zero_external_authority_and_no_private_audience_harvest():
    result = review()
    assert result["outbound_sent"] is False
    assert result["database_writes"] is False
    assert result["meta_scraping"] is False
    assert result["payment_links_created"] is False
    assert all("unconsented_custom_audiences" in x["do_not_use"]
               for x in result["campaign_briefs"])
    assert result["source_status"]["community_intent"]["collection_quality"]["linkedin"] == "LATEST_RETRIEVAL_NOT_VERIFIED"


def test_agent_card_is_identity_candidate_not_fake_registration():
    card = agent_card()
    assert card["agent_id"] == AGENT_ID
    assert card["registration"]["external_agent_network"] == "not_registered"
    assert card["registration"]["cryptographic_identity"] == "not_provisioned"
    assert not card["registration"]["trusted_by_other_agents"]
    assert len(card["capabilities"]) == 7
    assert all(not x["callable_endpoint_deployed"] for x in card["capabilities"])


def test_dedupes_market_and_holds_unsafe_campaign_target():
    malformed = dict(gps()["research_queue"][0])
    duplicated = dict(malformed)
    unsafe = {**malformed, "metro": "atlanta, ga",
              "external_execution_authorized": True}
    rows = [malformed, duplicated, unsafe]
    result = review(g=gps(research_queue=rows))
    assert result["market_candidate_count"] == 1
    assert "DUPLICATE_GPS_MARKET" in result["holds"]
    assert "REJECT_UNSAFE_GPS_RESEARCH_ROW" in result["holds"]


def test_malformed_pain_counts_not_promoted():
    rows = [{"pain_point": "lead_generation", "observed_mentions": 2,
             "high_intent_mentions": 8}]
    result = review(community(pain_solution_briefs=rows))
    assert "BAD_COMMUNITY_INTENT_COUNTS" in result["holds"]
    assert all(x["source_domain"] != "community_intent" for x in result["prioritized_research_signals"])
