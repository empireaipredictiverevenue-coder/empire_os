"""Existing EmpireOS MRR/seat/territory catalogue reconciliation tests."""
from datetime import datetime, timezone
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.lead_territory_mrr_bridge import build_territory_mrr_bridge
from empire_os.founder_lead_supply_api import (
    create_founder_lead_supply_router, read_territory_package_preview,
)

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)


def exchange():
    return {
        "source": "canonical_empiredb_projection",
        "canonical_backend": "empiredb",
        "observed_at": NOW.isoformat(),
        "buyer_seats": [
            {
                "buyer_id": "buyer-roof",
                "niche_family": "roofing",
                "metro": "chicago",
                "corridor_key": "corridor:v1:roofing:chicago:qualified_lead:webhook",
                "seat_state": "blocked_missing_evidence",
            },
            {
                "buyer_id": "buyer-solar",
                "niche_family": "solar",
                "metro": "bolton",
                "corridor_key": "corridor:v1:solar:bolton:qualified_lead:webhook",
                "seat_state": "active_capacity",
            },
        ],
        "inventory": [
            {
                "niche_family": "roofing",
                "metro": "chicago",
                "corridor_key": "corridor:v1:roofing:chicago:qualified_lead:webhook",
                "state": "overflow_no_capacity",
            },
        ],
    }


def test_current_catalog_offers_without_legacy_subscription_access():
    report = build_territory_mrr_bridge(exchange=exchange(), observed_at=NOW)
    assert report["product_catalog_count"] == 4
    assert [p["monthly_price_cents"] for p in report["product_catalog"]] == [
        9900, 24900, 49900, 99900,
    ]
    assert report["product_catalog"][0]["corridor_limit"] == 1
    assert report["product_catalog"][1]["corridor_limit"] == 5
    assert report["product_catalog"][2]["corridor_limit"] == 25
    assert report["product_catalog"][3]["corridor_limit"] is None
    assert report["buyer_subscription_record_count"] is None
    assert report["strike_pack_record_count"] is None
    assert report["actual_mrr_cents"] is None
    assert not report["territory_exclusivity_verified"]
    assert all(not t["ready_for_binding_sale"] for t in report["territories"])


def test_canonical_records_are_not_auto_promoted_to_paying_mrr():
    packs = [{
        "id": "pack-1", "slug": "historic-bronze", "name": "Old Bronze",
        "tier": "standard", "niches": ["Roofing"], "is_active": True,
        "is_public": True, "monthly_price_cents": 10000,
        "max_leads_per_month": 100, "lane_count": 1,
    }]
    subs = [
        {
            "id": "sub-1", "buyer_id": "buyer-roof", "pack_id": "pack-1",
            "status": "active", "active": True,
            "monthly_price_cents": 10000, "period_start": "2026-10-01T00:00:00Z",
            "period_end": "2026-11-01T00:00:00Z",
        },
        {
            "id": "sub-2", "buyer_id": "buyer-solar", "pack_id": "pack-1",
            "status": "active", "active": True,
            "monthly_price_cents": 20000, "period_start": "2026-08-01T00:00:00Z",
            "period_end": "2026-09-01T00:00:00Z",
        },
        {
            "id": "sub-3", "buyer_id": "unknown", "pack_id": "unrecognized",
            "status": "paused", "active": False, "monthly_price_cents": 9900,
        },
    ]
    report = build_territory_mrr_bridge(
        exchange=exchange(), strike_packs=packs, buyer_subscriptions=subs,
        subscriptions_reader_available=True,
        strike_packs_reader_available=True, observed_at=NOW,
    )
    assert report["buyer_subscription_record_count"] == 3
    assert report["marked_active_subscription_record_count"] == 1
    assert report["subscription_rows_with_no_buyer_seat_match"] == 1
    assert report["subscription_rows_with_no_pack_match"] == 1
    assert report["nominal_monthly_contract_field_cents_unverified"] == 10000
    assert report["subscription_rows_matching_active_capacity"] == 0
    assert report["by_niche"][0]["marked_active_subscription_rows"] == 1
    assert report["actual_mrr_cents"] is None
    assert report["payment_verified"] is False
    assert report["subscription_entitlement_verified"] is False


def test_active_capacity_match_still_does_not_verify_payment():
    report = build_territory_mrr_bridge(
        exchange=exchange(), buyer_subscriptions=[{
            "id": "sub-x", "buyer_id": "buyer-solar", "pack_id": "old-pack",
            "active": True, "status": "active",
            "monthly_price_cents": 24900,
            "period_start": "2026-10-01T00:00:00Z",
        }], subscriptions_reader_available=True, observed_at=NOW,
    )
    assert report["subscription_rows_matching_active_capacity"] == 1
    assert report["actual_mrr_cents"] is None
    assert not report["subscription_entitlement_verified"]


def test_unavailable_optional_subscription_reader_is_unknown_not_zero():
    report = build_territory_mrr_bridge(
        exchange=exchange(), strike_packs=[], buyer_subscriptions=[],
        strike_packs_reader_available=False,
        subscriptions_reader_available=False, observed_at=NOW,
    )
    assert report["marked_active_subscription_record_count"] is None
    assert report["nominal_monthly_contract_field_cents_unverified"] is None


def test_private_packages_route_works_without_full_lead_census(tmp_path):
    exchange_path = tmp_path / "exchange.json"
    exchange_path.write_text(json.dumps(exchange()))
    missing = tmp_path / "unreleased.json"
    result = read_territory_package_preview(exchange_path)
    assert result["available"] is True
    assert result["product_catalog_count"] == 4
    app = FastAPI()
    app.include_router(create_founder_lead_supply_router(missing, exchange_path))
    response = TestClient(app).get("/v1/founder-lead-supply/packages")
    assert response.status_code == 200
    assert response.json()["product_catalog"][0]["monthly_price_cents"] == 9900
    assert response.json()["buyer_subscriptions_reader_available"] is False


def test_noncanonical_exchange_is_rejected():
    with pytest.raises(ValueError):
        build_territory_mrr_bridge(
            exchange={"canonical_backend": "legacy"}, observed_at=NOW,
        )


def test_delivery_corridors_are_aggregated_by_market_without_rights_inference():
    payload = exchange()
    payload["inventory"].append({
        "niche_family": "roofing",
        "metro": "chicago",
        "corridor_key": "corridor:v1:roofing:chicago:qualified_lead:lead",
        "state": "allocation_candidate",
    })
    report = build_territory_mrr_bridge(exchange=payload, observed_at=NOW)
    assert report["raw_buyer_and_supply_corridor_keys_not_equivalent"] is True
    assert report["territory_count"] == 3
    assert report["territory_market_count"] == 2
    roof = next(m for m in report["territory_markets"] if m["niche"] == "roofing")
    assert roof["distinct_corridor_keys"] == 2
    assert roof["buyer_seat_records"] == 1
    assert roof["sampled_qualified_inventory_records"] == 2
    assert roof["readiness"] == "NO_VERIFIED_BUYER_CAPACITY"
    assert roof["exact_route_compatibility_verified"] is False
    assert roof["sale_ready"] is False
