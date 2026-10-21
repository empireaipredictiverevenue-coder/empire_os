"""Buyer capacity and CRM gaps cannot upgrade unverified intent into outreach."""
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import pytest

from empire_os.jev_commercial_action_readiness import review_portfolio_commercial_readiness
from empire_os.jev_commercial_signal_portfolio import review_existing_intent_signals
from test_jev_commercial_signal_portfolio_20261021 import inputs

NOW=datetime(2026,10,21,22,0,tzinfo=timezone.utc)


def portfolio():
    return review_existing_intent_signals(inputs())


def capacity(*,positive=False):
    return {
        "schema_version":"empire.buyer_capacity_readiness.v1",
        "mode":"OBSERVE","execution_authority":"none",
        "allocation_executed":False,"allocation_ready":False,
        "payment_action":False,"revenue_recognition":False,
        "observed_at":(NOW-timedelta(minutes=8)).isoformat(),
        "buyers_seen":5,"reviewed":1,"market_defined":4,
        "positive_capacity_configured":3,
        "delivery_destination_present":2,
        "capacity_verified":1 if positive else 0,
        "terms_verified":1 if positive else 0,
        "delivery_verified":1 if positive else 0,
        "commercially_activated":1 if positive else 0,
        "fully_activated":0,
        "buyer_private_address":"do-not-expose@example.invalid",
    }


def registry(*,suppressed=True,fresh_mail=False):
    return {
        "schema_version":"empire.commercial_relationship_registry.v1",
        "mode":"OBSERVE","outbound_authorized":False,"outbound_sent":False,
        "execution_authority":"none",
        "generated_at":(NOW-timedelta(minutes=3)).isoformat(),
        "gmail_snapshot_captured_at":(
            NOW-timedelta(minutes=4) if fresh_mail
            else NOW-timedelta(days=3)).isoformat(),
        "gmail_snapshot_fresh":fresh_mail,
        "automatic_live_gmail_ingest_configured":fresh_mail,
        "relationships":[
            {"company":"PrivateName Corp","entity_key":"private.example",
             "stage":"CONTACTED_AWAITING_RESPONSE","do_not_pursue":False,
             "bounced_addresses":[],"last_outbound_at":"2026-10-18T09:00:00Z"},
            {"company":"BlockedCo","entity_key":"blocked.example",
             "stage":"AWAITING_BUYER","do_not_pursue":suppressed,
             "bounced_addresses":(["blocked@example.invalid"] if suppressed else [])},
        ],
    }


def review(*,buyer=None,relationships=None):
    return review_portfolio_commercial_readiness(
        portfolio(),buyer_capacity=buyer,relationships=relationships,as_of=NOW)


def test_existing_buyer_and_crm_evidence_stays_review_only():
    result=review(buyer=capacity(),relationships=registry())
    assert result["source_signal_review_count"]==3
    assert result["buyer_capacity_status"]=="NO_VERIFIED_COMMERCIAL_CAPACITY"
    assert result["buyer_capacity_counts"]["buyers_seen"]==5
    assert result["specific_buybox_verified"] is False
    assert result["relationship_registry_status"]=="GMAIL_SNAPSHOT_HOLD"
    assert result["total_relationships"]==2
    assert result["aggregate_suppression_or_bounce_review_count"]==1
    assert "CRM_OR_MAILBOX_EVIDENCE_NOT_CURRENT" in result["blocking_reasons"]
    assert result["review_steps"][0]["task"]=="FIRST_PARTY_IDENTITY_RESEARCH"
    assert result["review_steps"][-1]["task"]=="EXISTING_CRM_RELATIONSHIP_AND_SUPPRESSION_RECONCILIATION"
    assert all(step["action_authorized"] is False for step in result["review_steps"])
    assert result["outreach_sent"]==0
    assert result["canonical_prospects_created"]==0
    assert result["database_writes"] is False
    assert result["payment_mutations"] is False
    assert result["execution_authority"]=="none"
    raw=json.dumps(result)
    assert "PrivateName" not in raw
    assert "blocked@example.invalid" not in raw
    assert "private.example" not in raw


