"""Adapter integration tests: data here are fixtures, never real CRM records."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import pytest

from empire_os.campaign_intelligence import (
    AccountIntelligenceContext, CampaignIntelligenceHeld,
    TrustedAccountRoute, TrustedBuyingMember, TrustedWarmIntroduction,
    TrustedCampaignSignal, TrustedJourneyProjection,
    review_adaptive_buyer_journey, review_adaptive_buyer_journey_portfolio,
)
from empire_os.revenue_crm_channel_evidence import (
    TrustedChannelEvidence, VERIFIED_SOURCE,
)

NOW = datetime(2026, 10, 20, 10, tzinfo=timezone.utc)
ACCOUNT = "a" * 32
TENANT = "tenant_empireai"
CRM_TENANT = "11223344-2233-4433-8833-223344556677"
PROSPECT = "11223344-2233-4433-8833-223344556688"
CAMPAIGN = "campaign_" + "a" * 24


def context(**kw):
    return replace(AccountIntelligenceContext(
        tenant_ref=TENANT, account_key=ACCOUNT, market_scope="GB:solar:buyers",
        campaign_id=CAMPAIGN, canonical_account_verified=True,
        suppression_clear=True, inbound_response_basis_verified=True,
        marketing_contact_basis_verified=True, offer_evidence_current=True,
    ), **kw)


def member():
    return TrustedBuyingMember(
        person_key="b" * 32, account_key=ACCOUNT, tenant_ref=TENANT,
        decision_role="economic_buyer", observed_at=NOW,
        canonical_person_link_verified=True, contact_route_verified=True,
        source_provenance_verified=True,
    )


def intro():
    return TrustedWarmIntroduction(
        referrer_key="c" * 32, account_key=ACCOUNT, tenant_ref=TENANT,
        kind="partner_intro", observed_at=NOW,
        relationship_verified=True, introduction_permission_verified=True,
        strength="strong",
    )


def route(*, ctx=None, intros=()):
    return TrustedAccountRoute(
        context=ctx or context(), buying_members=(member(),),
        warm_introductions=tuple(intros), contact_history=(),
        contact_history_complete=True, market_and_buyer_fit_verified=True,
        offer_fulfilment_verified=True, marketing_channel_lawfulness_verified=True,
    )


def crm(**kw):
    return {
        "tenant_id": CRM_TENANT, "prospect_id": PROSPECT,
        "niche": "solar", "prospect_status": "research",
        **kw,
    }


def receipt(channel="email", **kw):
    return replace(TrustedChannelEvidence(
        tenant_id=CRM_TENANT, prospect_id=PROSPECT,
        channel=channel, identity_bound=True,
        consent_state="verified_opt_in",
        suppression_state="not_found",
        consent_evidence_ref="canonical:consent:receipt001",
        suppression_evidence_ref="canonical:suppression:receipt001",
        observed_at=NOW, source=VERIFIED_SOURCE,
    ), **kw)


def projection(*, row=None, receipts=(), buyer_route=None, **kw):
    return replace(TrustedJourneyProjection(
        account_route=buyer_route or route(),
        crm_row=crm() if row is None else row,
        canonical_account_to_crm_binding_verified=True,
        crm_snapshot_observed_at=NOW,
        channel_receipts=tuple(receipts),
    ), **kw)


def signal(kind="pricing_request"):
    return TrustedCampaignSignal(
        event_id="d" * 32, tenant_ref=TENANT, account_key=ACCOUNT,
        market_scope="GB:solar:buyers", campaign_id=CAMPAIGN,
        kind=kind,
        source={
            "pricing_request": "canonical_crm",
            "email_link_clicked": "first_party_click_gateway",
            "unsubscribe": "canonical_crm",
            "verified_paying_customer": "canonical_commercial_ledger",
        }[kind],
        observed_at=NOW, source_receipt_verified=True,
        canonical_account_link_verified=True, purpose_lawfulness_verified=True,
    )


def review(packet=None, *, signals=()):
    return review_adaptive_buyer_journey(
        packet or projection(), verified_signals=signals, now=NOW,
    )


def test_unknown_channel_consent_blocks_proactive_email_without_guessing():
    result = review()
    assert result["recommended_play"] == "HOLD_CHANNEL_EVIDENCE"
    assert result["preferred_human_channel_review"] is None
    assert result["channel_review_states"] == {
        "email": "HOLD_MISSING_EVIDENCE",
        "sms": "HOLD_MISSING_EVIDENCE",
        "web_push": "HOLD_MISSING_EVIDENCE",
    }
    assert result["editorial_interest_hypothesis_not_subscription"] == "industry_opportunity_signals"
    assert result["send_authorized"] is False
    assert result["auto_sequence_enabled"] is False
    assert PROSPECT not in json.dumps(result)
    assert ACCOUNT not in json.dumps(result)


def test_verified_email_optin_is_internal_offer_review_not_sender_authority():
    result = review(projection(receipts=(receipt(),)))
    assert result["recommended_play"] == "OFFER_EXPERIMENT_OWNER_REVIEW"
    assert result["preferred_human_channel_review"] == "email"
    assert result["channel_review_states"]["email"] == "REVIEW_ONLY_EVIDENCE_PRESENT"
    assert result["send_authorized"] is False
    assert result["auto_paid_retargeting"] is False


def test_channel_specific_optout_never_selects_that_channel():
    result = review(projection(receipts=(
        receipt("email", consent_state="opted_out"),
        receipt("sms"),
    )))
    assert result["preferred_human_channel_review"] == "sms"
    assert result["channel_review_states"]["email"] == "BLOCKED_BY_EVIDENCE"
    assert result["recommended_play"] == "OFFER_EXPERIMENT_OWNER_REVIEW"
    assert result["send_authorized"] is False


def test_expired_permission_and_missing_suppression_proof_are_held():
    for evid in (
        receipt(observed_at=NOW-timedelta(days=2)),
        receipt(suppression_evidence_ref=None),
        receipt(identity_bound=False),
    ):
        out = review(projection(receipts=(evid,)))
        assert out["preferred_human_channel_review"] is None
        assert out["recommended_play"] == "HOLD_CHANNEL_EVIDENCE"


def test_crm_contact_hold_supersedes_all_positive_signals_and_channels():
    out = review(projection(row=crm(prospect_status="unsubscribed"),
                            receipts=(receipt(),)), signals=(signal(),))
    assert out["recommended_play"] == "STOP_CONTACT"
    assert out["timing"] == "NO_EXTERNAL_CONTACT"


def test_verified_account_suppression_stops_marketing_even_with_optin():
    out = review(projection(
        buyer_route=route(ctx=context(suppression_clear=False)),
        receipts=(receipt(),),
    ))
    assert out["recommended_play"] == "STOP_CONTACT"


def test_real_crm_fulfilment_stage_beats_new_marketing_offer():
    out = review(projection(row=crm(
        fulfilment_order_id="canonical_order_a",
        fulfilment_state="accepted",
    ), receipts=(receipt(),)))
    assert out["crm_journey_stage"] == "fulfilment_review"
    assert out["recommended_play"] == "FULFILMENT_OWNER_REVIEW"
    assert out["send_authorized"] is False


def test_crm_proposal_and_payment_stage_keep_commercial_lifecycle():
    proposal = review(projection(row=crm(
        closer_case_id="canonical_case_a",
        closer_state="proposal_ready",
    )))
    assert proposal["recommended_play"] == "PROPOSAL_AND_TERMS_REVIEW"
    payment = review(projection(row=crm(
        closer_case_id="canonical_case_a",
        closer_state="awaiting_payment",
    )))
    assert payment["recommended_play"] == "PAYMENT_STATUS_OWNER_REVIEW"
    assert payment["crm_mutation"] is False


def test_explicit_buyer_inbound_triggers_review_even_without_marketing_subscription():
    buyer = route(ctx=context(marketing_contact_basis_verified=False))
    out = review(
        projection(buyer_route=buyer, receipts=()),
        signals=(signal("pricing_request"),),
    )
    assert out["recommended_play"] == "SAME_DAY_BUYER_CONVERSATION_REVIEW"
    assert out["timing"] == "SAME_BUSINESS_DAY"
    assert out["send_authorized"] is False


def test_click_cannot_upgrade_evidence_or_authorize_campaigns():
    buyer = route(ctx=context(marketing_contact_basis_verified=False))
    out = review(projection(buyer_route=buyer), signals=(signal("email_link_clicked"),))
    assert out["recommended_play"] == "INTERNAL_ACCOUNT_RESEARCH"
    assert out["preferred_human_channel_review"] is None
    assert out["send_authorized"] is False


def test_verified_partner_intro_remains_operator_only_even_without_email_optin():
    out = review(projection(buyer_route=route(intros=(intro(),))))
    assert out["recommended_play"] == "WARM_INTRO_OWNER_REVIEW"
    assert out["preferred_human_channel_review"] is None
    assert out["send_authorized"] is False


def test_existing_paying_customer_is_not_treated_as_new_acquisition():
    out = review(signals=(signal("verified_paying_customer"),))
    assert out["recommended_play"] == "EXISTING_CUSTOMER_REVIEW"


def test_untrusted_account_to_crm_binding_fails_closed():
    out = review(projection(canonical_account_to_crm_binding_verified=False,
                            receipts=(receipt(),)))
    assert out["recommended_play"] == "HOLD_CANONICAL_SOURCE"
    assert out["crm_journey_stage"] is None
    assert out["preferred_human_channel_review"] is None
    assert out["send_authorized"] is False


def test_cross_tenant_channel_receipt_is_rejected_not_silently_ignored():
    with pytest.raises(CampaignIntelligenceHeld, match="IDENTITY_OR_EVIDENCE"):
        review(projection(receipts=(
            receipt(tenant_id="11223344-2233-4433-8833-223344556699"),
        )))


def test_duplicate_channel_receipts_and_invalid_type_rejected():
    with pytest.raises(CampaignIntelligenceHeld, match="DUPLICATE"):
        review(projection(receipts=(receipt(), receipt())))
    with pytest.raises(CampaignIntelligenceHeld, match="UNTRUSTED"):
        review(projection(receipts=("email",)))


def test_canonical_crm_snapshot_must_be_current_not_future():
    for dt in (NOW-timedelta(hours=25), NOW+timedelta(hours=1)):
        with pytest.raises(CampaignIntelligenceHeld, match="SNAPSHOT_STALE"):
            review(projection(crm_snapshot_observed_at=dt))


def test_only_matching_canonical_uuid_fields_accepted():
    with pytest.raises(CampaignIntelligenceHeld, match="CRM_ID_INVALID"):
        review(projection(row=crm(tenant_id="tenant_somebodyelse")))


def test_portfolio_aggregates_plays_without_exposing_people_or_identifiers():
    first = projection(receipts=(receipt(),))
    second = projection(
        buyer_route=replace(
            route(ctx=context(account_key="e"*32)),
            buying_members=(replace(member(), account_key="e"*32),),
        ),
        row=crm(prospect_id="11223344-2233-4433-8833-223344556699"),
        receipts=(),
    )
    out = review_adaptive_buyer_journey_portfolio(
        [(first, ()), (second, ())], now=NOW,
    )
    assert out["accounts_reviewed"] == 2
    assert out["recommended_human_play_counts"]["OFFER_EXPERIMENT_OWNER_REVIEW"] == 1
    assert out["recommended_human_play_counts"]["HOLD_CHANNEL_EVIDENCE"] == 1
    assert out["messages_scheduled"] == 0
    assert out["contact_identity_records_exposed"] == 0
    assert PROSPECT not in json.dumps(out)


def test_portfolio_cannot_contain_duplicate_campaign_account():
    packet = projection()
    with pytest.raises(CampaignIntelligenceHeld, match="DUPLICATE"):
        review_adaptive_buyer_journey_portfolio(
            [(packet, ()), (packet, ())], now=NOW,
        )


def test_verified_engaged_crm_conversation_routes_to_sales_owner_not_marketing():
    engaged = crm(
        conversation_id="canonical_conversation_a",
        conversation_state="engaged",
        conversation_updated_at=NOW-timedelta(hours=80),
    )
    out = review(projection(row=engaged))
    assert out["crm_journey_stage"] == "engaged_conversation_review"
    assert out["crm_stale_conversation_review"] is True
    assert out["recommended_play"] == "SAME_DAY_BUYER_CONVERSATION_REVIEW"
    assert out["preferred_human_channel_review"] is None
    assert out["send_authorized"] is False


def test_engaged_conversation_without_verified_reply_basis_is_held():
    engaged = crm(
        conversation_id="canonical_conversation_a",
        conversation_state="engaged",
    )
    out = review(projection(
        row=engaged,
        buyer_route=route(ctx=context(inbound_response_basis_verified=False)),
    ))
    assert out["recommended_play"] == "HOLD_INBOUND_RESPONSE_BASIS"
    assert out["timing"] == "NO_EXTERNAL_CONTACT"


def test_direct_request_without_verified_response_basis_is_held():
    out = review(
        projection(buyer_route=route(
            ctx=context(inbound_response_basis_verified=False),
        )),
        signals=(signal("pricing_request"),),
    )
    assert out["recommended_play"] == "HOLD_INBOUND_RESPONSE_BASIS"
    assert out["send_authorized"] is False


def test_same_crm_prospect_cannot_be_double_counted_between_account_routes():
    first = projection()
    second = projection(buyer_route=replace(
        route(ctx=context(account_key="e"*32)),
        buying_members=(replace(member(), account_key="e"*32),),
    ))
    with pytest.raises(CampaignIntelligenceHeld, match="DUPLICATE_CANONICAL_CRM"):
        review_adaptive_buyer_journey_portfolio(
            [(first, ()), (second, ())], now=NOW,
        )


def test_existing_full_funnel_entry_reuses_adaptive_journeys_without_live_activation():
    from scripts.review_tam_full_funnel_strategy_20261020 import (
        review_authenticated_campaign_intelligence,
    )
    packet = projection(receipts=(receipt(),))
    out = review_authenticated_campaign_intelligence(
        now=NOW, adaptive_journey_packets=((packet, ()),),
    )
    assert out["adaptive_buyer_journeys"]["accounts_reviewed"] == 1
    assert out["adaptive_buyer_journeys"]["recommended_human_play_counts"][
        "OFFER_EXPERIMENT_OWNER_REVIEW"] == 1
    assert out["adaptive_buyer_journeys"]["messages_scheduled"] == 0
    assert out["multiwave_campaign_learning"] is None
    assert out["live_recipient_contact_or_messages"] is False


def test_no_source_from_owner_does_not_imply_zero_adaptive_buyers():
    from scripts.review_tam_full_funnel_strategy_20261020 import (
        review_authenticated_campaign_intelligence,
    )
    out = review_authenticated_campaign_intelligence(now=NOW)
    assert out["adaptive_buyer_journeys"] is None
    assert out["database_writes"] is False
