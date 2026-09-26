from datetime import datetime, timezone

import pytest

from empire_os.outreach_account_strategy import (
    build_buying_committee,
    choose_introduction_path,
    evaluate_contact_fatigue,
)
from empire_os.outreach_intelligence import (
    build_outreach_packet,
    choose_play_type,
    choose_trigger,
    reply_next_action,
)


NOW = datetime(2026, 9, 20, 0, 0, tzinfo=timezone.utc)


def base_account():
    return {
        "account_id": "acct-1",
        "business_name": "Northstar Roofing",
        "contact_name": "Jane Smith",
        "contact_title": "Owner",
    }


def base_contact_plan():
    return {
        "outreach_ready": True,
        "preferred_email": "jane@northstar.example",
    }


def base_context():
    return {
        "outreach_ready": True,
        "bound_to_decision_maker": True,
        "suppressed": False,
        "offer_key": "territory-seat",
        "corridor_key": "roofing:manchester:exclusive",
        "territory": "Manchester",
        "campaign_key": "buyer-growth-q4",
    }


def signals():
    return [
        {
            "signal_type": "market_demand",
            "summary": "Observed buyer demand is rising in the Manchester roofing corridor.",
            "source": "market-intelligence",
            "observed_at": "2026-09-19T20:00:00+00:00",
            "confidence": 0.88,
            "evidence_ref": "market:roofing:manchester:20260919",
        }
    ]


def test_packet_is_observe_only_and_ties_to_predicted_economics():
    packet = build_outreach_packet(
        account=base_account(),
        contact_plan=base_contact_plan(),
        context=base_context(),
        signals=signals(),
        proof_refs=["proof:buyer-capacity:1"],
        predicted_economics={
            "prediction_ref": "pred-1",
            "expected_revenue_cents": 500000,
            "expected_cost_cents": 125000,
            "confidence": 0.74,
        },
        now=NOW,
    )
    assert packet["review_ready"] is True
    assert packet["send_enabled"] is False
    assert packet["execution_authority"] == "none"
    assert packet["predicted_economics"]["expected_gross_profit_cents"] == 375000
    assert packet["predicted_economics"]["actual_revenue"] is False
    assert packet["trigger"]["signal_type"] == "market_demand"
    assert packet["sequence"][0]["channel"] == "email"
    assert all(step["execution_authority"] == "none" for step in packet["sequence"])


def test_missing_trigger_and_verified_path_fail_closed():
    packet = build_outreach_packet(
        account=base_account(),
        contact_plan={"outreach_ready": False, "preferred_email": "guess@example.com"},
        context={**base_context(), "outreach_ready": False},
        signals=[],
        proof_refs=[],
        now=NOW,
    )
    assert packet["review_ready"] is False
    assert "no_verified_contact_or_intro_path" in packet["blockers"]
    assert "no_fresh_evidence_backed_trigger" in packet["blockers"]
    assert "no_proof_evidence" in packet["blockers"]
    assert "outreach_readiness_unverified" in packet["blockers"]


def test_stale_or_future_signal_is_not_promoted():
    trigger = choose_trigger(
        [
            {
                "signal_type": "permit",
                "summary": "Old permit",
                "source": "permit-radar",
                "observed_at": "2026-01-01T00:00:00+00:00",
                "confidence": 0.99,
                "evidence_ref": "permit:old",
            },
            {
                "signal_type": "storm",
                "summary": "Future storm record",
                "source": "storm-radar",
                "observed_at": "2026-09-21T00:00:00+00:00",
                "confidence": 0.99,
                "evidence_ref": "storm:future",
            },
        ],
        now=NOW,
        max_age_hours=24 * 30,
    )
    assert trigger is None


def test_verified_company_phone_never_becomes_person_bound_primary():
    packet = build_outreach_packet(
        account=base_account(),
        contact_plan={"outreach_ready": False},
        context=base_context(),
        signals=signals(),
        channel_evidence=[
            {
                "channel": "voice",
                "value": "+441204555555",
                "verified": True,
                "person_bound": False,
                "source": "official_business_phone",
            }
        ],
        proof_refs=["proof:1"],
        now=NOW,
    )
    assert packet["channel_plan"]["primary"] is None
    assert packet["channel_plan"]["company_fallbacks"][0]["channel"] == "voice"
    assert packet["review_ready"] is False
    assert packet["voice_dial_enabled"] is False


