"""Tests use explicitly marked fixtures; no fabricated production leads."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.campaign_intelligence import (
    AccountIntelligenceContext, TrustedCampaignSignal, CampaignIntelligenceHeld,
    review_account_intelligence, review_private_account_portfolio,
    TrustedArmOutcome, evaluate_real_customer_experiment,
)

NOW = datetime(2026, 10, 20, 10, tzinfo=timezone.utc)
CID = "campaign_" + "a" * 24
ACCOUNT = "b" * 32
TENANT = "tenant_empireai"


def context(**kw):
    x = AccountIntelligenceContext(
        tenant_ref=TENANT, account_key=ACCOUNT, market_scope="GB:solar:buyers",
        campaign_id=CID, canonical_account_verified=True,
        suppression_clear=True, inbound_response_basis_verified=True,
        marketing_contact_basis_verified=False, offer_evidence_current=True,
    )
    return replace(x, **kw)


def signal(kind="email_link_clicked", *, idx=1, when=NOW, **changes):
    sources = {
        "email_link_clicked": "first_party_click_gateway",
        "email_delivered": "email_provider",
        "consented_site_visit": "first_party_site",
        "consented_offer_page_visit": "first_party_site",
        "verified_public_procurement": "verified_public_intent_source",
        "public_company_growth_signal": "verified_public_intent_source",
        "optin_enquiry": "canonical_crm",
        "verified_social_inbound_enquiry": "canonical_crm",
        "demo_request": "canonical_crm",
        "direct_buyer_question": "canonical_crm",
        "pricing_request": "canonical_crm",
        "meeting_booked": "canonical_crm",
        "terms_accepted": "canonical_crm",
        "verified_paying_customer": "canonical_commercial_ledger",
        "unsubscribe": "canonical_crm",
        "hard_bounce": "email_provider",
        "explicit_not_interested": "canonical_crm",
    }
    return replace(TrustedCampaignSignal(
        event_id=f"{idx:032x}", tenant_ref=TENANT, account_key=ACCOUNT,
        market_scope="GB:solar:buyers", campaign_id=CID,
        kind=kind, source=sources[kind], observed_at=when,
        source_receipt_verified=True, canonical_account_link_verified=True,
        purpose_lawfulness_verified=True,
    ), **changes)


def review(*events, ctx=None):
    return review_account_intelligence(ctx or context(), events, now=NOW)


def test_weak_click_and_website_sessions_cannot_be_promoted_into_sales_intent():
    result = review(signal(idx=1), signal(idx=2, when=NOW-timedelta(hours=4)),
                    signal("consented_site_visit", idx=3))
    assert result["action"] == "INTERNAL_RESEARCH_ONLY"
    assert result["signal_strength_points_not_probability"] > 0
    assert result["marketing_contact_eligible_from_signals"] is False
    assert result["human_identity_inferred_from_click"] is False
    for k in ("auto_send", "auto_retarget", "auto_budget", "database_writes"):
        assert result[k] is False
    assert ACCOUNT not in json.dumps(result)
    assert CID not in json.dumps(result)
    assert "person@example.com" not in json.dumps(result)


def test_100_clicks_same_day_cannot_spam_intent_score():
    report = review(*[signal(idx=i+1) for i in range(100)])
    assert report["signal_strength_points_not_probability"] == 1
    assert report["action"] == "INTERNAL_RESEARCH_ONLY"


def test_verified_direct_enquiry_gets_same_business_day_review_only():
    report = review(signal("optin_enquiry", idx=1))
    assert report["action"] == "SAME_BUSINESS_DAY_SALES_REVIEW"
    assert report["auto_send"] is False
    assert report["execution_authority"] == "NONE"
    for ctx in (context(inbound_response_basis_verified=False),
                context(offer_evidence_current=False)):
        assert review(signal("optin_enquiry"), ctx=ctx)["action"] == "HOLD_INBOUND_BASIS"


def test_verified_pricing_meeting_terms_and_payment_are_distinct():
    cases = [
        ("pricing_request", "SAME_BUSINESS_DAY_SALES_REVIEW"),
        ("meeting_booked", "SAME_BUSINESS_DAY_SALES_REVIEW"),
        ("terms_accepted", "REVIEW_ACCEPTED_TERMS"),
        ("verified_paying_customer", "REVIEW_EXISTING_CUSTOMER"),
    ]
    for i, (kind, status) in enumerate(cases, 1):
        assert review(signal(kind, idx=i))["action"] == status


@pytest.mark.parametrize("negative", ["unsubscribe", "hard_bounce", "explicit_not_interested"])
def test_negative_signal_overrides_payment_or_meeting(negative):
    report = review(signal("verified_paying_customer", idx=1),
                    signal(negative, idx=2, when=NOW-timedelta(days=120)))
    assert report["action"] == "STOP_AND_SUPPRESS"
    assert report["hard_stop_signal_count"] == 1
    assert report["auto_send"] is False


def test_current_canonical_suppression_overrides_any_observed_event():
    report = review(signal("meeting_booked"), ctx=context(suppression_clear=False))
    assert report["action"] == "STOP_AND_SUPPRESS"


def test_account_source_or_identity_unknown_fail_closed():
    assert review(signal("pricing_request"),
                  ctx=context(canonical_account_verified=False))["action"] == "HOLD_IDENTITY_OR_SOURCE"
    with pytest.raises(CampaignIntelligenceHeld):
        review(signal("optin_enquiry", source_receipt_verified=False))
    with pytest.raises(CampaignIntelligenceHeld):
        review(signal("optin_enquiry", canonical_account_link_verified=False))
    with pytest.raises(CampaignIntelligenceHeld):
        review(signal("optin_enquiry", purpose_lawfulness_verified=False))


def test_wrong_source_or_cross_tenant_signal_rejected():
    with pytest.raises(CampaignIntelligenceHeld, match="SOURCE_PAIR"):
        review(signal("optin_enquiry", source="first_party_click_gateway"))
    with pytest.raises(CampaignIntelligenceHeld, match="CROSS_TENANT"):
        review(signal(tenant_ref="tenant_somebodyelse"))
    with pytest.raises(CampaignIntelligenceHeld, match="CROSS_TENANT"):
        review(signal(campaign_id="campaign_" + "f"*24))


def test_conflicting_event_replay_is_rejected_but_same_retry_deduped():
    first = signal(idx=1)
    assert review(first, first)["replayed_event_ids_discarded"] == 1
    changed = replace(first, kind="optin_enquiry", source="canonical_crm")
    with pytest.raises(CampaignIntelligenceHeld, match="CONFLICT"):
        review(first, changed)


def test_old_positive_signal_not_current_but_old_negative_remains_stop():
    old = signal("email_link_clicked", when=NOW-timedelta(days=50))
    assert review(old)["action"] == "NO_OBSERVED_INTENT"
    assert review(old)["stale_positive_observations"] == 1
    negative = signal("unsubscribe", idx=2, when=NOW-timedelta(days=350))
    assert review(negative)["action"] == "STOP_AND_SUPPRESS"


def test_future_and_too_old_signal_are_rejected():
    for when in (NOW+timedelta(minutes=2), NOW-timedelta(days=366)):
        with pytest.raises(CampaignIntelligenceHeld, match="TIME"):
            review(signal(when=when))


def test_same_day_review_portfolio_returns_only_privacy_safe_aggregates():
    report = review_private_account_portfolio([
        (context(), [signal("pricing_request", idx=1)]),
        (context(account_key="c"*32), [signal(idx=2, account_key="c"*32)]),
    ], now=NOW)
    assert report["accounts_reviewed"] == 2
    assert report["action_counts"]["SAME_BUSINESS_DAY_SALES_REVIEW"] == 1
    assert report["action_counts"]["INTERNAL_RESEARCH_ONLY"] == 1
    assert report["scheduled_communications"] == 0
    dumped = json.dumps(report)
    assert ACCOUNT not in dumped
    assert "c"*32 not in dumped


def test_duplicate_portfolio_identity_fails_closed():
    with pytest.raises(CampaignIntelligenceHeld, match="DUPLICATE"):
        review_private_account_portfolio([
            (context(), []), (context(), []),
        ], now=NOW)


def arms(*, trusted=True, financial=False, negative=False):
    totals = {
        "no_marketing_holdout": (100, 0, 1, 0, 0, 100, 1000),
        "buyer_inventory_fit_offer": (100, 95, 5, 1, 0, 600, 10000),
        "revenue_leak_signal_offer": (100, 90, 4, 2, 0, 1600, 13000),
        "verified_market_opportunity_brief": (100, 95, 2, 2, 0, 300, 7000),
    }
    if negative:
        totals["buyer_inventory_fit_offer"] = (100, 95, 10, 1, 5, 1200, 10000)
    return [
        TrustedArmOutcome(
            arm=k, assigned_accounts=n, delivered_accounts=d,
            paying_customers=p, unsubscribe_accounts=u,
            complaint_accounts=c,
            realized_gp_cents=gp if financial else None,
            recognized_revenue_cents=rev if financial else None,
            canonical_receipts_verified=trusted,
            assignment_integrity_verified=True,
            outcome_window_closed=True, financial_receipts_verified=financial,
        )
        for k, (n,d,p,u,c,gp,rev) in totals.items()
    ]


def test_arm_evaluation_correctly_uses_assigned_accounts_with_zero_delivery_holdout():
    result = evaluate_real_customer_experiment(arms())
    assert result["status"] == "DESCRIPTIVE_OFFER_CANDIDATE_HUMAN_REVIEW_ONLY"
    assert result["candidate_offer_arm"] == "buyer_inventory_fit_offer"
    assert result["primary_metric"] == "verified_paying_customers_per_randomly_assigned_account"
    control = next(x for x in result["arm_reviews"] if x["arm"] == "no_marketing_holdout")
    assert control["delivered_accounts"] == 0
    assert control["paid_customer_rate_per_assigned_account"] == 0.01
    assert result["significance_or_causal_lift_claimed"] is False
    assert result["auto_budget_raised"] is False


def test_verified_gross_profit_can_override_click_or_customer_count_winner():
    result = evaluate_real_customer_experiment(arms(financial=True))
    assert result["comparison_metric"] == "realized_gp_per_assigned_account_cents"
    assert result["candidate_offer_arm"] == "revenue_leak_signal_offer"
    assert result["arm_reviews"][0]["recognized_revenue_cents"] == 1000


def test_unverified_paying_customer_receipts_never_produce_winner():
    result = evaluate_real_customer_experiment(arms(trusted=False))
    assert result["candidate_offer_arm"] is None
    assert "OBSERVATIONAL_RESULTS_NOT_READY" == result["status"]
    assert all(row["paid_customer_rate_per_assigned_account"] is None for row in result["arm_reviews"])


def test_high_complaint_arm_cannot_win_even_when_converting_more():
    result = evaluate_real_customer_experiment(arms(negative=True))
    assert result["candidate_offer_arm"] == "revenue_leak_signal_offer"
    top = next(x for x in result["arm_reviews"] if x["arm"] == "buyer_inventory_fit_offer")
    assert top["complaint_or_optout_hold"] is True


def test_holdout_receiving_marketing_rejected():
    bad = arms()
    bad[0] = replace(bad[0], delivered_accounts=1)
    with pytest.raises(CampaignIntelligenceHeld, match="HOLDOUT"):
        evaluate_real_customer_experiment(bad)


def test_invalid_counts_low_sample_and_missing_financial_amounts():
    bad = arms()
    bad[1] = replace(bad[1], paying_customers=101)
    with pytest.raises(CampaignIntelligenceHeld, match="INCOHERENT"):
        evaluate_real_customer_experiment(bad)
    bad = arms()
    bad[1] = replace(bad[1], assigned_accounts=10, delivered_accounts=9)
    assert evaluate_real_customer_experiment(bad)["candidate_offer_arm"] is None
    bad = arms()
    bad[1] = replace(bad[1], financial_receipts_verified=True)
    with pytest.raises(CampaignIntelligenceHeld, match="FINANCIAL"):
        evaluate_real_customer_experiment(bad)


def test_no_paid_customers_means_no_commercial_winner():
    empty = [
        replace(x, paying_customers=0)
        for x in arms()
    ]
    report = evaluate_real_customer_experiment(empty)
    assert report["candidate_offer_arm"] is None
    assert report["status"] == "NO_POSITIVE_OBSERVED_OFFER_ADVANTAGE"

from empire_os.campaign_intelligence import (
    TrustedCampaignFunnelStage, diagnose_campaign_conversion_bottlenecks,
)


def stage(kind="visitor_to_lead", *, entered=100, converted=20, **changes):
    return replace(TrustedCampaignFunnelStage(
        stage=kind,
        entered_accounts=entered,
        converted_accounts=converted,
        canonical_source_ref="canonical:commercial_events:receipt_aabbccdd",
        source_receipts_verified=True,
        campaign_attribution_verified=True,
        outcome_window_closed=True,
    ), **changes)


def test_real_source_verified_funnel_identifies_a_test_not_a_revenue_claim():
    rows = [
        stage("visitor_to_lead", entered=150, converted=15),
        stage("delivered_outreach_to_reply", entered=120, converted=24),
        stage("reply_to_qualified_conversation", entered=90, converted=45),
        stage("acceptance_to_payment", entered=50, converted=40),
    ]
    report = diagnose_campaign_conversion_bottlenecks(rows)
    assert report["lowest_observed_stage"] == "visitor_to_lead"
    assert report["next_test"] == "test_landing_page_offer_and_form_clarity"
    assert report["verified_stages_with_sufficient_sample"] == 4
    assert report["incremental_revenue_or_causal_lift_claimed"] is False
    assert report["campaign_mutated"] is False


def test_optimisation_is_not_based_on_untrusted_or_small_samples():
    result = diagnose_campaign_conversion_bottlenecks([
        stage(entered=100, converted=1, source_receipts_verified=False),
        stage("delivered_outreach_to_reply", entered=10, converted=1),
    ])
    assert result["lowest_observed_stage"] is None
    assert result["next_test"] is None
    assert result["status"] == "HOLD_INSUFFICIENT_VERIFIED_FUNNEL"


def test_invalid_stage_cross_group_counts_and_fake_evidence_ref_fail():
    for row in (
        stage("not_a_stage"),
        stage(entered=10, converted=11),
        stage(canonical_source_ref="https://example.test/private"),
    ):
        with pytest.raises(CampaignIntelligenceHeld):
            diagnose_campaign_conversion_bottlenecks([row])
    with pytest.raises(CampaignIntelligenceHeld, match="DUPLICATE"):
        diagnose_campaign_conversion_bottlenecks([stage(), stage()])


def test_public_procurement_and_growth_signals_are_research_only():
    for kind, source in [
        ("verified_public_procurement", "verified_public_intent_source"),
        ("public_company_growth_signal", "verified_public_intent_source"),
    ]:
        row = signal(kind)
        assert review(row)["action"] == "INTERNAL_RESEARCH_ONLY"
        assert review(row)["auto_send"] is False


def test_social_verified_inbound_has_same_day_review_if_response_permitted():
    row = signal("verified_social_inbound_enquiry")
    assert review(row)["action"] == "SAME_BUSINESS_DAY_SALES_REVIEW"
    assert review(row, ctx=context(inbound_response_basis_verified=False))["action"] == "HOLD_INBOUND_BASIS"


def test_website_offer_visits_never_allow_direct_messaging():
    row = signal("consented_offer_page_visit")
    result = review(row)
    assert result["action"] == "INTERNAL_RESEARCH_ONLY"
    assert result["auto_send"] is False
    assert result["auto_retarget"] is False

from scripts.review_tam_full_funnel_strategy_20261020 import (
    review_authenticated_campaign_intelligence,
    recommend_next_real_execution_focus,
)


def test_integration_no_authenticated_sources_does_not_fabricate_counts():
    result = review_authenticated_campaign_intelligence(now=NOW)
    assert result["source_status"] == "EXISTING_OWNERS_MUST_SUPPLY_AUTHENTICATED_RECEIPT_ADAPTERS"
    assert result["account_intelligence"] is None
    assert result["verified_customer_experiment"] is None
    assert result["conversion_bottleneck_review"] is None
    assert result["database_writes"] is False
    assert result["live_recipient_contact_or_messages"] is False


def test_existing_owner_evidence_flows_to_all_three_intelligence_processors():
    result = review_authenticated_campaign_intelligence(
        now=NOW,
        account_packets=[(context(), [signal("optin_enquiry")])],
        experiment_arms=arms(),
        funnel_stage_receipts=[stage("acceptance_to_payment", entered=80, converted=40)],
    )
    assert result["source_status"] == "REVIEWED_OWNER_SUPPLIED_OFFLINE_EVIDENCE"
    assert result["account_intelligence"]["action_counts"]["SAME_BUSINESS_DAY_SALES_REVIEW"] == 1
    assert result["verified_customer_experiment"]["candidate_offer_arm"] == "buyer_inventory_fit_offer"
    assert result["conversion_bottleneck_review"]["lowest_observed_stage"] == "acceptance_to_payment"
    assert result["production_training_or_model_mutation"] is False
    assert result["execution_authority"] == "NONE"


def test_commercial_next_action_prioritises_real_buyer_contact_readiness():
    base = {
        "real_buyer_contactability": {
            "source_status": "VERIFIED_READONLY_BUYER_SNAPSHOTS",
            "buyer_contact_verified_count": 0,
        },
        "campaign_assets": {"deployed_assets_correlated_to_runtime": 5},
        "verified_commercial_feedback": {"outcome_linkage_verified": False},
    }
    r = recommend_next_real_execution_focus(base)
    assert r["priority"] == "VERIFY_REAL_FIRST_WAVE_BUYER_CONTACTS_WITH_EXISTING_SALES_OWNER"
    assert r["auto_send_authorized"] is False
    base["real_buyer_contactability"]["buyer_contact_verified_count"] = 20
    assert recommend_next_real_execution_focus(base)["priority"] == "PROVE_PERMISSIONED_SENDABLE_RECIPIENTS_WITH_EXISTING_SALES_OWNER"
    base["real_buyer_contactability"]["permitted_email_recipients"] = 20
    assert recommend_next_real_execution_focus(base)["priority"] == "RUN_ONE_GOVERNED_MARKET_WAVE_USING_EXISTING_OUTREACH_OWNER"
    base["first_market_wave_delivered_verified"] = True
    assert recommend_next_real_execution_focus(base)["priority"] == "CONNECT_REAL_CAMPAIGN_AND_CUSTOMER_OUTCOME_RECEIPTS"
    base["verified_commercial_feedback"]["outcome_linkage_verified"] = True
    assert recommend_next_real_execution_focus(base)["priority"] == "REVIEW_REAL_CUSTOMER_OFFER_EXPERIMENT_BEFORE_SCALING"


def test_loss_making_offer_cannot_win_even_if_less_bad_than_control():
    rows = arms(financial=True)
    # All are genuinely losing money; relative performance is not profit.
    losses = {
        "no_marketing_holdout": -1200,
        "buyer_inventory_fit_offer": -100,
        "revenue_leak_signal_offer": -200,
        "verified_market_opportunity_brief": -300,
    }
    rows = [replace(row, realized_gp_cents=losses[row.arm]) for row in rows]
    result = evaluate_real_customer_experiment(rows)
    assert result["candidate_offer_arm"] is None
    assert result["status"] == "NO_POSITIVE_REALIZED_GROSS_PROFIT"
    assert result["auto_budget_raised"] is False
