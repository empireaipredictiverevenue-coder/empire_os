"""Economics-first buyer research is not buyer authorisation or revenue."""
from datetime import datetime, timezone
from copy import deepcopy
import json

import pytest

from empire_os.buyer_specification_readiness import REQUIRED_GATES
from empire_os.buyer_scout_commercial_awareness import review_buyer_scout_awareness
from empire_os.buyer_scout_economic_intelligence import (
    build_buyer_economic_gap_review, _review_pilots,
)

NOW = datetime(2026, 10, 19, 20, 0, tzinfo=timezone.utc)


def sources(*, pilots=None, candidates=None, known=None, targets=None):
    stamp = NOW.isoformat()
    scout = {
        "schema_version": "empire.buyer_acquisition_scout.v1",
        "generated_at": stamp, "mode": "OBSERVE",
        "execution_authority": "none", "outbound_sent": False,
        "candidates": candidates if candidates is not None else [
            {"domain": "publisher.test.com",
             "buyer_relationship": "intermediary_or_marketplace",
             "explicit_direct_buyer_evidence": False},
        ],
    }
    actions = {
        "schema_version": "empire.buyer_qualification_actions.v1",
        "generated_at": stamp, "mode": "OBSERVE",
        "execution_authority": "none", "outbound_sent": False,
        "outbound_enabled": False, "targets": targets or [],
    }
    registry = {
        "schema_version": "empire.commercial_relationship_registry.v1",
        "generated_at": stamp, "mode": "OBSERVE",
        "execution_authority": "NONE", "outbound_sent": False,
        "outbound_authorized": False, "gmail_snapshot_fresh": False,
        "relationships": known or [],
        "partner_pilot_readiness_queue": pilots if pilots is not None else [pilot()],
    }
    return scout, actions, registry


def pilot(index=0):
    return {
        "entity_key": f"private_partner_{index}", "company": "PRIVATE PARTNER",
        "activation_gates": {key: False for key in REQUIRED_GATES},
        "gate_count_total": len(REQUIRED_GATES), "gate_count_verified": 0,
        "outbound_authorized": False, "live_traffic_authorized": False,
        "lead_smart_route_and_terms_reused": False,
        "tracking_or_route_mutation_performed": False,
        "activation_stage": "WAITING_BUYER_BUYBOX",
        "inbound_requirement_review_status": "NO_NEW_VERIFIED_GMAIL_OBSERVATION",
        "two_way_gmail_thread_observed": True,
        "mailbox_snapshot_fresh": True,
        "reviewed_gmail_thread_id": "private_thread",
    }


def review(*, pilots=None, candidates=None, known=None, targets=None):
    scout, actions, registry = sources(
        pilots=pilots, candidates=candidates, known=known, targets=targets)
    awareness = review_buyer_scout_awareness(
        scout, actions, registry, as_of=NOW)
    return build_buyer_economic_gap_review(awareness, registry, as_of=NOW)


def test_two_way_thread_never_claims_buyer_capacity_or_price():
    d = review()
    assert d["partner_pilots_reviewed"] == 1
    assert d["partner_pilots_with_two_way_history"] == 1
    assert d["partner_pilots_without_verified_buybox"] == 1
    assert d["partner_pilots_without_verified_payable_terms"] == 1
    assert d["verified_paying_buyer_capacity"] == 0
    assert d["active_confirmed_paying_pilots"] == 0
    assert d["buyer_activation_authorized"] is False
    assert d["outbound_authorized"] is False
    assert d["canonical_empiredb_writes"] is False
    assert d["next_pilot_evidence_queue"][0]["buyer_per_lead_or_call_price_verified"] is False
    assert "PRIVATE PARTNER" not in json.dumps(d)
    assert "private_thread" not in json.dumps(d)


def test_historical_requirements_get_reconciliation_first():
    p = pilot()
    p["inbound_requirement_review_status"] = "HISTORICAL_REPORTED_REQUIREMENTS_HOLD"
    d = review(pilots=[p])
    assert d["next_pilot_evidence_queue"][0]["commercial_next_research_task"] == (
        "RECONCILE_HISTORICAL_BUYER_REQUIREMENTS_BEFORE_ASKING_TERMS")


