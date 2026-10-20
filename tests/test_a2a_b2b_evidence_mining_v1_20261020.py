"""Strict owner-source mining and unverified-buyer classification tests."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from empire_os.a2a_b2b_evidence_mining_v1 import (
    mine_targeted_business_evidence, make_mining_source_hold, _domain,
)
from empire_os.a2a_owner_research_protocol_v1 import make_owner_pickup_packets
from empire_os.a2a_target_owner_handoff_v1 import make_owner_research_handoffs
from tests.test_a2a_target_owner_handoff_v1_20261020 import scout, NOW
from tests.test_a2a_prompt_targeted_buyer_research_v1_20261020 import community
from empire_os.a2a_founder_targeting_cycle_v1 import build_prompted_research


def targeting():
    return build_prompted_research({
        "schema_version": "empire.a2a.founder_prompt_target_profiles.v1",
        "owner": "empire.a2a.commercial_signal_miner.v1",
        "execution_authority": "NONE", "contact_authorized": False,
        "campaign_launch_authorized": False,
        "profiles": [
            {"label": "Tampa", "prompt": "Find roofing companies buying inbound calls in Tampa, Florida"},
            {"label": "Little Rock", "prompt": "Find HVAC companies buying appointments in Little Rock, Arkansas"},
            {"label": "NYC", "prompt": "Find general contractor businesses buying permit data in New York City"},
        ],
    }, community())


def fixture_data():
    targets = targeting()
    buyer_scout = scout()
    buyer_scout["generated_at"] = NOW.isoformat()
    handoff = make_owner_research_handoffs(targets, buyer_scout, now=NOW)
    pickup = make_owner_pickup_packets(handoff)
    seeds = {
        "schema_version": "empire.buyer_public_research_seeds.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "outbound_sent": False, "database_write_performed": False,
        "generated_at": NOW.isoformat(),
        "seed_count": 4,
        "fresh_search_result_status": "NO_FRESH_DOMAIN_RESULTS_PROVIDER_HEALTH_UNVERIFIED",
        "search_provider_health_independently_verified": False,
        "seeds": [
            {
                "domain": "flroofing.example", "website": "https://flroofing.example",
                "target_verticals": ["roofing"], "target_markets": ["USA"],
                "source_refs": ["public:first_party:flroofing.example"],
            },
            {
                "domain": "flroofing.example", "website": "https://flroofing.example",
                "target_verticals": ["roofing"], "target_markets": ["USA"],
                "source_refs": ["public:first_party:flroofing.example"],
            },
            {
                "domain": "hvac-au.example", "website": "https://hvac-au.example",
                "target_verticals": ["hvac"], "target_markets": ["AU"],
                "source_refs": ["public:multimarket_review:AU:hvac-au.example"],
            },
            {
                "domain": "hvac-us.example", "website": "https://hvac-us.example",
                "target_verticals": ["hvac"], "target_markets": ["USA"],
                "source_refs": ["public:multimarket_review:USA:hvac-us.example"],
            },
        ],
    }
    for item in seeds["seeds"]:
        item.update({
            "truth_class": "OBSERVED_PUBLIC_RESEARCH",
            "identity_verified": False,
            "buyer_capacity_verified": False,
            "buyer_price_verified": False,
            "commercial_terms_verified": False,
            "outreach_authorized": False,
        })
    nyc = {
        "schema": "empire.permit_property_three_agency_evidence.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "external_outreach_sent": False,
        "customer_facing_distributable": False,
        "rights_review_required_for_customer_distribution": True,
        "permit_event_count": 2,
        "diagnostics": [
            {"verified_business_buyer": False, "commercial_contact_authorized": False,
             "building_tax_lot_evidence_state": "LOT_CONTEXT_ONLY"},
            {"verified_business_buyer": False, "commercial_contact_authorized": False,
             "building_tax_lot_evidence_state": "BIN_UNCONFIRMED"},
        ],
    }
    return targets, pickup, seeds, buyer_scout, nyc


def mined(*args):
    return mine_targeted_business_evidence(*args, now=NOW)


def test_mines_real_shape_but_never_makes_local_buyers():
    data = fixture_data()
    result = mined(*data)
    assert result["public_seed_input_rows_scanned"] == 4
    assert result["distinct_public_business_domains_observed"] == 3
    assert result["nyc_permit_market_context"]["permit_event_records_mined"] == 2
    tampa = next(t for t in result["target_mining_results"] if t["niche"] == "roofing")
    assert tampa["public_business_research_record_count"] == 1
    row = tampa["records"][0]
    assert row["country_hypothesis_supported_by_seed"] is True
    assert row["requested_city_independently_verified"] is False
    assert row["buyer_company_identity_verified"] is False
    assert row["contact_authorized"] is False
    assert result["verified_new_local_buyer_count"] == 0
    assert result["verified_real_lead_count"] == 0
    assert result["new_crawl_performed"] is False


def test_does_not_assume_au_hvac_sells_in_little_rock():
    data = fixture_data()
    result = mined(*data)
    hvac = next(t for t in result["target_mining_results"] if t["niche"] == "hvac")
    assert hvac["public_business_research_record_count"] == 1
    assert hvac["records"][0]["public_business_domain_for_owner_review"] == "hvac-us.example"
    assert hvac["exact_city_verified_buyers"] == 0


def test_buyer_scout_duplicate_domain_does_not_double_count():
    data = list(fixture_data())
    scout_source = data[3]
    scout_source["candidates"] = [{
        "domain": "flroofing.example",
        "website": "https://flroofing.example",
        "outreach_authorized": False,
        "commercial_terms_verified": False,
        "budget_verified": False,
        "candidate_state": "RESEARCH_EVIDENCE_ONLY",
        "buyer_relationship": "unknown",
        "icp_intelligence": {"fit_evidence": {"industry_signal_hits": ["roofing"]}},
    }]
    scout_source["candidate_count"] = 1
    result = mined(*data)
    tampa = next(t for t in result["target_mining_results"] if t["niche"] == "roofing")
    assert tampa["public_business_research_record_count"] == 1
    assert len(tampa["records"][0]["source_families"]) == 2
    assert tampa["records"][0]["source_ref_count_not_independent_confirmations"] == 1


def test_intermediary_is_not_purchaser():
    data = list(fixture_data())
    seed = data[2]["seeds"][0]
    scout_source = data[3]
    scout_source["candidates"] = [{
        "domain": seed["domain"], "outreach_authorized": False,
        "commercial_terms_verified": False, "budget_verified": False,
        "candidate_state": "RESEARCH_EVIDENCE_ONLY",
        "buyer_relationship": "intermediary_or_marketplace",
        "icp_intelligence": {"fit_evidence": {"industry_signal_hits": ["roofing"]}},
    }]
    scout_source["candidate_count"] = 1
    result = mined(*data)
    roof = next(t for t in result["target_mining_results"] if t["niche"] == "roofing")
    assert roof["records"][0]["publisher_or_intermediary_caveat"] is True
    assert roof["records"][0]["review_priority"] == "EXCLUDE_INTERMEDIARY_PENDING_OWNER_REVIEW"
    assert result["verified_real_lead_count"] == 0


def test_malicious_domains_rejected_without_private_addresses():
    assert _domain("https://bob:password@example.org") is None
    assert _domain("http://example.org") is None
    assert _domain("https://127.0.0.1") is None
    assert _domain("https://reddit.com") is None
    assert _domain("https://i.redd.it/media.jpg") is None
    assert _domain("https://images.googleusercontent.com/foo") is None
    assert _domain("https://www.example.com") == "example.com"
    assert _domain("https://example.org:invalid") is None


def test_seed_truth_escalation_fails_closed():
    data = list(fixture_data())
    data[2]["seeds"][0]["buyer_capacity_verified"] = True
    with pytest.raises(ValueError, match="PUBLIC_RESEARCH_TRUTH_ESCALATION"):
        mined(*data)


def test_unauthorised_scout_record_fails_closed():
    data = list(fixture_data())
    data[3]["candidates"] = [{
        "domain": "example.org", "outreach_authorized": True,
        "commercial_terms_verified": False, "budget_verified": False,
        "candidate_state": "RESEARCH_EVIDENCE_ONLY",
    }]
    data[3]["candidate_count"] = 1
    with pytest.raises(ValueError, match="BUYER_SCOUT_TRUTH_ESCALATION"):
        mined(*data)


def test_nyc_permit_is_event_not_selling_buyer():
    data = list(fixture_data())
    data[4]["diagnostics"][0]["verified_business_buyer"] = True
    with pytest.raises(ValueError, match="PERMIT_EVENT_BUYER_CLAIM_UNVERIFIED"):
        mined(*data)


def test_no_fresh_search_claims_without_real_provider_receipt():
    result = mined(*fixture_data())
    assert result["public_provider_fresh_search_status"].startswith("NO_FRESH")
    assert not result["search_provider_health_independently_verified"]
    assert result["source_research_only_no_new_provider_queries"] is True
    assert result["total_target_research_records_before_cross_target_dedupe"] == 2


def test_missing_owner_source_is_unknown_not_zero():
    held = make_mining_source_hold(targeting(),
                                   reason="CANONICAL_MINING_INPUT_UNAVAILABLE", now=NOW)
    assert held["distinct_public_business_domains_observed"] is None
    assert held["source_absence_is_not_zero_market_demand"] is True
    assert held["target_mining_results"] == []
    assert held["verified_real_lead_count"] == 0


def test_real_current_owner_reports_smoke_if_installed():
    root = Path("/srv/empire_os/runtime")
    required = (
        "buyer_acquisition/public_research_seeds.json",
        "buyer_acquisition/scout_latest.json",
        "data_brokerage/nyc_dobnow_property_three_agency_latest.json",
    )
    if not all((root/x).is_file() for x in required):
        pytest.skip("No current owner reports mounted")
    t, pk, *_ = fixture_data()
    seeds = json.loads((root/required[0]).read_text())
    scout_real = json.loads((root/required[1]).read_text())
    nyc = json.loads((root/required[2]).read_text())
    report = mine_targeted_business_evidence(t, pk, seeds, scout_real, nyc)
    assert report["public_seed_input_rows_scanned"] >= 0
    assert report["new_crawl_performed"] is False
    assert report["verified_real_lead_count"] == 0
    assert report["crm_write_performed"] is False
