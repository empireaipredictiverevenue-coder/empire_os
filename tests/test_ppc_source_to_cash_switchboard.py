"""Canonical PPC switchboard links existing traffic, CRO and cash reviews.

All amounts/call counts in this file are SYNTHETIC TEST FIXTURES, never actual
Empire results. No media, website, buyer route, agent or DB is activated.
"""
from __future__ import annotations

from copy import deepcopy
import json
from datetime import datetime, timezone
from pathlib import Path
import pytest

from empire_os.competitor_call_traffic_sources import SOURCE, build_registry
from empire_os.ppc_switchboard_adapter import review_pay_per_call_source_to_cash
from empire_os.conversion_intelligence import HOMEOWNER_CALL_STAGES
from empire_os.call_unit_economics_review import REQUIRED_FIELDS, REQUIRED_RECEIPTS

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 27, 15, 0, tzinfo=timezone.utc)


def original_registry():
    return build_registry(
        json.loads((ROOT / SOURCE).read_text(encoding="utf-8")), now=NOW
    )


def test_all_15_operator_research_sources_have_safe_funnel_preview():
    registry = original_registry()
    all_sources = (
        registry["free_or_earned"] + registry["paid_research_only"]
        + registry["excluded"]
    )
    assert len(all_sources) == 15
    for channel in all_sources:
        r = review_pay_per_call_source_to_cash(
            registry=registry,
            source_id=channel["id"],
            cohort_ref="OWNER_COHORT_NOT_YET_OBSERVED",
        )
        assert r["original_source_status"] == channel["status"]
        assert r["measured_funnel_stages"] == 0
        assert r["reviewed_cash_margin_cents"] is None
        assert r["traffic_or_ad_spend_authorized"] is False
        assert r["revenue_recognized"] is False
        assert r["execution_authority"] == "none"
    assert review_pay_per_call_source_to_cash(
        registry=registry, source_id="google_lsa",
        cohort_ref="OWNER_COHORT_NOT_YET_OBSERVED",
    )["next_task"] == "DO_NOT_USE_POLICY_EXCLUDED_SOURCE"


def synthetic_aggregate():
    # Invented for tests ONLY; values must never feed actual revenue.
    counts = dict(zip(HOMEOWNER_CALL_STAGES, (100, 70, 50, 30, 20, 18)))
    funnel_refs = {
        key: "synthetic-test-evidence:" + key for key in HOMEOWNER_CALL_STAGES
    }
    cash = {
        "provider_connected_calls": 30,
        "buyer_accepted_payable_calls": 20,
        "independently_settled_calls": 18,
        "bank_verified_cash_received_cents": 108000,
        "actual_paid_media_cost_cents": 0,
        "actual_publisher_cost_cents": 12000,
        "actual_processing_cost_cents": 4000,
        "actual_refund_or_chargeback_cost_cents": 1000,
    }
    receipts = {
        key: "synthetic-test-receipt:" + key for key in REQUIRED_RECEIPTS
    }
    return counts, funnel_refs, cash, receipts


def test_reuses_both_original_specialists_on_single_cohort_proposal():
    counts, refs, cash, receipts = synthetic_aggregate()
    r = review_pay_per_call_source_to_cash(
        registry=original_registry(), source_id="organic_search",
        cohort_ref="SYNTHETIC_COHORT_NOT_EARNED_CASH",
        funnel_counts=counts, funnel_evidence_refs=refs,
        finance_values=cash, finance_receipt_refs=receipts,
        source_lineage_verified=True,
        buyer_source_approval_verified=True,
        buyer_source_approval_ref="synthetic-buyer-source-owner",
        independent_finance_verified=True, same_cohort_verified=True,
    )
    assert r["measured_funnel_stages"] >= 1
    assert r["existing_conversion_specialist_review"][
        "first_reviewable_bottleneck"] is not None
    assert r["reviewed_cash_margin_cents"] == 91000
    assert r["profitability_reviewable_with_owner_assertions"]
    assert r["original_owner_approval_document_authenticated_by_this_view"] is False
    assert r["next_task"] == "REVIEW_CRO_HYPOTHESIS_AGAINST_VERIFIED_CASH_MARGIN"
    assert r["traffic_or_ad_spend_authorized"] is False
    assert r["automated_optimisation_enabled"] is False
    assert not r["revenue_recognized"]


