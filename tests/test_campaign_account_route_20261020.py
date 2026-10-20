"""Owner-authenticated account route tests. All inputs are test fixtures."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.campaign_intelligence import (
    AccountIntelligenceContext, CampaignIntelligenceHeld,
    TrustedAccountRoute, TrustedBuyingMember, TrustedWarmIntroduction,
    TrustedAccountTouch, TrustedCampaignSignal,
    review_account_buying_route,
)

NOW = datetime(2026, 10, 20, 10, tzinfo=timezone.utc)
ACC = "b" * 32
TENANT = "tenant_empireai"
CAMPAIGN = "campaign_" + "a" * 24


def context(**kw):
    return replace(AccountIntelligenceContext(
        tenant_ref=TENANT, account_key=ACC, market_scope="GB:solar:buyers",
        campaign_id=CAMPAIGN, canonical_account_verified=True,
        suppression_clear=True, inbound_response_basis_verified=True,
        marketing_contact_basis_verified=True, offer_evidence_current=True,
    ), **kw)


def member(n="c", *, role="economic_buyer", contact_verified=True, **kw):
    return replace(TrustedBuyingMember(
        person_key=n*32, account_key=ACC, tenant_ref=TENANT,
        decision_role=role, observed_at=NOW,
        canonical_person_link_verified=True,
        contact_route_verified=contact_verified,
        source_provenance_verified=True,
    ), **kw)


def intro(*, kind="partner_intro", permitted=True, **kw):
    return replace(TrustedWarmIntroduction(
        referrer_key="d"*32, account_key=ACC, tenant_ref=TENANT,
        kind=kind, observed_at=NOW,
        relationship_verified=True,
        introduction_permission_verified=permitted, strength="strong",
    ), **kw)


def touch(*, days_ago=5, **kw):
    return replace(TrustedAccountTouch(
        touch_key="e"*32, account_key=ACC, tenant_ref=TENANT,
        observed_at=NOW-timedelta(days=days_ago),
        canonical_delivery_receipt_verified=True,
    ), **kw)


def signal(kind="email_link_clicked", **kw):
    sources = {
        "email_link_clicked": "first_party_click_gateway",
        "pricing_request": "canonical_crm",
        "optin_enquiry": "canonical_crm",
        "unsubscribe": "canonical_crm",
        "verified_paying_customer": "canonical_commercial_ledger",
    }
    return replace(TrustedCampaignSignal(
        event_id="f"*32, tenant_ref=TENANT, account_key=ACC,
        market_scope="GB:solar:buyers", campaign_id=CAMPAIGN, kind=kind,
        source=sources[kind], observed_at=NOW,
        source_receipt_verified=True, canonical_account_link_verified=True,
        purpose_lawfulness_verified=True,
    ), **kw)


def route(*, members=None, intros=(), touches=(), **kw):
    return replace(TrustedAccountRoute(
        context=context(), buying_members=tuple(members if members is not None else (member(),)),
        warm_introductions=tuple(intros),
        contact_history=tuple(touches), contact_history_complete=True,
        market_and_buyer_fit_verified=True,
        offer_fulfilment_verified=True, marketing_channel_lawfulness_verified=True,
    ), **kw)


def review(r=None, signals=()):
    return review_account_buying_route(r or route(), verified_signals=signals, now=NOW)


def test_verified_buyer_route_plans_one_human_review_never_a_send():
    report = review()
    assert report["recommended_play"] == "PREPARE_ONE_CONTACT_OFFER_FOR_OWNER_REVIEW"
    assert report["observed_verified_buying_members"] == 1
    assert report["selected_contact_role"] == "economic_buyer"
    assert report["verified_contact_route_count"] == 1
    for flag in ("outbound_sent", "campaign_enrolled",
                 "personal_data_exposed", "inferred_buyer_identity_or_demand"):
        assert report[flag] is False
    dump = json.dumps(report)
    assert ACC not in dump and TENANT not in dump and "c"*32 not in dump


def test_selects_verified_functional_over_uncontactable_economic_buyer():
    r = route(members=[member("c", role="economic_buyer", contact_verified=False),
                       member("f", role="functional_buyer", contact_verified=True)])
    report = review(r)
    assert report["selected_contact_role"] == "functional_buyer"
    assert report["verified_contact_route_count"] == 1


def test_verified_and_permitted_warm_intro_beats_cold_first_touch():
    report = review(route(intros=[intro()]))
    assert report["recommended_play"] == "PREPARE_VERIFIED_WARM_INTRO_FOR_OWNER_REVIEW"
    assert report["preferred_introduction_type"] == "partner_intro"
    assert report["verified_warm_introduction_available"] is True
    report = review(route(intros=[intro(permitted=False)]))
    assert report["preferred_introduction_type"] is None
    assert report["recommended_play"] == "PREPARE_ONE_CONTACT_OFFER_FOR_OWNER_REVIEW"


def test_click_only_does_not_escalate_to_sales_response():
    report = review(signals=[signal()])
    assert report["account_signal_action"] == "INTERNAL_RESEARCH_ONLY"
    assert report["recommended_play"] == "PREPARE_ONE_CONTACT_OFFER_FOR_OWNER_REVIEW"
    assert report["outbound_sent"] is False


def test_inbound_pricing_request_routes_same_day_without_marketing_permission():
    r = route(context=context(marketing_contact_basis_verified=False),
              marketing_channel_lawfulness_verified=False)
    report = review(r, [signal("pricing_request")])
    assert report["recommended_play"] == "SAME_BUSINESS_DAY_EXISTING_INBOUND_REVIEW"
    assert report["outbound_sent"] is False


def test_no_inbound_response_basis_blocks_reply_even_on_explicit_request():
    r = route(context=context(inbound_response_basis_verified=False))
    assert review(r, [signal("optin_enquiry")])["recommended_play"] == "HOLD_INBOUND_REPLY_BASIS"


def test_existing_customer_not_retreated_as_new_cold_prospect():
    assert review(signals=[signal("verified_paying_customer")])[
        "recommended_play"] == "EXISTING_CUSTOMER_HUMAN_REVIEW"


def test_global_suppression_and_unsubscribe_beat_every_positive_signal():
    r = route(context=context(suppression_clear=False))
    assert review(r)["recommended_play"] == "STOP_AND_SUPPRESS"
    assert review(signals=[signal("unsubscribe")])["recommended_play"] == "STOP_AND_SUPPRESS"


def test_global_company_cooldown_blocks_another_marketing_message():
    assert review(route(touches=[touch()]))["recommended_play"] == "HOLD_30_DAY_COMPANY_COOLDOWN"
    assert review(route(touches=[touch(days_ago=31)]))["recommended_play"] == (
        "PREPARE_ONE_CONTACT_OFFER_FOR_OWNER_REVIEW"
    )
    assert review(route(contact_history_complete=False))[
        "recommended_play"] == "HOLD_INCOMPLETE_GLOBAL_CONTACT_HISTORY"


def test_missing_marketing_lawful_basis_and_offer_proof_hold():
    assert review(route(marketing_channel_lawfulness_verified=False))[
        "recommended_play"] == "HOLD_MARKETING_CHANNEL_PERMISSION"
    assert review(route(context=context(marketing_contact_basis_verified=False)))[
        "recommended_play"] == "HOLD_MARKETING_CHANNEL_PERMISSION"
    assert review(route(offer_fulfilment_verified=False))[
        "recommended_play"] == "VERIFY_COMMERCIAL_OFFER_PROOF"
    assert review(route(market_and_buyer_fit_verified=False))[
        "recommended_play"] == "RESEARCH_ACCOUNT_MARKET_FIT"


def test_unverified_canonical_person_and_cross_tenant_are_never_selected():
    with pytest.raises(CampaignIntelligenceHeld, match="PERSON_LINK_UNVERIFIED"):
        review(route(members=[member(canonical_person_link_verified=False)]))
    with pytest.raises(CampaignIntelligenceHeld, match="CROSS_ACCOUNT"):
        review(route(members=[member(account_key="h"*32)]))


def test_contact_history_rejects_fake_or_conflicting_events():
    with pytest.raises(CampaignIntelligenceHeld, match="SOURCE_UNVERIFIED"):
        review(route(touches=[touch(canonical_delivery_receipt_verified=False)]))
    with pytest.raises(CampaignIntelligenceHeld, match="DUPLICATE_CONTACT"):
        review(route(touches=[touch(), touch()]))
    with pytest.raises(CampaignIntelligenceHeld, match="FUTURE"):
        review(route(touches=[touch(observed_at=NOW+timedelta(hours=1))]))


def test_unverified_warm_path_cannot_be_selected_or_inferred():
    with pytest.raises(CampaignIntelligenceHeld, match="PROVENANCE"):
        review(route(intros=[intro(relationship_verified=False)]))
    with pytest.raises(CampaignIntelligenceHeld, match="STALE"):
        review(route(intros=[intro(observed_at=NOW-timedelta(days=91))]))
    with pytest.raises(CampaignIntelligenceHeld, match="DUPLICATE"):
        review(route(intros=[intro(), intro()]))


def test_unknown_role_future_people_and_overlong_lists_rejected():
    for person in (member(role="unapproved_role"),
                   member(observed_at=NOW+timedelta(seconds=2))):
        with pytest.raises(CampaignIntelligenceHeld):
            review(route(members=[person]))
    with pytest.raises(CampaignIntelligenceHeld, match="BOUNDED"):
        review(route(members=[member("g")] * 31))


def test_without_verified_buyer_contact_only_research_is_allowed():
    assert review(route(members=[]))["recommended_play"] == "RESEARCH_VERIFIED_BUYING_COMMITTEE"


def test_aggregate_sales_director_portfolio_tracks_real_evidence_without_disclosing_contacts():
    from empire_os.campaign_intelligence import review_account_route_portfolio
    second = route(
        context=context(account_key="f"*32),
        members=[member("f", account_key="f"*32)],
        intros=[intro(account_key="f"*32)],
    )
    result = review_account_route_portfolio([
        (route(), [signal("pricing_request")]),
        (second, ()),
    ], now=NOW)
    assert result["accounts_reviewed"] == 2
    assert result["commercial_plays"]["SAME_BUSINESS_DAY_EXISTING_INBOUND_REVIEW"] == 1
    assert result["commercial_plays"]["PREPARE_VERIFIED_WARM_INTRO_FOR_OWNER_REVIEW"] == 1
    assert result["verified_contact_routes_reviewed"] == 2
    assert result["sent_messages"] == 0
    dump = json.dumps(result)
    assert ACC not in dump and "f"*32 not in dump and TENANT not in dump


def test_portfolio_prevents_duplicate_same_account_and_overly_large_batches():
    from empire_os.campaign_intelligence import review_account_route_portfolio
    with pytest.raises(CampaignIntelligenceHeld, match="DUPLICATE"):
        review_account_route_portfolio([(route(), ()), (route(), ())], now=NOW)
    with pytest.raises(CampaignIntelligenceHeld, match="LIMIT"):
        review_account_route_portfolio([(route(), ())] * 501, now=NOW)


def test_main_existing_review_api_can_take_canonical_account_route_projections():
    from scripts.review_tam_full_funnel_strategy_20261020 import (
        review_authenticated_campaign_intelligence,
    )
    report = review_authenticated_campaign_intelligence(
        now=NOW,
        account_route_packets=[(route(), [signal("pricing_request")])],
    )
    assert report["account_intelligence"] is None
    assert report["verified_customer_experiment"] is None
    assert report["account_buying_committee_routes"]["accounts_reviewed"] == 1
    assert report["account_buying_committee_routes"]["commercial_plays"][
        "SAME_BUSINESS_DAY_EXISTING_INBOUND_REVIEW"
    ] == 1
    assert report["live_recipient_contact_or_messages"] is False
