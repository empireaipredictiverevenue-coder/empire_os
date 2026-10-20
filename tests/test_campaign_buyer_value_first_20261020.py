"""Value-first offers are generated from authentic, separately bound sources.

All data here are offline fixtures; no buyer, supplier, lead or money is real.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.campaign_intelligence import (
    AccountIntelligenceContext, TrustedBuyerValueProblem,
    TrustedOfferCapability, TrustedBuyerValueCase, TrustedCampaignSignal,
    CampaignIntelligenceHeld, review_buyer_value_first_offer,
    review_buyer_value_first_portfolio,
)
from scripts.review_tam_full_funnel_strategy_20261020 import (
    review_authenticated_campaign_intelligence,
)

NOW = datetime(2026, 10, 20, 11, tzinfo=timezone.utc)
ACC = "a"*32
TENANT = "tenant_empireai"
CAMPAIGN = "campaign_" + "f"*24
ARMS = {
    "supply_territory_fit": (
        "buyer_inventory_fit_offer", "canonical_inventory",
        "verified_supply_acceptance_fit",
    ),
    "missed_demand_followup": (
        "revenue_leak_signal_offer", "canonical_first_party_analytics",
        "verified_conversion_bottleneck",
    ),
    "market_expansion_decision": (
        "verified_market_opportunity_brief", "verified_public_market_source",
        "verified_territory_market_signal",
    ),
}


def ctx(**kw):
    return replace(AccountIntelligenceContext(
        tenant_ref=TENANT, account_key=ACC,
        market_scope="GB:solar:buyers", campaign_id=CAMPAIGN,
        canonical_account_verified=True, suppression_clear=True,
        inbound_response_basis_verified=True,
        marketing_contact_basis_verified=False,
        offer_evidence_current=True,
    ), **kw)


def problem(code="supply_territory_fit", **kw):
    return replace(TrustedBuyerValueProblem(
        tenant_ref=TENANT, account_key=ACC,
        market_scope="GB:solar:buyers",
        problem_code=code, observed_at=NOW,
        buyer_directly_stated_problem=True,
        canonical_crm_evidence_verified=True,
        friction_code="quality_uncertainty",
        friction_receipt_verified=True,
    ), **kw)


def capability(code="supply_territory_fit", **kw):
    arm, source, kind = ARMS[code]
    return replace(TrustedOfferCapability(
        tenant_ref=TENANT, market_scope="GB:solar:buyers",
        offer_arm=arm, capability_source=source, proof_kind=kind,
        proof_key="e"*32, verified_at=NOW,
        source_receipt_verified=True,
        currently_deliverable=True,
        verified_sufficient_market_fit=True,
        paid_catalog_product=None,
    ), **kw)


def signals(kind="pricing_request", **kw):
    source = {
        "pricing_request": "canonical_crm",
        "optin_enquiry": "canonical_crm",
        "meeting_booked": "canonical_crm",
        "email_link_clicked": "first_party_click_gateway",
        "verified_public_procurement": "verified_public_intent_source",
        "unsubscribe": "canonical_crm",
        "verified_paying_customer": "canonical_commercial_ledger",
    }[kind]
    return (replace(TrustedCampaignSignal(
        event_id="b"*32, tenant_ref=TENANT, account_key=ACC,
        market_scope="GB:solar:buyers", campaign_id=CAMPAIGN,
        kind=kind, source=source, observed_at=NOW,
        source_receipt_verified=True, canonical_account_link_verified=True,
        purpose_lawfulness_verified=True,
    ), **kw),)


def case(code="supply_territory_fit", **kw):
    return replace(TrustedBuyerValueCase(
        context=ctx(), problem=problem(code),
        capabilities=(capability(code),),
    ), **kw)


def review(value=None, *, signal_rows=()):
    return review_buyer_value_first_offer(
        value or case(), verified_signals=signal_rows, now=NOW,
    )


@pytest.mark.parametrize("code,arm", [
    ("supply_territory_fit", "buyer_inventory_fit_offer"),
    ("missed_demand_followup", "revenue_leak_signal_offer"),
    ("market_expansion_decision", "verified_market_opportunity_brief"),
])
def test_buyer_proven_need_and_verified_deliverability_select_correct_offer(code, arm):
    result = review(case(code))
    assert result["review_play"] == "PREPARE_PROOF_FIRST_VALUE_BRIEF_NO_SALES_CTA"
    assert result["offer_candidate"] == arm
    assert result["value_first_deliverable"]
    assert result["proof_based_demo_outline"]["format"] == "screen_demo"
    assert result["proof_based_demo_outline"]["asset_created_or_published"] is False
    assert result["buyer_risk_resolution"]
    assert result["commercial_cta_review_eligible"] is False
    assert result["paid_price_quoted_cents"] is None
    assert result["roi_or_results_guaranteed"] is False
    assert result["auto_send"] is False
    dumped = json.dumps(result)
    assert ACC not in dumped and TENANT not in dumped and "e"*32 not in dumped


def test_explicit_recent_buyer_request_opens_human_cta_review_not_automatic_outreach():
    packet = review(signal_rows=signals())
    assert packet["commercial_cta_review_eligible"] is True
    assert packet["review_play"] == "SAME_DAY_RESPOND_WITH_VALUE_THEN_REVIEW_CTA"
    assert packet["auto_follow_up"] is False
    assert packet["campaign_auto_enrolled"] is False
    assert packet["execution_authority"] == "NONE"


def test_click_or_public_market_research_never_turns_into_buyer_cta():
    for kind in ("email_link_clicked", "verified_public_procurement"):
        packet = review(signal_rows=signals(kind))
        assert packet["review_play"] == "PREPARE_PROOF_FIRST_VALUE_BRIEF_NO_SALES_CTA"
        assert packet["commercial_cta_review_eligible"] is False


def test_inbound_without_permission_to_reply_still_has_no_commercial_cta():
    packet = review(case(context=ctx(inbound_response_basis_verified=False)),
                    signal_rows=signals("pricing_request"))
    assert packet["commercial_cta_review_eligible"] is False
    assert packet["auto_send"] is False


def test_explicit_suppression_dominates_verified_offer_proof():
    packet = review(case(context=ctx(suppression_clear=False)),
                    signal_rows=signals("pricing_request"))
    assert packet["review_play"] == "STOP_CONTACT_AND_SUPPRESS"
    assert packet["offer_candidate"] is None
    assert packet["commercial_cta_review_eligible"] is False
    packet = review(signal_rows=signals("unsubscribe"))
    assert packet["review_play"] == "STOP_CONTACT_AND_SUPPRESS"
    assert packet["value_first_deliverable"] is None


def test_unknown_account_identity_blocks_selected_commercial_offer():
    packet = review(case(context=ctx(canonical_account_verified=False)))
    assert packet["review_play"] == "HOLD_ACCOUNT_IDENTITY"
    assert packet["offer_candidate"] is None


def test_unproven_or_stale_buyer_need_cannot_fake_personalized_pain():
    for buyer_problem in (
        problem(buyer_directly_stated_problem=False),
        problem(canonical_crm_evidence_verified=False),
        problem(observed_at=NOW-timedelta(days=46)),
    ):
        packet = review(case(problem=buyer_problem), signal_rows=signals())
        assert packet["buyer_problem_proven_by_first_party"] is False
        assert packet["offer_candidate"] is None
        assert packet["review_play"] == "RESEARCH_BUYER_NEED_BEFORE_PERSONALIZATION"
        assert packet["commercial_cta_review_eligible"] is False


def test_no_buyer_problem_does_not_create_one_from_site_or_supply():
    packet = review(case(problem=None), signal_rows=signals("email_link_clicked"))
    assert packet["buyer_problem_type"] is None
    assert packet["offer_candidate"] is None


def test_current_inventory_proof_only_seven_days_old():
    packet = review(case(capabilities=(capability(
        verified_at=NOW-timedelta(days=8),
    ),)))
    assert packet["offer_candidate"] is None
    assert packet["offer_proof_statuses"]["buyer_inventory_fit_offer"] == "HOLD_STALE_PROOF"


def test_offer_not_ready_or_incompatible_tenant_cannot_be_sold():
    for change, hold in (
        ({"source_receipt_verified": False}, "HOLD_SOURCE_UNVERIFIED"),
        ({"currently_deliverable": False}, "HOLD_UNAVAILABLE_DELIVERY"),
        ({"verified_sufficient_market_fit": False}, "HOLD_UNVERIFIED_MARKET_FIT"),
    ):
        packet = review(case(capabilities=(capability(**change),)))
        assert packet["offer_candidate"] is None
        assert packet["offer_proof_statuses"]["buyer_inventory_fit_offer"] == hold


def test_public_market_signal_cannot_be_falsely_labelled_supplier_inventory():
    with pytest.raises(CampaignIntelligenceHeld, match="OFFER_PROOF_OR_PROVENANCE"):
        review(case(capabilities=(capability(capability_source="verified_public_market_source"),)))


def test_paid_product_quote_requires_canonical_product_readiness():
    unready = {
        "active": True, "binding_terms_ready": False,
        "catalog_state": "VERIFIED", "version_state": "VERIFIED",
        "price_basis": {"amount_cents": 5000, "currency": "USD", "unit": "one_off"},
    }
    packet = review(case(capabilities=(capability(
        paid_catalog_product=unready,
    ),)))
    assert packet["offer_candidate"] is None
    assert packet["offer_proof_statuses"]["buyer_inventory_fit_offer"] == "HOLD_UNVERIFIED_PAID_PRODUCT"
    paid = {**unready, "binding_terms_ready": True, "readiness_blockers": []}
    packet = review(case(capabilities=(capability(
        paid_catalog_product=paid,
    ),)))
    assert packet["offer_candidate"] == "buyer_inventory_fit_offer"
    assert packet["paid_price_quoted_cents"] is None


def test_unconfirmed_buyer_objection_is_not_fabricated():
    packet = review(case(problem=problem(friction_receipt_verified=False)))
    assert packet["buyer_risk_resolution"] is None
    assert packet["buyer_friction_confirmed"] is None


def test_cross_tenant_proof_and_buyer_need_are_rejected():
    with pytest.raises(CampaignIntelligenceHeld, match="CROSS_TENANT_OFFER_PROOF"):
        review(case(capabilities=(capability(tenant_ref="tenant_different01"),)))
    with pytest.raises(CampaignIntelligenceHeld, match="CROSS_ACCOUNT_OR_UNSUPPORTED_BUYER_PROBLEM"):
        review(case(problem=problem(account_key="f"*32)))


def test_only_matching_offer_type_may_solve_the_buyers_need():
    packet = review(case(
        problem=problem("market_expansion_decision"),
        capabilities=(capability("supply_territory_fit"),),
    ))
    assert packet["offer_candidate"] is None
    assert packet["review_play"] == "VERIFY_DELIVERABLE_BUYER_VALUE_BEFORE_OFFER"


def test_duplicate_offer_capabilities_fail_closed():
    with pytest.raises(CampaignIntelligenceHeld, match="DUPLICATE"):
        review(case(capabilities=(capability(),capability())))


def test_future_source_and_unknown_enum_or_trust_flag_fail_closed():
    for item in (
        case(problem=problem(observed_at=NOW+timedelta(hours=1))),
        case(capabilities=(capability(verified_at=NOW+timedelta(days=1)),)),
        case(problem=problem(problem_code="imaginary_problem")),
        case(capabilities=(capability(currently_deliverable="true"),)),
    ):
        with pytest.raises(CampaignIntelligenceHeld):
            review(item)


def test_portfolio_never_exports_private_people_or_claimed_commercial_conversions():
    packet = review_buyer_value_first_portfolio([
        (case(), signals("pricing_request")),
    ], now=NOW)
    assert packet["accounts_reviewed"] == 1
    assert packet["buyer_value_next_play_counts"] == {
        "SAME_DAY_RESPOND_WITH_VALUE_THEN_REVIEW_CTA": 1,
    }
    assert packet["evidence_backed_offer_candidate_counts"]["buyer_inventory_fit_offer"] == 1
    assert packet["messages_or_quotes_sent"] == 0
    assert "a"*32 not in json.dumps(packet)


def test_portfolio_rejects_same_account_twice():
    with pytest.raises(CampaignIntelligenceHeld, match="DUPLICATE_VALUE_PORTFOLIO"):
        review_buyer_value_first_portfolio([
            (case(), ()), (case(), ()),
        ], now=NOW)


def test_integration_full_funnel_accepts_value_case_owner_packets():
    output = review_authenticated_campaign_intelligence(
        now=NOW, value_case_packets=[(case(), signals("pricing_request"))],
    )
    assert output["buyer_value_first_offer_review"]["accounts_reviewed"] == 1
    assert output["authenticated_tenant_crm_handoff"] is None
    assert output["live_recipient_contact_or_messages"] is False


def test_live_entry_without_value_case_source_remains_unknown_not_zero():
    output = review_authenticated_campaign_intelligence(now=NOW)
    assert output["buyer_value_first_offer_review"] is None


def test_private_experience_renders_three_minute_proof_first_buyer_page():
    from empire_os.campaign_intelligence import build_private_buyer_offer_experience
    preview = build_private_buyer_offer_experience(
        case(), verified_signals=(), now=NOW,
    )
    assert preview["status"] == "PRIVATE_OPERATOR_PREVIEW_READY"
    assert preview["offer_arm"] == "buyer_inventory_fit_offer"
    assert preview["demo_target_seconds"] == 180
    assert len(preview["demo_storyboard"]) == 3
    assert "<!doctype html>" in preview["private_html"]
    assert "Empire AI" in preview["private_html"]
    assert "Better-fit opportunities start with better evidence." in preview["private_html"]
    assert "PRIVATE PREVIEW" in preview["private_html"]
    assert preview["publication_authorized"] is False
    assert preview["working_first_party_cta_present"] is False
    assert preview["customer_or_account_identity_exposed"] is False
    assert preview["financial_results_or_inventory_quantity_claimed"] is False
    assert preview["legal_privacy_consent_and_landing_owner_signoff_required"] is True
    assert "a"*32 not in preview["private_html"]
    assert "e"*32 not in preview["private_html"]
    assert "tenant_empireai" not in preview["private_html"]


@pytest.mark.parametrize("code,unique", [
    ("supply_territory_fit", "Define the buy box"),
    ("missed_demand_followup", "Trace the handoff"),
    ("market_expansion_decision", "Set the market criteria"),
])
def test_private_offer_page_content_and_storyboard_match_buyer_need(code, unique):
    from empire_os.campaign_intelligence import build_private_buyer_offer_experience
    output = build_private_buyer_offer_experience(case(code), verified_signals=(), now=NOW)
    assert unique in output["private_html"]
    assert output["demo_storyboard"][0]["title"] == unique
    assert "No. " in output["private_html"]
    assert output["market_scope"] == "GB:solar:buyers"
    assert output["source_proof_day"] == "2026-10-20"
    assert all(not step["live_customer_example_included"] for step in output["demo_storyboard"])


def test_private_offer_preview_is_inert_without_sender_or_tracking_controls():
    from empire_os.campaign_intelligence import build_private_buyer_offer_experience
    import re
    markup = build_private_buyer_offer_experience(
        case(), verified_signals=signals("pricing_request"), now=NOW,
    )["private_html"].lower()
    for forbidden in (
        "<script", "<iframe", "<form", "<input", "<button",
        "href=", "fetch(", "navigator.", "mailto:", "tel:",
        "http://", "https://", "onclick=", "onload=",
    ):
        assert forbidden not in markup
    assert 'name="robots" content="noindex,nofollow,noarchive"' in markup
    assert 'default-src &#39;none&#39;' not in markup  # literal CSP attribute
    assert 'default-src \'none\'' in markup


def test_private_offer_hold_produces_no_buyer_facing_page():
    from empire_os.campaign_intelligence import build_private_buyer_offer_experience
    for value in (
        case(problem=None),
        case(context=ctx(suppression_clear=False)),
        case(capabilities=(capability(currently_deliverable=False),)),
        case(capabilities=(capability(source_receipt_verified=False),)),
        case(problem=problem(buyer_directly_stated_problem=False)),
    ):
        result = build_private_buyer_offer_experience(
            value, verified_signals=(), now=NOW,
        )
        assert result["status"] == "HOLD_NO_SUPPORTED_PUBLIC_FACING_VALUE"
        assert result["private_html"] is None
        assert result["demo_storyboard"] is None
        assert result["publication_authorized"] is False


def test_verified_explicit_inbound_does_not_activate_real_cta():
    from empire_os.campaign_intelligence import build_private_buyer_offer_experience
    output = build_private_buyer_offer_experience(
        case(), verified_signals=signals("pricing_request"), now=NOW,
    )
    assert output["status"] == "PRIVATE_OPERATOR_PREVIEW_READY"
    assert output["working_first_party_cta_present"] is False
    assert output["execution_authority"] == "NONE"
    assert "No form, external link or automatic contact has been activated." in output["private_html"]


def test_private_preview_escaping_never_leaks_raw_proof_keys_or_account_fields():
    from empire_os.campaign_intelligence import build_private_buyer_offer_experience
    value = case(context=ctx(
        tenant_ref="tenant_canonical0123",
        campaign_id="campaign_"+"f"*24,
    ))
    # Wrong market/tenant context is rejected rather than using dynamic
    # untrusted strings in static HTML.
    with pytest.raises(CampaignIntelligenceHeld):
        build_private_buyer_offer_experience(value, verified_signals=(), now=NOW)


def test_value_portfolio_reports_preview_eligibility_without_exporting_html():
    result = review_buyer_value_first_portfolio(
        [(case(), ()),], now=NOW,
    )
    assert result["proof_first_private_page_candidate_count"] == 1
    assert "private_html" not in result
    assert result["public_buyer_list_exposed"] is False


def test_full_funnel_shared_interface_exposes_preview_readiness_count_only():
    result = review_authenticated_campaign_intelligence(
        now=NOW, value_case_packets=[(case(), ())],
    )
    assert result["buyer_value_first_offer_review"][
        "proof_first_private_page_candidate_count"
    ] == 1
    assert "private_html" not in json.dumps(result)
    assert result["live_recipient_contact_or_messages"] is False


def test_prospect_mind_eight_questions_are_explicitly_answered_or_open():
    from empire_os.campaign_intelligence import (
        build_private_buyer_offer_experience,
    )
    experience = build_private_buyer_offer_experience(
        case(), verified_signals=(), now=NOW,
    )
    audit = experience["prospect_question_coverage"]
    assert audit["questions_reviewed"] == 8
    assert audit["answered_at_review_level"] == 2
    assert audit["partially_answered"] == 3
    assert audit["owner_evidence_needed"] == 3
    assert audit["open_question_keys"] == [
        "price_and_risk", "delivery_timing", "working_next_step",
    ]
    assert audit["all_commercial_questions_answered"] is False
    assert audit["conversion_ready_for_live_site"] is False
    assert "What will I pay and what is the risk?" in experience["private_html"]
    assert "How quickly can we start and deliver?" in experience["private_html"]
    assert "Why choose Empire AI?" in experience["private_html"]
    assert "No competitor comparison or" in experience["private_html"]
    assert "A price, contract, acceptance rules" in experience["private_html"]
    assert "Start date, turnaround" in experience["private_html"]


@pytest.mark.parametrize("problem_code", list(ARMS))
def test_each_offer_experience_has_eight_answers_without_fake_roi_or_price(problem_code):
    from empire_os.campaign_intelligence import (
        build_private_buyer_offer_experience,
    )
    result = build_private_buyer_offer_experience(
        case(problem_code), verified_signals=(), now=NOW,
    )
    audit = result["prospect_question_coverage"]
    assert len({entry["question_key"] for entry in audit["questions"]}) == 8
    assert audit["questions_reviewed"] == 8
    assert audit["execution_authority"] == "NONE"
    assert audit["owner_evidence_needed"] >= 3
    assert audit["all_commercial_questions_answered"] is False
    assert result["publication_authorized"] is False


def test_coverage_never_accepts_unverified_or_bogus_value_report():
    from empire_os.campaign_intelligence import (
        review_prospect_question_coverage,
    )
    with pytest.raises(CampaignIntelligenceHeld, match="PROSPECT_QUESTION_SOURCE_PROOF_REQUIRED"):
        review_prospect_question_coverage(
            {"offer_candidate": "buyer_inventory_fit_offer",
             "buyer_problem_proven_by_first_party": False},
            market_label="UK solar buyers", source_review_day="2026-10-20",
        )