@pytest.mark.parametrize("missing", [
    "source_lineage_verified", "same_cohort_verified",
    "buyer_source_approval_verified", "independent_finance_verified",
])
def test_missing_owner_evidence_never_yields_actual_margin(missing):
    counts, refs, cash, receipts = synthetic_aggregate()
    flags = dict(source_lineage_verified=True, buyer_source_approval_verified=True,
                 independent_finance_verified=True, same_cohort_verified=True)
    flags[missing] = False
    r = review_pay_per_call_source_to_cash(
        registry=original_registry(), source_id="organic_search",
        cohort_ref="SYNTHETIC_COHORT_NOT_EARNED_CASH",
        funnel_counts=counts, funnel_evidence_refs=refs,
        finance_values=cash, finance_receipt_refs=receipts,
        buyer_source_approval_ref="synthetic-buyer-source-owner", **flags,
    )
    assert r["reviewed_cash_margin_cents"] is None
    assert not r["profitability_reviewable_with_owner_assertions"]


def test_prohibited_google_lsa_cannot_become_billable_even_with_owner_flags():
    counts, refs, cash, receipts = synthetic_aggregate()
    r = review_pay_per_call_source_to_cash(
        registry=original_registry(), source_id="google_lsa",
        cohort_ref="SYNTHETIC_COHORT_NOT_EARNED_CASH",
        funnel_counts=counts, funnel_evidence_refs=refs,
        finance_values=cash, finance_receipt_refs=receipts,
        source_lineage_verified=True, buyer_source_approval_verified=True,
        buyer_source_approval_ref="synthetic-buyer-source-owner",
        independent_finance_verified=True, same_cohort_verified=True,
    )
    assert r["source_policy_excluded"]
    assert r["reviewed_cash_margin_cents"] is None
    assert r["next_task"] == "DO_NOT_USE_POLICY_EXCLUDED_SOURCE"


def test_conflicting_cro_vs_finance_counts_rejected():
    counts, refs, cash, receipts = synthetic_aggregate()
    cash["provider_connected_calls"] = 31
    with pytest.raises(ValueError, match="disagree on cohort"):
        review_pay_per_call_source_to_cash(
            registry=original_registry(), source_id="organic_search",
            cohort_ref="SYNTHETIC_COHORT_NOT_EARNED_CASH",
            funnel_counts=counts, funnel_evidence_refs=refs,
            finance_values=cash, finance_receipt_refs=receipts,
        )


@pytest.mark.parametrize("alter", [
    lambda r: r.update(media_spend_authorized=True),
    lambda r: r.update(source_count=16),
    lambda r: r["free_or_earned"][0].update(eligible_for_immediate_ad_spend=True),
    lambda r: r["paid_research_only"].append(r["paid_research_only"][0]),
])
def test_untrusted_source_registry_does_not_promote_campaign(alter):
    r = deepcopy(original_registry())
    alter(r)
    with pytest.raises(ValueError):
        review_pay_per_call_source_to_cash(
            registry=r, source_id="organic_search",
            cohort_ref="ORIGINAL_OWNER_NO_COHORT_YET",
        )


def test_unknown_channel_and_invalid_buyer_source_approval_rejected():
    r = original_registry()
    with pytest.raises(ValueError):
        review_pay_per_call_source_to_cash(
            registry=r, source_id="unverified_tiktok_ads",
            cohort_ref="ORIGINAL_OWNER_NO_COHORT_YET",
        )
    with pytest.raises(ValueError):
        review_pay_per_call_source_to_cash(
            registry=r, source_id="organic_search",
            cohort_ref="ORIGINAL_OWNER_NO_COHORT_YET",
            buyer_source_approval_verified=True,
        )


