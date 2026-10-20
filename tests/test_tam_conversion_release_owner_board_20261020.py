"""Read-only conversion release owner board. Fixture counts are NOT live leads."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import pytest

from empire_os.commercial_product_catalog import summarize_catalog
from scripts.probe_owned_research_enquiry_aggregate_readonly import classify
from scripts.review_tam_full_funnel_strategy_20261020 import (
    read_existing_commercial_catalog_readonly,
    review_commercial_catalog_for_conversion,
    review_existing_enquiry_aggregate_for_conversion,
    review_conversion_owner_release_board,
)

NOW = datetime(2026, 10, 20, 12, 52, tzinfo=timezone.utc)


def product(ready=True):
    return {
        "product_code": "offline_fixture_only",
        "active": True,
        "catalog_state": "VERIFIED" if ready else "UNKNOWN",
        "version_state": "VERIFIED" if ready else "PENDING",
        "price_basis": {"state": "VERIFIED", "amount_cents": 12345,
                        "currency": "GBP", "unit": "one_time"},
        "acquisition_cost_basis": {"state": "VERIFIED"},
        "fulfilment_cost_basis": {"state": "VERIFIED"},
        "margin_policy": {"state": "VERIFIED"},
    }


def catalog():
    packet = summarize_catalog([product(True), product(False)])
    packet["generated_at"] = NOW.isoformat()
    return packet


def enquiry(**overrides):
    counts = {
        "research_enquiry_rows": 0,
        "research_campaigns_with_enquiries": 0,
        "enquiry_marketing_or_outbound_hold_violations": 0,
        "server_received_submission_events": 0,
        "browser_page_view_events": 12,
        "browser_cta_click_events": 5,
        "browser_enquiry_started_events": 1,
        "invalid_submission_events": 0,
    }
    counts.update(overrides)
    return classify(privileged=True, returncode=0, stdout=json.dumps(counts))


def review_enquiries(packet=None, *, verified=True):
    return review_existing_enquiry_aggregate_for_conversion(
        enquiry() if packet is None else packet,
        owner_operator_attestation_verified=verified,
        source_observed_at=NOW, now=NOW,
    )


def test_catalog_counts_independently_recomputed_not_claimed_buyer_fit():
    report = review_commercial_catalog_for_conversion(catalog(), now=NOW)
    assert report["source_status"] == "CURRENT_CATALOG_PRODUCT_TERMS_REVIEWED"
    assert report["products_catalogued"] == 2
    assert report["active_products"] == 2
    assert report["verified_commercial_terms_products"] == 1
    assert report["buyer_specific_value_offer_match_verified"] is False
    assert report["delivery_capacity_or_start_date_verified"] is False
    assert report["pricing_or_terms_published_by_campaign_owner"] is False
    assert report["payment_or_revenue_inferred"] is False
    assert "offline_fixture_only" not in json.dumps(report)
    assert "12345" not in json.dumps(report)


@pytest.mark.parametrize("change", [
    {"schema_version": "unknown"},
    {"execution_authority": "send"},
    {"actual_revenue": True},
    {"generated_at": "2026-09-11T12:00:00+00:00"},
    {"generated_at": "2026-10-21T12:00:00+00:00"},
    {"generated_at": "none"},
    {"product_count": 3},
    {"active_count": 100},
    {"binding_terms_ready_count": 100},
    {"binding_terms_ready_count": True},
])
def test_catalog_mismatched_or_stale_meta_cannot_authorize_quote(change):
    data = catalog()
    data.update(change)
    outcome = review_commercial_catalog_for_conversion(data, now=NOW)
    assert outcome["source_status"] == "HOLD_MISSING_STALE_OR_UNTRUSTED_CATALOG"
    assert outcome["verified_commercial_terms_products"] is None


def test_catalog_bad_record_shape_held_without_leaking_product_details():
    data = catalog()
    data["products"].append("someone@private.test")
    data["product_count"] = 3
    outcome = review_commercial_catalog_for_conversion(data, now=NOW)
    assert outcome["products_catalogued"] is None
    assert "someone@private.test" not in json.dumps(outcome)


def test_catalog_reader_uses_fixed_local_file_without_symlink(tmp_path):
    p = tmp_path / "runtime/commercial_catalog/latest.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(catalog()))
    p.chmod(0o640)
    assert read_existing_commercial_catalog_readonly(tmp_path)["product_count"] == 2
    external = tmp_path / "external-file"
    external.write_text(json.dumps(catalog()))
    p.unlink()
    p.symlink_to(external)
    assert read_existing_commercial_catalog_readonly(tmp_path) == {}
    p.unlink()
    p.write_text(json.dumps(catalog()))
    p.chmod(0o666)
    assert read_existing_commercial_catalog_readonly(tmp_path) == {}


def test_unprivileged_source_observation_stays_unknown_not_zero():
    held = classify(privileged=False, returncode=0,
                    stdout=json.dumps({"research_enquiry_rows": 0}))
    result = review_enquiries(held, verified=True)
    assert result["source_status"] == "HOLD_UNTRUSTED_AGGREGATE_EVIDENCE"
    assert result["accepted_research_enquiries"] is None
    unverified = review_enquiries(enquiry(), verified=False)
    assert unverified["source_status"] == "AWAIT_AUTHORIZED_DATABASE_OPERATOR"
    assert unverified["page_view_events_not_unique_visitors"] is None


def test_existing_count_only_source_can_be_ingested_without_cold_leads():
    response = review_enquiries(
        enquiry(research_enquiry_rows=3,
                research_campaigns_with_enquiries=2,
                server_received_submission_events=3)
    )
    assert response["source_status"] == "AUTHORIZED_AGGREGATE_RESEARCH_EVIDENCE_REVIEWED"
    assert response["accepted_research_enquiries"] == 3
    assert response["page_view_events_not_unique_visitors"] == 12
    assert response["cta_click_events_not_unique_buyers"] == 5
    assert response["real_unique_visitor_to_lead_rate"] is None
    assert response["exact_campaign_conversions"] is None
    assert response["crm_matched_buyers"] is None
    assert response["sales_or_payment_inferred"] is False
    assert response["first_party_marketing_permission_inferred"] is False


def test_authenticated_aggregate_zero_is_distinct_from_absent_reader():
    result = review_enquiries(enquiry())
    assert result["source_status"] == "AUTHORIZED_AGGREGATE_RESEARCH_EVIDENCE_REVIEWED"
    assert result["accepted_research_enquiries"] == 0
    assert result["page_view_events_not_unique_visitors"] == 12
    assert result["sales_or_payment_inferred"] is False


def test_bogus_privileged_counts_and_evidence_consistency_fail_closed():
    valid = enquiry(research_enquiry_rows=3, research_campaigns_with_enquiries=1,
                    server_received_submission_events=3)
    assert valid["status"] == "RESEARCH_ENQUIRIES_OBSERVED_SEPARATE_FROM_SALES"
    for change in (
        {"research_enquiry_rows": 2},
        {"research_campaigns_with_enquiries": 4},
        {"research_enquiry_rows": True},
        {"enquiry_marketing_or_outbound_hold_violations": 1},
        {"contact_data_disclosed": True},
        {"customer_identifiers_disclosed": True},
        {"new_privileges_granted": True},
        {"read_only": False},
        {"status": "NO_RESEARCH_ENQUIRIES_IN_CANONICAL_SOURCE"},
        {"execution_authority": "SEND"},
    ):
        bad = {**valid, **change}
        response = review_enquiries(bad)
        assert response["source_status"] == "HOLD_UNTRUSTED_AGGREGATE_EVIDENCE"
        assert response["accepted_research_enquiries"] is None


def board(*, release=True, owner_enquiry=False, closed_finance=False):
    return review_conversion_owner_release_board(
        release={"release_status": (
            "EXISTING_RELEASED_RESEARCH_PATHS_VERIFIED" if release else "HELD"
        )},
        catalog=review_commercial_catalog_for_conversion(catalog(), now=NOW),
        research_aggregate=review_enquiries(enquiry(), verified=owner_enquiry),
        customer_money_join=({
            "finance_receipt_window_closed": True,
            "revenue_attribution_basis":
                "EXACT_INTAKE_CRM_ORDER_JOIN_WITH_CLOSED_FINANCE_WINDOW",
            "authenticated_crm_enquiries_linked": 1,
        } if closed_finance else None),
    )


def test_five_owner_board_tasks_are_precise_and_not_automatic_assignments():
    result = board()
    assert result["tasks_total"] == 5
    assert len(result["tasks"]) == 5
    assert [x["owner"] for x in result["tasks"]] == [
        "existing_flagship_website_owner",
        "existing_commercial_catalog_and_fulfilment_owner",
        "existing_seo_research_enquiry_database_owner",
        "existing_tenant_crm_and_sales_owner",
        "existing_finance_and_revenue_owner",
    ]
    assert result["website_source_verified"] is True
    assert result["real_enquiry_source_available"] is False
    assert result["revenue_and_cost_receipts_joined"] is False
    assert result["buyer_specific_offer_terms_and_timing_verified"] is False
    assert result["automated_handoff_performed"] is False
    assert result["production_action_authority"] == "NONE"


def test_research_enquiry_source_and_finance_handoff_can_progress_separately():
    result = board(owner_enquiry=True)
    assert result["real_enquiry_source_available"] is True
    assert result["revenue_and_cost_receipts_joined"] is False
    result = board(owner_enquiry=True, closed_finance=True)
    assert result["real_enquiry_source_available"] is True
    assert result["revenue_and_cost_receipts_joined"] is True
    assert result["owner_approved_private_value_page_published"] is False
    assert result["production_action_authority"] == "NONE"


def test_no_signed_release_is_not_a_published_site_claim():
    result = board(release=False)
    assert result["website_source_verified"] is False
    assert result["tasks"][0]["status"] == "RELEASE_EVIDENCE_REQUIRED"
    assert result["owner_approved_private_value_page_published"] is False


def test_research_counts_cannot_be_claimed_live_from_old_operator_output():
    for observed in (None, NOW-timedelta(days=2), NOW+timedelta(minutes=1)):
        result = review_existing_enquiry_aggregate_for_conversion(
            enquiry(), owner_operator_attestation_verified=True,
            source_observed_at=observed, now=NOW,
        )
        assert result["source_status"] == "HOLD_UNVERIFIED_OR_STALE_AGGREGATE_CAPTURE"
        assert result["accepted_research_enquiries"] is None
        assert result["sales_or_payment_inferred"] is False


def test_owner_handoff_is_compact_no_pii_and_truthfully_unknown_sources():
    from scripts.review_tam_full_funnel_strategy_20261020 import (
        export_conversion_owner_handoff,
    )
    source = {
        "conversion_release_owner_board": board(),
        "existing_catalog_conversion_readiness":
            review_commercial_catalog_for_conversion(catalog(), now=NOW),
        "research_enquiry_aggregate_conversion_readiness":
            review_existing_enquiry_aggregate_for_conversion(
                None, owner_operator_attestation_verified=False,
            ),
        "existing_first_party_research_release": {
            "verified_research_pages": 5,
            "existing_enquiry_route": "/api/research/enquiry",
        },
        "decision_intelligence": {
            "real_first_party_conversion_journey": None,
        },
    }
    handoff = export_conversion_owner_handoff(source, now=NOW)
    assert handoff["website"]["signed_research_route_count"] == 5
    assert handoff["catalog"]["binding_terms_ready_count"] == 1
    assert handoff["first_party_interest"]["authentic_research_enquiries_observed"] is None
    assert handoff["crm"]["authenticated_enquiry_prospect_link_count"] is None
    assert handoff["finance"]["realized_campaign_profit_cents"] is None
    assert handoff["execution_authority"] == "NONE"
    assert len(handoff["existing_owner_actions"]) == 5
    assert handoff["messages_sent"] is False
    assert handoff["database_writes"] is False
    serialized = json.dumps(handoff)
    for banned in ("offline_fixture_only", "12345", "reply_email",
                   "research_question", "prospect_id", "DSN",
                   "personal_email"):
        assert banned not in serialized


def test_owner_handoff_updates_only_after_actual_owner_supplied_receipts():
    from scripts.review_tam_full_funnel_strategy_20261020 import (
        export_conversion_owner_handoff,
    )
    source = {
        "conversion_release_owner_board": board(closed_finance=True),
        "existing_catalog_conversion_readiness":
            review_commercial_catalog_for_conversion(catalog(), now=NOW),
        "research_enquiry_aggregate_conversion_readiness":
            review_enquiries(enquiry(), verified=True),
        "existing_first_party_research_release": {
            "verified_research_pages": 2,
            "existing_enquiry_route": "/api/research/enquiry",
        },
        "decision_intelligence": {
            "real_first_party_conversion_journey": {
                "authenticated_crm_enquiries_linked": 1,
                "recognized_campaign_revenue_cents": 2000,
                "realized_campaign_gp_cents": 500,
            },
        },
    }
    handoff = export_conversion_owner_handoff(source, now=NOW)
    assert handoff["first_party_interest"]["authentic_research_enquiries_observed"] == 0
    assert handoff["crm"]["authenticated_enquiry_prospect_link_count"] == 1
    assert handoff["finance"]["recognized_campaign_revenue_cents"] == 2000
    assert handoff["finance"]["realized_campaign_profit_cents"] == 500
    assert handoff["automatic_tasks_reassigned"] is False
    assert handoff["execution_authority"] == "NONE"
