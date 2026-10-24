"""Buyer commercial terms != supply, approved live traffic or received money."""
from datetime import datetime, timezone

import pytest

from empire_os.revenue_first_buyer_offer_triage import (
    review_buyer_offer, review_buyer_offer_portfolio,
)

NOW = datetime(2026, 10, 24, 1, tzinfo=timezone.utc)


def reply(s, n):
    return {"message_ref": f"gmail-reviewed:{n}",
            "received_at": "2026-10-23T21:00:00Z", "claim": s}


def buyer(**changes):
    d = {
        "buyer_key": "buyer-one",
        "market": "US",
        "vertical": "garage_door_repair",
        "programme": "PAY_PER_CALL",
        "message_claims": [reply("BUYER_PILOT_TERMS_PROPOSED", "a")],
        "proposed_payout_cents": 5000,
        "payout_currency": "USD",
        "candidate_source_exists": False,
        "independently_verified_qualified_demand": False,
        "review_owner": "sales_director_operator",
    }
    d.update(changes)
    return d


def test_genuine_buyer_offer_is_not_earned_revenue():
    r = review_buyer_offer(buyer(), as_of=NOW)
    assert r["reported_terms_posture"] == "BUYER_TERMS_OFFERED_NOT_ONBOARDED"
    assert r["proposed_payout_cents"] == 5000
    assert r["quoted_payout_is_settled_earnings"] is False
    assert r["partner_onboarded_and_approved"] is False
    assert r["source_eligibility_independently_verified"] is False
    assert r["accepted_calls_count"] is None
    assert r["settled_revenue_cents"] is None
    assert r["website_live_traffic_authorized"] is False
    assert r["buyer_sends_authorized"] is False
    assert "OWNED_COMPLIANT_SOURCE_NOT_READY" in r["blockers"]


def test_same_buyer_open_and_paused_email_conflict_holds():
    r = review_buyer_offer(buyer(message_claims=[
        reply("BUYER_ONBOARDING_PAUSED", "a"),
        reply("BUYER_REVIEW_OPEN", "b"),
    ]), as_of=NOW)
    assert r["reported_terms_posture"] == "CONFLICTING_BUYER_ONBOARDING_HOLD"
    assert "CONFLICTING_BUYER_ONBOARDING_STATEMENTS" in r["blockers"]
    assert r["next_action"] == "RECONCILE_CONTRADICTORY_BUYER_RESPONSES_NO_ACTIVATION"


def test_buyer_direct_number_test_does_not_activate_traffic():
    r = review_buyer_offer(buyer(
        vertical="roofing",
        message_claims=[reply("BUYER_DIRECT_ROUTE_TESTED_CLAIM", "s")],
    ), as_of=NOW)
    assert r["reported_terms_posture"] == "DIRECT_BUYER_ROUTE_CLAIM_ONLY"
    assert r["next_action"] == "COMPLETE_EXISTING_WEBSITE_LEGAL_TRACKING_FINANCE_GATES"
    assert r["website_live_traffic_authorized"] is False


def test_market_does_not_create_offer_cross_license():
    r = review_buyer_offer_portfolio([
        buyer(buyer_key="one"),
        buyer(buyer_key="two", market="UK", vertical="roofing",
              proposed_payout_cents=None, payout_currency=None,
              message_claims=[reply("BUYER_APPLICATION_REQUIRED", "b")]),
    ], as_of=NOW)
    assert r["buying_relationships_not_cross_licensed"] is True
    assert r["reviewed_buyers"][1]["proposed_payout_cents"] is None
    assert r["verified_settled_revenue_cents"] is None
    assert r["verified_customer_enquiries"] is None
    assert r["crm_mutations"] is False
    assert r["outbound_sent"] is False


def test_b2b_intelligence_has_no_ppc_payout():
    review = review_buyer_offer(buyer(
        programme="B2B_INTELLIGENCE", vertical="property_intelligence",
        proposed_payout_cents=None, payout_currency=None,
        message_claims=[],
    ), as_of=NOW)
    assert review["reported_terms_posture"] == "BUYER_INTEREST_NOT_VERIFIED"
    assert review["settled_revenue_cents"] is None


@pytest.mark.parametrize("changes", [
    {"proposed_payout_cents": -1},
    {"proposed_payout_cents": 1000001},
    {"proposed_payout_cents": 5.5},
    {"proposed_payout_cents": 5000, "payout_currency": "GBP"},
    {"proposed_payout_cents": None, "payout_currency": "USD"},
    {"vertical": "HVAC_NOT_REVIEWED"},
    {"programme": "B2B_INTELLIGENCE"},
    {"buyer_key": "a person@example.com"},
    {"review_owner": "outbound_governor"},
    {"candidate_source_exists": "yes"},
    {"independently_verified_qualified_demand": 1},
    {"message_claims": [reply("BUYER_REVIEW_OPEN", "a")] * 2},
    {"message_claims": [reply("AUTO_SEND_APPROVED", "a")]},
    {"message_claims": [reply("BUYER_REVIEW_OPEN", "a"),
                        {"message_ref": "injection", "received_at": NOW.isoformat(),
                         "claim": "BUYER_REVIEW_OPEN", "email": "x@example.com"}]},
    {"message_claims": [{"message_ref": "x",
                         "received_at": "2026-10-24T03:00:00Z",
                         "claim": "BUYER_REVIEW_OPEN"}]},
])
def test_untrusted_offers_fail_closed(changes):
    with pytest.raises(ValueError):
        review_buyer_offer(buyer(**changes), as_of=NOW)


def test_forecast_and_received_cash_injection_rejected():
    row = buyer()
    row["recognized_revenue_cents"] = 500000
    with pytest.raises(ValueError, match="exact"):
        review_buyer_offer(row, as_of=NOW)


def test_no_fake_canonical_source_flag_unlocks():
    r = review_buyer_offer(buyer(
        candidate_source_exists=True,
        independently_verified_qualified_demand=True,
    ), as_of=NOW)
    assert r["genuine_enquiries_independently_verified"] is False
    assert r["source_eligibility_independently_verified"] is False
    assert "AUTHENTICATED_CANONICAL_SOURCE_AND_BUYER_JOIN_NOT_ESTABLISHED" in r["blockers"]


def test_duplicate_buyer_key_rejected():
    with pytest.raises(ValueError, match="duplicate buyer"):
        review_buyer_offer_portfolio([buyer(), buyer()], as_of=NOW)


def test_empty_buyer_list_is_not_verified_zero():
    result = review_buyer_offer_portfolio([], as_of=NOW)
    assert result["reviewed_buyers"] == []
    assert result["verified_customer_enquiries"] is None
    assert result["verified_settled_revenue_cents"] is None


def test_unknown_claim_or_future_reply_does_not_authorize():
    with pytest.raises(ValueError, match="future"):
        review_buyer_offer(buyer(message_claims=[
            {"message_ref":"future", "received_at":"2026-10-25T00:00:00Z",
             "claim":"BUYER_REVIEW_OPEN"}]), as_of=NOW)
