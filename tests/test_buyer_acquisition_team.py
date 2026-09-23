from datetime import datetime, timezone

from empire_os.buyer_acquisition_team import (
    build_buyer_acquisition_plan,
    build_demand_gap_queue,
    direct_buyer_profile,
)


def test_direct_lead_buyer_evidence_scores_above_generic_agency():
    direct = direct_buyer_profile({
        "business_name": "Pipeline Exchange",
        "notes": "We buy leads and pay per lead for B2B campaigns",
    })
    agency = direct_buyer_profile({
        "business_name": "Acme Marketing Agency",
        "notes": "SEO and content services",
    })

    assert direct["buyer_type"] == "direct_lead_buyer"
    assert direct["explicit_direct_buyer_evidence"] is True
    assert direct["direct_buyer_score"] > agency["direct_buyer_score"]
    assert direct["binding_commercial_evidence"] is False


def test_overflow_corridor_becomes_top_buyer_hunt_priority():
    exchange = {
        "inventory": [
            {
                "corridor_key": (
                    "corridor:v1:roofing:austin_tx:"
                    "qualified_lead:lead"
                ),
                "state": "overflow_no_capacity",
            },
            {
                "corridor_key": (
                    "corridor:v1:roofing:austin_tx:"
                    "qualified_lead:lead"
                ),
                "state": "overflow_no_capacity",
            },
        ],
        "buyer_seats": [],
    }

    queue = build_demand_gap_queue(exchange)

    assert len(queue) == 1
    assert queue[0]["overflow_count"] == 2
    assert queue[0]["buyer_hunt_required"] is True
    assert queue[0]["acquisition_should_continue"] is True
    assert queue[0]["rank"] == 1


def test_blocked_seats_do_not_count_as_active_capacity():
    corridor = (
        "corridor:v1:roofing:austin_tx:qualified_lead:lead"
    )
    exchange = {
        "inventory": [
            {"corridor_key": corridor, "state": "allocation_candidate"},
        ],
        "buyer_seats": [
            {
                "corridor_key": corridor,
                "seat_state": "blocked_missing_evidence",
                "remaining_capacity": 100,
            },
        ],
    }

    queue = build_demand_gap_queue(exchange)

    assert queue[0]["active_remaining_capacity"] == 0
    assert queue[0]["blocked_seat_count"] == 1
    assert queue[0]["buyer_hunt_required"] is True


def test_plan_automates_internal_team_but_not_live_send():
    plan = build_buyer_acquisition_plan(
        {
            "inventory": [],
            "buyer_seats": [],
            "supply_gate_diagnostics": {
                "prospects_seen": 200,
                "qualification_ready_count": 0,
            },
            "seat_activation_blocker_counts": {
                "buyer_not_commercially_activated": 168,
            },
        },
        generated_at=datetime(
            2026, 9, 23, 0, 0, tzinfo=timezone.utc
        ),
    )

    assert plan["phase"] == "4"
    assert plan["team_role_count"] >= 8
    assert plan["automation"]["buyer_research_planning"] is True
    assert plan["automation"]["decision_maker_resolution"] is True
    assert plan["automation"]["commercial_evidence_extraction"] is True
    assert plan["automation"]["live_outbound_send"] is False
    assert plan["canonical_settlement_rail"] == "USDT_BSC"
    assert plan["legacy_buyer_hunter_is_canonical"] is False
    assert plan["buyer_capacity_never_gates_acquisition"] is True
    assert plan["execution_authority"] == "none"


def test_buyer_acquisition_covers_end_buyers_enterprise_and_saas():
    plan = build_buyer_acquisition_plan(
        {"inventory": [], "buyer_seats": []},
        generated_at=datetime(
            2026, 9, 23, 0, 0, tzinfo=timezone.utc
        ),
    )
    pools = {row["pool"]: row for row in plan["buyer_pools"]}

    assert "end_service_buyers" in pools
    assert "direct_demand_buyers" in pools
    assert "agency_and_reseller_buyers" in pools
    assert "enterprise_and_data_buyers" in pools
    assert "software_and_advisory_buyers" in pools
    assert "qualified_leads" in pools["end_service_buyers"]["purchases"]
    assert "vertical_intelligence" in pools[
        "enterprise_and_data_buyers"
    ]["purchases"]
    assert "saas_subscriptions" in pools[
        "software_and_advisory_buyers"
    ]["purchases"]


def test_priority_targets_include_direct_and_end_buyer_research():
    corridor = (
        "corridor:v1:roofing:austin_tx:qualified_lead:lead"
    )
    plan = build_buyer_acquisition_plan(
        {
            "inventory": [
                {
                    "corridor_key": corridor,
                    "state": "overflow_no_capacity",
                }
            ],
            "buyer_seats": [],
        },
        generated_at=datetime(
            2026, 9, 23, 0, 0, tzinfo=timezone.utc
        ),
    )

    queries = plan["priority_targets"][0]["research_queries"]
    assert "direct_demand_buyers" in queries
    assert "end_service_buyers" in queries
    assert "agency_and_reseller_buyers" in queries
    assert "enterprise_and_data_buyers" in queries
    assert "software_and_advisory_buyers" in queries
    assert any("roofing company" in q for q in queries["end_service_buyers"])
    assert any("buy roofing leads" in q for q in queries["direct_demand_buyers"])


