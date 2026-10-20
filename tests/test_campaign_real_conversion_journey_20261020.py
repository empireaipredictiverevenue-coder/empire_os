"""Exact source-provenance conversion journey tests. All contacts and payments
are offline fixtures, never production orders, buyers or revenue."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
import json
import pytest

from empire_os.campaign_intelligence import (
    CampaignIntelligenceHeld, TrustedResearchEnquiry,
    TrustedResearchCrmAttribution, TrustedResearchCommercialOutcome,
    review_released_research_route, reconcile_first_party_conversion_journey,
)
from empire_os.owned_campaign_content import PRIVACY
from empire_os.owned_campaign_intake import accept, validate_enquiry
from scripts.review_tam_full_funnel_strategy_20261020 import (
    review_authenticated_campaign_intelligence,
)

NOW = datetime(2026, 10, 20, 16, tzinfo=timezone.utc)
CID = "campaign_" + "a"*24
ASSET = CID + ":landing"
ENQUIRY_ID = "671e45d0-3802-4cbc-975b-97edc1495088"
PROSPECT_ID = "671e45d0-3802-4cbc-975b-97edc1495099"
TENANT_ID = "d60c9a21-b1c4-4e95-9ab6-11b432629a41"
ORDER_ID = "671e45d0-3802-4cbc-975b-97edc14950aa"
START = NOW-timedelta(days=3)


def marketing():
    return {"campaigns": [{
        "campaign_id": CID, "outbound_authorized": False,
        "conversion_plan": {"landing_path": f"/research/{CID}"},
        "assets": [{
            "asset_type": "landing_page", "asset_id": ASSET,
            "privacy_notice": PRIVACY,
        }],
    }]}


def released_route(monkeypatch):
    monkeypatch.setattr(
        "empire_os.owned_campaign_release.load_release",
        lambda *, root: marketing(),
    )
    return review_released_research_route(
        root=Path("/repo-fixture"), campaign_id=CID, now=NOW,
    )


def enq(**changes):
    return replace(TrustedResearchEnquiry(
        campaign_id=CID, asset_id=ASSET, receipt_id=ENQUIRY_ID,
        received_at=START, release_website_binding_verified=True,
        canonical_intake_readback_verified=True,
        original_same_origin_admission_verified=True,
    ), **changes)


def crm(**changes):
    return replace(TrustedResearchCrmAttribution(
        campaign_id=CID, enquiry_receipt_id=ENQUIRY_ID,
        tenant_id=TENANT_ID, prospect_id=PROSPECT_ID,
        recorded_at=START+timedelta(minutes=15),
        exact_intake_to_prospect_link_verified=True,
        authenticated_tenant_reader_verified=True,
    ), **changes)


def outcome(**changes):
    return replace(TrustedResearchCommercialOutcome(
        campaign_id=CID, tenant_id=TENANT_ID,
        prospect_id=PROSPECT_ID, order_id=ORDER_ID,
        finance_event_key="e"*32,
        paid_at=START+timedelta(hours=2),
        delivered_at=START+timedelta(hours=6),
        recognized_at=START+timedelta(hours=7),
        actual_cost_verified=True, payment_settlement_verified=True,
        fulfilment_verified=True, recognized_revenue_event_verified=True,
        canonical_order_prospect_join_verified=True,
        recognized_revenue_cents=10000, actual_cost_cents=2500,
        realized_gp_cents=7500,
    ), **changes)


def join(route, enquiries=None, links=None, outcomes=None, *, closed=False):
    return reconcile_first_party_conversion_journey(
        root=Path("/repo-fixture"), released_route=route, enquiries=enquiries,
        crm_links=links, commercial_outcomes=outcomes,
        now=NOW, finance_window_complete=closed,
    )


def test_validated_released_route_reuses_existing_production_enquiry_schema(monkeypatch):
    route = released_route(monkeypatch)
    assert route["status"] == "EXISTING_RELEASE_VERIFIED_RESEARCH_ROUTE"
    assert route["current_research_path"] == f"/research/{CID}"
    assert route["canonical_enquiry_post_path"] == "/api/research/enquiry"
    assert route["canonical_event_post_path"] == "/api/research/event"
    assert route["source_asset_id"] == ASSET
    assert route["form_reply_not_marketing_subscription"] is True
    assert route["active_proof_experience_published"] is False
    assert route["live_http_verified_here"] is False


def test_first_party_enquiry_validator_and_existing_admission_work_together(monkeypatch):
    route = released_route(monkeypatch)
    class FixtureRepository:
        def __init__(self):
            self.rows = []
        def enquiry(self, obj):
            self.rows.append(obj)
            return ENQUIRY_ID
    repo = FixtureRepository()
    data = {
        "campaign_id": CID, "asset_id": ASSET,
        "reply_email": "REAL_FIXTURE_ONLY@example.com",
        "research_question": "Can you show a verified acceptance and territory fit check?",
    }
    receipt = accept("enquiry", data, marketing(), repo)
    assert receipt["accepted"] is True
    assert receipt["receipt_id"] == ENQUIRY_ID
    assert repo.rows[0]["reply_email"] == "real_fixture_only@example.com"
    response = join(route, [enq()], [crm()], [outcome()], closed=True)
    assert response["accepted_first_party_enquiry_receipts"] == 1
    assert response["authenticated_crm_enquiries_linked"] == 1
    assert response["observed_paid_buyers"] == 1
    assert response["recognized_order_count"] == 1
    assert response["recognized_campaign_revenue_cents"] == 10000
    assert response["realized_campaign_gp_cents"] == 7500
    assert response["channel_or_roi_causal_lift_proven"] is False
    dumped = json.dumps(response)
    for forbidden in (ENQUIRY_ID, PROSPECT_ID, TENANT_ID, ORDER_ID, "real_fixture_only"):
        assert forbidden not in dumped
    assert response["new_crm_or_payment_writer_created"] is False


def test_absent_canonical_source_rows_are_unknown_not_zero(monkeypatch):
    route = released_route(monkeypatch)
    packet = join(route)
    for key in ("accepted_first_party_enquiry_receipts",
                "authenticated_crm_enquiries_linked",
                "observed_paid_buyers",
                "recognized_order_count",
                "recognized_campaign_revenue_cents",
                "realized_campaign_gp_cents"):
        assert packet[key] is None


def test_enquiry_and_crm_can_be_proved_before_payment_source_is_connected(monkeypatch):
    packet = join(released_route(monkeypatch), [enq()], [crm()])
    assert packet["accepted_first_party_enquiry_receipts"] == 1
    assert packet["authenticated_crm_enquiries_linked"] == 1
    assert packet["observed_paid_buyers"] is None
    assert packet["recognized_campaign_revenue_cents"] is None


def test_finance_rows_do_not_make_economic_totals_without_closed_window(monkeypatch):
    result = join(released_route(monkeypatch), [enq()], [crm()], [outcome()])
    assert result["observed_paid_buyers"] == 1
    assert result["recognized_order_count"] is None
    assert result["recognized_campaign_revenue_cents"] is None
    assert result["realized_campaign_gp_cents"] is None
    assert result["finance_receipt_window_closed"] is False


def test_missing_actual_cost_source_cannot_create_realized_gp(monkeypatch):
    row = outcome(actual_cost_verified=False, actual_cost_cents=None,
                  realized_gp_cents=None)
    packet = join(released_route(monkeypatch), [enq()], [crm()], [row], closed=True)
    assert packet["recognized_campaign_revenue_cents"] == 10000
    assert packet["realized_campaign_gp_cents"] is None


def test_payment_not_fulfilled_is_neither_recognized_revenue_nor_profit(monkeypatch):
    row = outcome(fulfilment_verified=False, delivered_at=None,
                  recognized_revenue_event_verified=False,
                  recognized_at=None, actual_cost_verified=False,
                  recognized_revenue_cents=None, actual_cost_cents=None,
                  realized_gp_cents=None)
    packet = join(released_route(monkeypatch), [enq()], [crm()], [row], closed=True)
    assert packet["observed_paid_buyers"] == 1
    assert packet["recognized_order_count"] == 0
    assert packet["recognized_campaign_revenue_cents"] == 0
    assert packet["realized_campaign_gp_cents"] is None


@pytest.mark.parametrize("change", [
    {"release_website_binding_verified": False},
    {"canonical_intake_readback_verified": False},
    {"original_same_origin_admission_verified": False},
    {"asset_id": "other:landing"},
    {"campaign_id": "campaign_"+"f"*24},
    {"receipt_id": "not-a-uuid"},
    {"received_at": NOW+timedelta(hours=3)},
])
def test_untrusted_or_mismatched_first_party_readback_is_rejected(monkeypatch, change):
    with pytest.raises(CampaignIntelligenceHeld):
        join(released_route(monkeypatch), [enq(**change)])


@pytest.mark.parametrize("change", [
    {"exact_intake_to_prospect_link_verified": False},
    {"authenticated_tenant_reader_verified": False},
    {"enquiry_receipt_id": "671e45d0-3802-4cbc-975b-97edc1495080"},
    {"campaign_id": "campaign_"+"b"*24},
    {"recorded_at": START-timedelta(minutes=1)},
])
def test_false_crm_linkage_does_not_upgrade_enquiry_to_customer(monkeypatch, change):
    with pytest.raises(CampaignIntelligenceHeld):
        join(released_route(monkeypatch), [enq()], [crm(**change)])


@pytest.mark.parametrize("change", [
    {"payment_settlement_verified": False},
    {"canonical_order_prospect_join_verified": False},
    {"prospect_id": "671e45d0-3802-4cbc-975b-97edc1495080"},
    {"finance_event_key": "invalid"},
    {"paid_at": START-timedelta(minutes=1)},
    {"delivered_at": START+timedelta(minutes=1)},
    {"recognized_at": START+timedelta(minutes=45)},
    {"recognized_revenue_cents": "10000"},
    {"realized_gp_cents": 99999},
    {"actual_cost_cents": -1},
])
def test_forged_or_inconsistent_payment_and_profit_are_held(monkeypatch, change):
    with pytest.raises(CampaignIntelligenceHeld):
        join(released_route(monkeypatch), [enq()], [crm()], [outcome(**change)], closed=True)


def test_duplicate_enquiries_crm_and_orders_prevent_double_count(monkeypatch):
    route = released_route(monkeypatch)
    for incoming, links, outcomes in (
        ([enq(), enq()], [crm()], [outcome()]),
        ([enq()], [crm(), crm()], [outcome()]),
        ([enq()], [crm()], [outcome(), outcome()]),
    ):
        with pytest.raises(CampaignIntelligenceHeld, match="DUPLICATE"):
            join(route, incoming, links, outcomes, closed=True)


def test_downstream_finance_without_upstream_crm_is_never_attributed(monkeypatch):
    route = released_route(monkeypatch)
    with pytest.raises(CampaignIntelligenceHeld):
        join(route, [enq()], None, [outcome()], closed=True)
    with pytest.raises(CampaignIntelligenceHeld):
        join(route, None, [crm()], None)


def test_route_must_come_from_existing_release_approval_not_blog_slug(monkeypatch):
    route = released_route(monkeypatch)
    for modified in (
        {**route, "source_asset_id": "another_asset"},
        {**route, "canonical_enquiry_post_path": "/no-real-endpoint"},
        {**route, "status": "PRIVATE_OPERATOR_PREVIEW_READY"},
    ):
        with pytest.raises(CampaignIntelligenceHeld):
            join(modified, [enq()])


def test_no_real_release_means_no_executable_research_route(monkeypatch):
    monkeypatch.setattr("empire_os.owned_campaign_release.load_release",
                        lambda *, root: None)
    hold = review_released_research_route(root=Path("/tmp"), campaign_id=CID, now=NOW)
    assert hold["status"] == "HOLD_UNVERIFIED_WEBSITE_RELEASE"
    assert hold["canonical_enquiry_post_path"] is None
    with pytest.raises(CampaignIntelligenceHeld):
        join(hold, [enq()])


def test_existing_full_funnel_accepts_exact_first_party_to_finance_chain(monkeypatch):
    route = released_route(monkeypatch)
    reply = review_authenticated_campaign_intelligence(
        now=NOW, released_research_route=route,
        released_research_repository_root=Path("/repo-fixture"),
        source_enquiry_receipts=(enq(),),
        source_crm_enquiry_links=(crm(),),
        source_finance_outcome_receipts=(outcome(),),
        finance_outcome_window_complete=True,
    )
    chain = reply["real_first_party_conversion_journey"]
    assert chain["recognized_campaign_revenue_cents"] == 10000
    assert chain["realized_campaign_gp_cents"] == 7500
    assert reply["live_recipient_contact_or_messages"] is False
    assert reply["database_writes"] is False


def test_full_funnel_without_owner_receipts_does_not_imply_no_customers():
    reply = review_authenticated_campaign_intelligence(now=NOW)
    assert reply["real_first_party_conversion_journey"] is None


def test_readonly_research_release_inventory_reports_signed_paths_without_sales_claims(monkeypatch):
    from scripts.review_tam_full_funnel_strategy_20261020 import (
        review_existing_research_release_entrypoints,
    )
    # This fixture checks integration with the original release reader, not
    # a second publisher, CRM or payment feed.
    valid = marketing()
    monkeypatch.setattr(
        "empire_os.owned_campaign_release.load_release",
        lambda *, root: valid,
    )
    report = review_existing_research_release_entrypoints(Path("/repo-fixture"))
    assert report["verified_research_pages"] == 1
    assert report["existing_enquiry_route"] == "/api/research/enquiry"
    assert report["published_private_value_experiences"] == 0
    assert report["real_enquiries_observed"] is None
    assert report["real_payments_observed"] is None
    assert report["actual_http_verified_in_this_report"] is False


def test_readonly_release_inventory_missing_release_returns_unknown_not_zero(monkeypatch):
    from scripts.review_tam_full_funnel_strategy_20261020 import (
        review_existing_research_release_entrypoints,
    )
    monkeypatch.setattr(
        "empire_os.owned_campaign_release.load_release",
        lambda *, root: None,
    )
    report = review_existing_research_release_entrypoints(Path("/repo-fixture"))
    assert report["release_status"] == "HOLD_NO_VERIFIED_SIGNED_RELEASE"
    assert report["verified_research_pages"] is None
    assert report["real_enquiries_observed"] is None
