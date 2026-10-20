"""Offline, synthetic contract tests for in-memory owner offer rebuild."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from empire_os.commercial_shadow_offer_reconstruction import (
    review_shadow_offer_reconstruction,
)
from empire_os.revenue_distribution_review import REVIEW_SOURCES

NOW = datetime(2026, 10, 20, 10, tzinfo=timezone.utc)
FRESH = "2026-10-20T09:00:00Z"
OLD = "2026-09-30T01:00:00Z"


def fixture(*, all_sources_fresh=False, ready_catalog=True):
    p = {
        "product_code": "synthetic_report",
        "product_name": "Synthetic Report",
        "price_basis": {
            "amount_cents": 12500, "currency": "USD", "unit": "per_report"
        },
        "active": True,
        "binding_terms_ready": ready_catalog,
        "catalog_state": "VERIFIED" if ready_catalog else "UNKNOWN",
        "version_state": "VERIFIED" if ready_catalog else "UNKNOWN",
        "readiness_blockers": [],
        "verified_at": FRESH,
    }
    catalog = {
        "schema_version": "empire.commercial-product-catalog.v1",
        "execution_authority": "none",
        "generated_at": FRESH,
        "products": [p],
    }
    distribution = {
        "schema_version": "empire.revenue_distribution.v1",
        "execution_authority": "none",
        "generated_at": FRESH if all_sources_fresh else OLD,
        "opportunities": [],
    }
    promotion = {
        "generated_at": FRESH,
        "proposals": [{
            "proposed_prospect_payload": {"business_name": "Example Synthetic"},
            "domain": "example.invalid",
            "target_product_codes": ["synthetic_report"],
            "candidate_id": "research-1",
        }],
    }
    sources = (
        {name: {"generated_at": FRESH} for name in REVIEW_SOURCES}
        if all_sources_fresh else
        {name: None for name in REVIEW_SOURCES}
    )
    sources["promotion"] = promotion
    old = {
        "schema_version": "empire.predictive-revenue.commercial-offer-book.v2",
        "execution_authority": "none",
        "generated_at": OLD,
        "targets": [],
    }
    return {
        "catalog": catalog,
        "distribution": distribution,
        "review_sources": sources,
        "previous_offer_book": old,
        "now": NOW,
    }


def test_source_hold_shadow_counts_not_live_revenue():
    inp = fixture()
    snapshot = deepcopy(inp)
    report = review_shadow_offer_reconstruction(**inp)
    assert inp == snapshot  # Builder cannot mutate owner source inputs.
    assert report["status"] == "SOURCE_FRESHNESS_HOLD"
    assert report["source_refresh_review_required"] is True
    assert report["historical_offer_book"]["target_count"] == 0
    assert report["in_memory_reconstructed_offer_book"]["target_count"] == 1
    assert report["in_memory_reconstructed_offer_book"]["offer_ready_count"] == 0
    assert report["in_memory_reconstructed_offer_book"]["source_claims_verified_buyer_demand_count"] == 0
    assert report["reconstructed_ready_catalog_product_count"] == 1
    assert report["target_count_delta_not_a_new_leads_count"] == 1
    assert report["outbound_authorized"] is False
    assert report["database_writes"] is False
    assert report["canonical_files_written"] is False
    assert report["agent_tasks_created"] is False
    assert report["crm_mutations"] is False
    assert "Example Synthetic" not in str(report)


def test_refresh_all_sources_still_not_an_authorization():
    report = review_shadow_offer_reconstruction(**fixture(all_sources_fresh=True))
    assert report["status"] == "SHADOW_RECONSTRUCTION_ONLY"
    assert report["source_refresh_review_required"] is False
    assert report["result_is_shadow_not_current_commercial_authority"] is True
    assert report["execution_authority"] == "none"
    assert report["in_memory_reconstructed_offer_book"]["state_counts"] == {
        "CONTACT_EVIDENCE_REQUIRED": 1,
    }


def test_product_unready_preserves_owner_catalog_gate():
    report = review_shadow_offer_reconstruction(**fixture(ready_catalog=False))
    assert report["reconstructed_ready_catalog_product_count"] == 0
    assert report["in_memory_reconstructed_offer_book"]["state_counts"] == {
        "PRODUCT_READINESS_REQUIRED": 1,
    }


@pytest.mark.parametrize("key,bad", [
    ("catalog", "UNTRUSTED_CATALOG"),
    ("distribution", "UNTRUSTED_DISTRIBUTION"),
    ("previous_offer_book", "UNTRUSTED_BOOK"),
])
def test_schema_forgery_rejected(key, bad):
    inp = fixture()
    inp[key]["schema_version"] = bad
    with pytest.raises(ValueError, match="exact canonical"):
        review_shadow_offer_reconstruction(**inp)


@pytest.mark.parametrize("key", [
    "catalog", "distribution", "previous_offer_book"
])
def test_external_execution_authority_is_rejected(key):
    inp = fixture()
    inp[key]["execution_authority"] = "live"
    with pytest.raises(ValueError, match="unsupported execution authority"):
        review_shadow_offer_reconstruction(**inp)


def test_missing_required_owner_sources_fails_closed():
    inp = fixture()
    del inp["review_sources"]["promotion"]
    with pytest.raises(ValueError, match="exact existing owner"):
        review_shadow_offer_reconstruction(**inp)


def test_invalid_review_source_shape_fails_closed():
    inp = fixture()
    inp["review_sources"]["enterprise"] = "forged"
    with pytest.raises(ValueError, match="review input"):
        review_shadow_offer_reconstruction(**inp)


def test_reconstructing_cannot_override_now_with_naive_datetime():
    inp = fixture()
    inp["now"] = datetime(2026, 10, 20, 10)
    with pytest.raises(ValueError, match="timezone-aware"):
        review_shadow_offer_reconstruction(**inp)


def test_invalid_future_and_missing_source_times_make_review_hold():
    inp = fixture(all_sources_fresh=True)
    inp["review_sources"]["promotion"]["generated_at"] = "2026-11-20T00:00:00Z"
    inp["review_sources"]["contacts"]["generated_at"] = ""
    inp["review_sources"]["enterprise"]["generated_at"] = "not-a-date"
    report = review_shadow_offer_reconstruction(**inp)
    assert report["status"] == "SOURCE_FRESHNESS_HOLD"
    clocks = report["upstream_freshness"]
    assert clocks["owner_review_promotion"]["state"] == "FUTURE_CLOCK"
    assert clocks["owner_review_contacts"]["state"] == "UNKNOWN_CLOCK"
    assert clocks["owner_review_enterprise"]["state"] == "INVALID_CLOCK"


def test_overlarge_opportunities_refused_before_builder_runs():
    inp = fixture()
    inp["distribution"]["opportunities"] = [{}] * 5001
    with pytest.raises(ValueError, match="bounded canonical"):
        review_shadow_offer_reconstruction(**inp)