def test_traffic_deferred_partner_not_auto_counted_as_buyer():
    p = pilot()
    p["activation_stage"] = "DEFERRED_PENDING_ESTABLISHED_TRAFFIC"
    d = review(pilots=[p])
    assert d["next_pilot_evidence_queue"][0]["commercial_next_research_task"] == (
        "VERIFY_IF_BUYER_WANTS_FUNDED_PILOT_WITH_NEW_TRAFFIC_CONSTRAINT")
    assert d["verified_paying_buyer_capacity"] == 0


def test_duplicate_pilot_id_is_hold():
    scout, actions, registry = sources(pilots=[pilot(),pilot()])
    awareness = review_buyer_scout_awareness(scout, actions, registry, as_of=NOW)
    with pytest.raises(ValueError, match="duplicate"):
        build_buyer_economic_gap_review(awareness, registry, as_of=NOW)


def test_invalid_gate_population_holds():
    for corrupt in (
        lambda p: p["activation_gates"].pop("contract_and_compliance_approved"),
        lambda p: p.update(gate_count_total=8),
        lambda p: p.update(live_traffic_authorized=True),
        lambda p: p.update(lead_smart_route_and_terms_reused=True),
    ):
        p = pilot()
        corrupt(p)
        with pytest.raises(ValueError):
            _review_pilots({"partner_pilot_readiness_queue":[p]})


def test_verified_gates_alone_do_not_approve_buyer_or_traffic():
    p=pilot()
    p["activation_gates"] = {key:True for key in REQUIRED_GATES}
    p["gate_count_verified"] = len(REQUIRED_GATES)
    d = review(pilots=[p])
    row=d["next_pilot_evidence_queue"][0]
    assert row["commercial_next_research_task"] == (
        "OWNER_REVIEW_COMPLETED_BUYER_EVIDENCE_NO_AUTO_ACTIVATION")
    assert d["verified_paying_buyer_capacity"] == 0
    assert row["buyer_daily_capacity_verified"] is False
    assert row["money_available_for_pilot_verified"] is False
    assert row["activation_authorized"] is False


def test_intermediary_never_promoted_as_paying_customer():
    d=review()
    row=d["scout_next_commercial_research_queue"][0]
    assert row["commercial_role_review"] == "INTERMEDIARY_OR_PUBLISHER"
    assert row["research_task"] == (
        "VERIFY_INTERMEDIARY_OWN_SPEND_VS_PUBLISHER_RECRUITMENT")
    assert row["first_payer_verified"] is False


def test_prior_contact_and_suppression_remain_holds():
    d = review(
        known=[{"identity_domains":["publisher.test.com"],
                "last_inbound_at":NOW.isoformat(), "do_not_pursue":True}],
    )
    row=d["scout_next_commercial_research_queue"][0]
    assert row["suppression_hold"] is True
    assert row["automatic_outbound_authorized"] is False
    assert row["research_task"] == "SUPPRESSION_REVIEW_ONLY"


def test_mismatched_registry_snapshot_rejected():
    s,a,r = sources()
    awareness=review_buyer_scout_awareness(s,a,r,as_of=NOW)
    r["generated_at"] = (NOW.replace(hour=19)).isoformat()
    with pytest.raises(ValueError,match="version"):
        build_buyer_economic_gap_review(awareness,r,as_of=NOW)


def test_untrusted_awareness_task_cannot_inject_raw_person_data():
    s,a,r = sources()
    awareness=review_buyer_scout_awareness(s,a,r,as_of=NOW)
    awareness["review_queue"][0]["next_evidence_task"]="Private Person private@example.com"
    with pytest.raises(ValueError,match="unsupported"):
        build_buyer_economic_gap_review(awareness,r,as_of=NOW)


def test_missing_or_duplicate_economic_company_domains_fail_closed():
    s,a,r = sources()
    awareness=review_buyer_scout_awareness(s,a,r,as_of=NOW)
    awareness["review_queue"][0]["domain"] = "not a domain"
    with pytest.raises(ValueError,match="invalid_commercial_domain"):
        build_buyer_economic_gap_review(awareness,r,as_of=NOW)


def test_no_pilot_does_not_invent_capacity():
    d=review(pilots=[])
    assert d["partner_pilots_reviewed"]==0
    assert d["verified_paying_buyer_capacity"]==0
    assert d["partner_pilots_without_verified_payable_terms"]==0