def test_founder_original_feed_consumes_all_15_research_sources(tmp_path):
    from empire_os.competitor_call_channel_atlas import SOURCE as ATLAS, build_atlas
    from empire_os.competitor_intelligence_feed import build_feed_runtime
    target = tmp_path / "runtime/competitive_intelligence"
    target.mkdir(parents=True)
    (target / "competitor_intelligence_feed_latest.json").write_text(
        '{"canonical_company_count":14}'
    )
    atlas = build_atlas(json.loads((ROOT / ATLAS).read_text()), now=NOW)
    (target / "call_acquisition_atlas_latest.json").write_text(json.dumps(atlas))
    registry = original_registry()
    (target / "call_traffic_source_registry_latest.json").write_text(
        json.dumps(registry)
    )
    result = build_feed_runtime(tmp_path)
    assert result["canonical_company_count"] == 14
    owner = result["call_acquisition_intelligence"]["source_to_cash_growth_research"]
    assert owner["available"]
    assert owner["original_traffic_source_count"] == 15
    assert owner["organic_research_count"] == 7
    assert owner["paid_unfunded_count"] == 7
    assert owner["policy_excluded_count"] == 1
    assert owner["original_cro_review_available"] is False
    assert owner["original_call_loss_review_available"] is False
    assert owner["first_measurement_action"] == (
        "ORIGINAL_ANALYTICS_OWNER_SOURCE_TO_SESSION_COHORT"
    )
    assert owner["ranked_source_research_queue"][0]["source_id"] == "organic_search"
    excluded = owner["ranked_source_research_queue"][-1]
    assert excluded["source_id"] == "google_lsa"
    assert excluded["policy_excluded"] is True
    assert excluded["next_task"] == "DO_NOT_USE_POLICY_EXCLUDED_SOURCE"
    assert all(row["measured_stage_count"] == 0
               and row["cash_margin_cents"] is None
               and row["activation_authorized"] is False
               for row in owner["ranked_source_research_queue"])
    assert owner["no_new_service_database_or_agent"] is True
    assert owner["execution_authority"] == "none"
    registry["paid_research_only"][0]["eligible_for_immediate_ad_spend"] = True
    (target / "call_traffic_source_registry_latest.json").write_text(
        json.dumps(registry)
    )
    altered = build_feed_runtime(tmp_path)
    assert altered["call_acquisition_intelligence"][
        "source_to_cash_growth_research"]["available"] is False


def test_source_registry_cannot_impersonate_live_paid_approval():
    r = original_registry()
    r["paid_research_only"][0]["status"] = "APPROVED_LIVE"
    with pytest.raises(ValueError):
        review_pay_per_call_source_to_cash(
            registry=r, source_id="google_search_ads",
            cohort_ref="ORIGINAL_OWNER_NO_COHORT_YET",
        )

def test_paid_source_even_with_owner_asserted_positive_cohort_cannot_spend():
    counts, refs, cash, receipts = synthetic_aggregate()
    r = review_pay_per_call_source_to_cash(
        registry=original_registry(), source_id="google_search_ads",
        cohort_ref="SYNTHETIC_PAID_CHANNEL_NOT_LIVE",
        funnel_counts=counts, funnel_evidence_refs=refs,
        finance_values=cash, finance_receipt_refs=receipts,
        source_lineage_verified=True,
        buyer_source_approval_verified=True,
        buyer_source_approval_ref="synthetic-buyer-source-owner",
        independent_finance_verified=True, same_cohort_verified=True,
    )
    assert r["profitability_reviewable_with_owner_assertions"]
    assert r["original_source_status"] == "PAID_UNFUNDED_RESEARCH_ONLY"
    assert r["traffic_or_ad_spend_authorized"] is False
    assert r["automated_optimisation_enabled"] is False
    assert r["new_agent_database_or_timer_created"] is False


def synthetic_original_call_loss(*, source="organic_search",
                                cohort="SYNTHETIC_COHORT_NOT_EARNED_CASH",
                                original_owner_authorized=True):
    from empire_os.competitor_call_loss_readiness import (
        COUNTS, NO_CONNECT_REASONS, NO_HUMAN_REASONS, NO_PAYABLE_REASONS,
        evaluate_approved_call_cohort,
    )
    counts = dict(zip(COUNTS, (40, 30, 25, 20, 18)))
    no_connect = {key: 0 for key in NO_CONNECT_REASONS}
    no_connect["TARGET_NO_ANSWER"] = 10
    no_human = {key: 0 for key in NO_HUMAN_REASONS}
    no_human["IVR_OR_QUEUE_ABANDON"] = 5
    no_payable = {key: 0 for key in NO_PAYABLE_REASONS}
    no_payable["WRONG_SERVICE"] = 5
    return evaluate_approved_call_cohort(
        source_id=source, cohort_ref=cohort, counts=counts,
        refs={key: "synthetic-owner-receipt:" + key for key in COUNTS},
        no_connect_reasons=no_connect, no_human_reasons=no_human,
        no_payable_reasons=no_payable,
        original_owner_authorized=original_owner_authorized,
        source_lineage_verified=True, buyer_acceptance_verified=True,
        unique_inbound_terminal_dispositions_verified=True,
    )