def test_lifecycle_play_selection():
    assert choose_play_type({"existing_buyer": True, "renewal_due": True}) == "renewal"
    assert choose_play_type({
        "existing_buyer": True,
        "territory_expansion_ready": True,
    }) == "territory_expansion"
    with pytest.raises(ValueError):
        choose_play_type({"play_type": "spam_everywhere"})


def test_reply_actions_are_never_auto_send():
    assert reply_next_action("positive")["recommended_action"] == "closer_review"
    assert reply_next_action("unsubscribe")["recommended_action"] == "suppress_and_close"
    assert reply_next_action("objection")["automatic_send"] is False


def test_buying_committee_ranks_economic_buyer_without_inventing_people():
    result = build_buying_committee([
        {
            "person_id": "p2",
            "name": "Alex Jones",
            "title": "Head of Sales",
            "decision_role": "functional_buyer",
            "contact_verified": True,
            "evidence_ref": "person:p2",
        },
        {
            "person_id": "p1",
            "name": "Jane Smith",
            "title": "Owner",
            "decision_role": "economic_buyer",
            "contact_verified": False,
            "evidence_ref": "person:p1",
        },
        {"person_id": "", "name": "Mystery Person", "evidence_ref": ""},
    ])
    assert result["primary"]["person_id"] == "p1"
    assert result["observed_member_count"] == 2
    assert result["multi_thread_candidate"] is True
    assert result["invented_members"] == 0


def test_verified_warm_intro_can_be_preferred_entry_path():
    intro = choose_introduction_path([
        {
            "kind": "partner_intro",
            "referrer": "Partner Alpha",
            "verified": True,
            "relationship_strength": "strong",
            "evidence_ref": "partner:alpha:relationship",
        }
    ])
    assert intro["kind"] == "partner_intro"

    packet = build_outreach_packet(
        account=base_account(),
        contact_plan={"outreach_ready": False},
        context={
            **base_context(),
            "introduction_paths": [{
                "kind": "partner_intro",
                "referrer": "Partner Alpha",
                "verified": True,
                "relationship_strength": "strong",
                "evidence_ref": "partner:alpha:relationship",
            }],
        },
        signals=signals(),
        proof_refs=["proof:1"],
        now=NOW,
    )
    assert packet["entry_strategy"] == "verified_warm_intro_review"
    assert packet["sequence"][0]["channel"] == "partner_intro"
    assert "no_verified_contact_or_intro_path" not in packet["blockers"]


def test_contact_fatigue_blocks_repeated_account_touching():
    fatigue = evaluate_contact_fatigue(
        [
            {"occurred_at": "2026-09-19T12:00:00+00:00"},
            {"occurred_at": "2026-09-16T12:00:00+00:00"},
            {"occurred_at": "2026-09-10T12:00:00+00:00"},
            {"occurred_at": "2026-09-05T12:00:00+00:00"},
        ],
        now=NOW,
    )
    assert fatigue["blocked"] is True
    assert "max_30d_touch_count_reached" in fatigue["blockers"]
    assert "contact_cooldown_active" in fatigue["blockers"]

    packet = build_outreach_packet(
        account=base_account(),
        contact_plan=base_contact_plan(),
        context={
            **base_context(),
            "prior_touches": [
                {"occurred_at": "2026-09-19T12:00:00+00:00"},
                {"occurred_at": "2026-09-16T12:00:00+00:00"},
                {"occurred_at": "2026-09-10T12:00:00+00:00"},
                {"occurred_at": "2026-09-05T12:00:00+00:00"},
            ],
        },
        signals=signals(),
        proof_refs=["proof:1"],
        now=NOW,
    )
    assert packet["review_ready"] is False
    assert "max_30d_touch_count_reached" in packet["blockers"]
