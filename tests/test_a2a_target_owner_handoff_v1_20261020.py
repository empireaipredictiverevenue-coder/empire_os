"""Read-only Buyer Scout crosswalk cannot promote research into verified buyers."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import pytest

from empire_os.a2a_target_owner_handoff_v1 import make_owner_research_handoffs, make_handoff_source_hold
from empire_os.a2a_founder_targeting_cycle_v1 import build_prompted_research
from tests.test_a2a_prompt_targeted_buyer_research_v1_20261020 import community, NOW


def targeting():
    config = {
        "schema_version": "empire.a2a.founder_prompt_target_profiles.v1",
        "owner": "empire.a2a.commercial_signal_miner.v1",
        "execution_authority": "NONE",
        "contact_authorized": False, "campaign_launch_authorized": False,
        "profiles": [
            {"label": "Tampa", "prompt": "Find roofing companies buying inbound calls in Tampa, Florida"},
            {"label": "NYC", "prompt": "Find general contractor businesses buying permit data in New York City"},
        ]
    }
    return build_prompted_research(config, community())


def scout(*, candidates=None):
    items = [] if candidates is None else candidates
    return {
        "schema_version": "empire.buyer_acquisition_scout.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "outbound_sent": False, "database_write_performed": False,
        "generated_at": NOW.isoformat(),
        "candidate_count": len(items), "candidates": items,
    }


def candidate(*, niche="roofing", metro="tampa, fl", identity=False,
              budget=False, terms=False):
    return {
        "canonical_seed_niche": niche,
        "canonical_seed_metro": metro,
        "canonical_identity_verified": identity,
        "budget_verified": budget,
        "commercial_terms_verified": terms,
        "outreach_authorized": False,
        "candidate_state": "RESEARCH_EVIDENCE_ONLY",
        "business_name": "CONFIDENTIAL TEST COMPANY, NOT FOR EXPORT",
        "domain": "secret-testing-company.example",
        "first_party_emails": ["no-export@example.com"],
        "first_party_people": ["PRIVATE REVIEW RECORD"],
    }


def test_emits_two_owner_review_tickets_per_target_with_stable_ids():
    t = targeting()
    report = make_owner_research_handoffs(t, scout(), now=NOW)
    assert report["profiles_reviewed"] == 2
    assert report["prepared_handoff_ticket_count"] == 4
    assert report["tasks_dispatched"] == 0
    assert report["owner_queue_published"] is False
    assert report["externally_verified_new_buyers"] == 0
    assert {r["review_owner"] for r in report["handoff_tickets"]} == {
        "community_intent", "buyer_scout"
    }
    repeated = make_owner_research_handoffs(t, scout(), now=NOW)
    assert [r["idempotency_key"] for r in report["handoff_tickets"]] == [
        r["idempotency_key"] for r in repeated["handoff_tickets"]
    ]


def test_unverified_or_geographically_unknown_company_not_linked():
    records = [
        candidate(identity=False, budget=True, terms=True),
        candidate(identity=True, budget=False, terms=True),
        candidate(identity=True, budget=True, terms=True, metro="phoenix, az"),
        {"canonical_seed_niche": "hvac", "canonical_seed_metro": "tampa, fl",
         "canonical_identity_verified": True, "budget_verified": True,
         "commercial_terms_verified": True, "outreach_authorized": False},
        {"canonical_seed_niche": "roofing",
         "canonical_identity_verified": True, "budget_verified": True,
         "commercial_terms_verified": True, "outreach_authorized": False},
    ]
    report = make_owner_research_handoffs(targeting(), scout(candidates=records), now=NOW)
    assert all(x["exact_sector_market_evidence_ready_for_owner_validation"] == 0
               for x in report["handoff_tickets"])
    assert "CONFIDENTIAL" not in str(report)
    assert "no-export@" not in str(report)


def test_exact_fully_flagged_market_overlap_is_still_not_a_verified_new_buyer():
    record = candidate(identity=True, budget=True, terms=True)
    report = make_owner_research_handoffs(targeting(), scout(candidates=[record]), now=NOW)
    tampa = [x for x in report["handoff_tickets"] if x["market"] == "tampa, fl"]
    assert len(tampa) == 2
    assert all(x["exact_sector_market_evidence_ready_for_owner_validation"] == 1
               for x in tampa)
    assert all(x["canonical_overlap_status"].startswith("EXACT_SECTOR") for x in tampa)
    assert report["externally_verified_new_buyers"] == 0
    assert not report["owner_response_received"]
    assert "secret-testing-company.example" not in str(report)


def test_cannot_spoof_outbound_permissions_or_owner_authority():
    t = targeting()
    t["profiles"][0]["source_review"]["contact_authorized"] = True
    with pytest.raises(ValueError, match="PRIVILEGE_ESCALATION"):
        make_owner_research_handoffs(t, scout(), now=NOW)
    t = targeting()
    bad = scout(candidates=[candidate()])
    bad["candidates"][0]["outreach_authorized"] = True
    with pytest.raises(ValueError, match="EXCEEDS"):
        make_owner_research_handoffs(t, bad, now=NOW)
    bad = scout()
    bad["database_write_performed"] = True
    with pytest.raises(ValueError, match="UNTRUSTED_CANONICAL"):
        make_owner_research_handoffs(t, bad, now=NOW)


def test_stale_scout_and_changed_candidate_total_held():
    s = scout()
    s["generated_at"] = "2024-01-01T00:00:00Z"
    with pytest.raises(ValueError, match="STALE"):
        make_owner_research_handoffs(targeting(), s, now=NOW)
    s = scout()
    s["candidate_count"] = 100
    with pytest.raises(ValueError, match="COUNT_MISMATCH"):
        make_owner_research_handoffs(targeting(), s, now=NOW)


def test_queries_are_niche_specific_without_user_text_injection():
    report = make_owner_research_handoffs(targeting(), scout(), now=NOW)
    for t in report["handoff_tickets"]:
        assert len(t["suggested_research_queries_not_executed"]) == 3
        assert all(t["market"] in q for q in t["suggested_research_queries_not_executed"])
        assert all(not t["may_send_messages"] and not t["may_write_canonical_crm"]
                   for t in report["handoff_tickets"])


def test_missing_owner_source_fails_closed_without_blocking_other_research():
    held = make_handoff_source_hold(
        reason="BUYER_SCOUT_SOURCE_UNAVAILABLE", profile_count=3, now=NOW,
    )
    assert held["prepared_handoff_ticket_count"] == 0
    assert held["handoff_tickets"] == []
    assert held["tasks_dispatched"] == 0
    assert held["externally_verified_new_buyers"] == 0
    assert held["existing_scout_research_candidate_count"] is None
    with pytest.raises(ValueError):
        make_handoff_source_hold(reason="SOURCE_READ_OK", profile_count=3, now=NOW)