def test_existing_original_call_loss_separates_queue_and_buyer_rejection():
    counts, refs, cash, receipts = synthetic_aggregate()
    result = review_pay_per_call_source_to_cash(
        registry=original_registry(), source_id="organic_search",
        cohort_ref="SYNTHETIC_COHORT_NOT_EARNED_CASH",
        funnel_counts=counts, funnel_evidence_refs=refs,
        finance_values=cash, finance_receipt_refs=receipts,
        approved_call_loss_cohort=synthetic_original_call_loss(),
        source_lineage_verified=True, same_cohort_verified=True,
        buyer_source_approval_verified=True,
        buyer_source_approval_ref="synthetic-buyer-source-owner",
        independent_finance_verified=True,
    )
    qa = result["existing_original_call_loss_review"]
    assert qa["available"] is True
    assert qa["human_buyer_answers"] == 25
    assert qa["calls_lost_before_target_connection"] == 10
    assert qa["target_connected_without_human_answer"] == 5
    assert qa["human_answered_but_not_payable"] == 5
    assert qa["rejection_reason_groups"]["no_connect_reasons"]["TARGET_NO_ANSWER"] == 10
    assert qa["rejection_reason_groups"][
        "target_connected_but_not_human_answered_reasons"]["IVR_OR_QUEUE_ABANDON"] == 5
    assert result["next_task"] == "INVESTIGATE_VERIFIED_TARGET_CONNECTED_WITHOUT_HUMAN_ANSWER"
    assert result["reviewed_cash_margin_cents"] == 91000
    assert result["traffic_or_ad_spend_authorized"] is False


@pytest.mark.parametrize("change", [
    lambda x: x.update(source_id="youtube_organic"),
    lambda x: x.update(cohort_ref="DIFFERENT_COHORT"),
    lambda x: x.update(execution_authority="LIVE"),
    lambda x: x.update(raw_ringba_target_attempt_counters_not_used=False),
    lambda x: x.update(buyer_human_answered_calls=31),
    lambda x: x.update(provider_target_connected_calls=31),
    lambda x: x.update(caller_ani="+18880000000"),
    lambda x: x["target_connected_but_not_human_answered_reasons"].update(
        IVR_OR_QUEUE_ABANDON=999),
])
def test_bad_owner_call_loss_proof_fails_closed(change):
    loss = deepcopy(synthetic_original_call_loss())
    change(loss)
    counts, refs, cash, receipts = synthetic_aggregate()
    with pytest.raises(ValueError):
        review_pay_per_call_source_to_cash(
            registry=original_registry(), source_id="organic_search",
            cohort_ref="SYNTHETIC_COHORT_NOT_EARNED_CASH",
            funnel_counts=counts, finance_values=cash,
            approved_call_loss_cohort=loss,
            source_lineage_verified=True, same_cohort_verified=True,
        )


def test_unapproved_or_unattributed_call_loss_keeps_unknown_metrics():
    for truth in (synthetic_original_call_loss(original_owner_authorized=False),
                  synthetic_original_call_loss()):
        result = review_pay_per_call_source_to_cash(
            registry=original_registry(), source_id="organic_search",
            cohort_ref="SYNTHETIC_COHORT_NOT_EARNED_CASH",
            approved_call_loss_cohort=truth,
            source_lineage_verified=False, same_cohort_verified=False,
        )
        qa = result["existing_original_call_loss_review"]
        assert qa["available"] is False
        assert qa["human_buyer_answers"] is None
        assert qa["target_connected_without_human_answer"] is None
        assert qa["rejection_reason_groups"] is None
        assert result["reviewed_cash_margin_cents"] is None
        assert result["revenue_recognized"] is False