def test_buyer_acquisition_includes_local_and_small_business_market():
    plan = build_buyer_acquisition_plan(
        {"inventory": [], "buyer_seats": []},
        generated_at=datetime(
            2026, 9, 23, 0, 0, tzinfo=timezone.utc
        ),
    )
    pools = {row["pool"]: row for row in plan["buyer_pools"]}

    assert "local_and_smb_buyers" in pools
    local = pools["local_and_smb_buyers"]
    assert "local_leads" in local["purchases"]
    assert "booked_appointments" in local["purchases"]
    assert "seo_and_search_intelligence" in local["purchases"]
    assert "commercial_diagnostics" in local["purchases"]
    assert "managed_growth" in local["purchases"]
    assert "lightweight_saas" in local["purchases"]


def test_priority_targets_include_local_smb_research_queries():
    corridor = (
        "corridor:v1:roofing:austin_tx:qualified_lead:lead"
    )
    plan = build_buyer_acquisition_plan(
        {
            "inventory": [
                {
                    "corridor_key": corridor,
                    "state": "overflow_no_capacity",
                }
            ],
            "buyer_seats": [],
        },
        generated_at=datetime(
            2026, 9, 23, 0, 0, tzinfo=timezone.utc
        ),
    )

    queries = plan["priority_targets"][0]["research_queries"]
    assert "local_and_smb_buyers" in queries
    assert any("local business" in q for q in queries["local_and_smb_buyers"])
    assert any("free quote" in q for q in queries["local_and_smb_buyers"])


def test_product_demand_separates_sellable_from_market_validation():
    plan = build_buyer_acquisition_plan(
        {"inventory": [], "buyer_seats": []},
        catalog_snapshot={
            "products": [
                {
                    "active": True,
                    "product_code": "managed_service",
                    "product_name": "Opportunity Intelligence Pilot",
                    "product_family": "opportunity_intelligence",
                    "billing_model": "flat_pilot",
                    "catalog_state": "VERIFIED",
                    "version_state": "VERIFIED",
                    "binding_terms_ready": True,
                },
                {
                    "active": True,
                    "product_code": "local_search_grid",
                    "product_name": "Local Search Grid Intelligence",
                    "product_family": "search_intelligence",
                    "billing_model": "terms_required",
                    "catalog_state": "UNKNOWN",
                    "version_state": "UNKNOWN",
                    "binding_terms_ready": False,
                },
            ]
        },
        generated_at=datetime(
            2026, 9, 23, 0, 0, tzinfo=timezone.utc
        ),
    )

    assert plan["product_demand_count"] == 7
    assert plan["sellable_product_demand_count"] == 1
    assert plan["market_validate_product_count"] == 6

    managed = next(
        row for row in plan["product_demand_queue"]
        if row["product_code"] == "managed_service"
    )
    search = next(
        row for row in plan["product_demand_queue"]
        if row["product_code"] == "local_search_grid"
    )

    assert managed["commercial_state"] == "SELLABLE_TERMS_READY"
    assert managed["price_claim_allowed"] is True
    assert "local_and_smb_buyers" in managed["target_buyer_pools"]

    assert search["commercial_state"] == (
        "MARKET_VALIDATE_TERMS_REQUIRED"
    )
    assert search["price_claim_allowed"] is False
    assert "local_and_smb_buyers" in search["target_buyer_pools"]
    assert "agency_and_reseller_buyers" in search["target_buyer_pools"]


def test_phase4_exchange_mrr_products_enter_buyer_demand_queue():
    plan = build_buyer_acquisition_plan(
        {"inventory": [], "buyer_seats": []},
        catalog_snapshot={"products": []},
        generated_at=datetime(
            2026, 9, 23, 0, 0, tzinfo=timezone.utc
        ),
    )

    rows = {
        row["product_code"]: row
        for row in plan["product_demand_queue"]
    }
    expected = {
        "exchange_seat_starter",
        "exchange_seat_growth",
        "exchange_seat_pro",
        "exchange_seat_enterprise",
    }

    assert expected.issubset(rows)
    for code in expected:
        row = rows[code]
        assert row["commercial_state"] == (
            "MARKET_VALIDATE_TERMS_REQUIRED"
        )
        assert row["binding_terms_ready"] is False
        assert row["price_claim_allowed"] is False
        assert row["recovered_mrr_product"] is True
        assert "local_and_smb_buyers" in row["target_buyer_pools"]



def test_tag_intelligence_enters_buyer_demand_without_price_claim():
    plan = build_buyer_acquisition_plan(
        {"inventory": [], "buyer_seats": []},
        catalog_snapshot={"products": []},
        generated_at=datetime(
            2026, 9, 23, 0, 0, tzinfo=timezone.utc
        ),
    )

    row = next(
        item for item in plan["product_demand_queue"]
        if item["product_code"] == "tag_intelligence_monitor"
    )

    assert row["billing_model"] == "monthly_subscription"
    assert row["commercial_state"] == "MARKET_VALIDATE_TERMS_REQUIRED"
    assert row["binding_terms_ready"] is False
    assert row["catalog_verified"] is False
    assert row["price_claim_allowed"] is False
    assert row["new_mrr_product"] is True
    assert "local_and_smb_buyers" in row["target_buyer_pools"]
    assert "agency_and_reseller_buyers" in row["target_buyer_pools"]