def test_positive_aggregate_and_live_mail_do_not_authorize_individual_match():
    result=review(buyer=capacity(positive=True),
                  relationships=registry(suppressed=False,fresh_mail=True))
    assert result["buyer_capacity_status"]=="AGGREGATE_CAPACITY_NOT_SPECIFIC_BUYBOX"
    assert result["relationship_registry_status"]=="OBSERVE_REVIEW"
    assert result["mailbox_current"] is True
    assert result["individual_buyer_identity_join_verified"] is False
    assert result["verified_buyer_capacity_for_portfolio"] is False
    assert result["suppression_clear_for_any_individual"] is False
    assert result["new_replies_verified"] is False
    assert result["commercial_offers_ready"]==0
    assert result["outreach_sent"]==0


def test_missing_readers_do_not_make_buyers_available():
    result=review(buyer=None,relationships=None)
    assert result["buyer_capacity_status"]=="SOURCE_MISSING"
    assert result["relationship_registry_status"]=="UNAVAILABLE"
    assert result["total_relationships"] is None
    assert result["aggregate_suppression_or_bounce_review_count"] is None
    assert result["suppression_clear_for_any_individual"] is False
    assert result["mailbox_current"] is False


def test_stale_buyer_evidence_and_stale_registry_are_held():
    buyer=capacity()
    buyer["observed_at"]=(NOW-timedelta(hours=7)).isoformat()
    relationships=registry()
    relationships["generated_at"]=(NOW-timedelta(hours=3)).isoformat()
    result=review(buyer=buyer,relationships=relationships)
    assert result["buyer_capacity_status"]=="SOURCE_STALE"
    assert result["relationship_registry_status"]=="STALE_HELD"
    assert result["customer_delivery_authorized"] is False


@pytest.mark.parametrize("change",[
    lambda p:p.update(outreach_sent=1),
    lambda p:p.update(identity_promotions=1),
    lambda p:p.update(actual_revenue=True),
    lambda p:p.update(database_writes=True),
    lambda p:p["items"][0].update(identity_verified=True),
    lambda p:p["items"][0].update(signal_event_sha256="wrong"),
    lambda p:p.update(lane_counts={"REVIEW_IDENTITY":99}),
])
def test_spoofed_buyer_or_intent_authority_is_rejected(change):
    p=portfolio()
    change(p)
    with pytest.raises(ValueError):
        review_portfolio_commercial_readiness(
            p,buyer_capacity=capacity(),relationships=registry(),as_of=NOW)


def test_no_naive_clock():
    with pytest.raises(ValueError):
        review_portfolio_commercial_readiness(
            portfolio(),buyer_capacity=None,relationships=None,
            as_of=datetime(2026,10,21,22))


def test_live_aggregate_readback_has_no_identifying_contact_data():
    path=(Path(__file__).resolve().parents[1] /
          "docs/commercial/JEV_COMMERCIAL_ACTION_READINESS_20261021.json")
    result=json.loads(path.read_text())
    assert result["schema_version"]=="empire.jev.commercial_action_readiness.v1"
    assert result["buyer_capacity_counts"]["capacity_verified"]==0
    assert result["buyer_capacity_counts"]["terms_verified"]==0
    assert result["buyer_capacity_counts"]["delivery_verified"]==0
    assert result["specific_buybox_verified"] is False
    assert result["source_signal_review_count"]==35
    assert result["relationship_registry_status"]=="GMAIL_SNAPSHOT_HOLD"
    assert result["outreach_sent"]==0
    assert result["database_writes"] is False
    assert result["execution_authority"]=="none"
    text=path.read_text()
    assert "@" not in text
    assert "reddit.com" not in text
    assert "entity_key" not in text
    assert "source_reference_sha256" not in text
