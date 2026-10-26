"""Pure, synthetic fixtures: no DB, outbound, or production mutations."""
from datetime import datetime, timezone

import pytest

from empire_os.tam_revenue_portfolio import (
    PRODUCT_LINES,
    build_tam_revenue_portfolio,
)


NOW = datetime(2026, 10, 26, 11, tzinfo=timezone.utc)


def tam():
    return {
        "schema_version": "empire.tam-market-intelligence.v1",
        "source": "empiredb_restricted_tam_reader", "mode": "OBSERVE",
        "execution_authority": "none", "tenant_id": "empire-platform-research",
        "generated_at": "2026-10-10T11:00:00+00:00",
        "market_scope_count": 2, "observed_unique_entity_count": 1,
        "market_scopes": [
            {"industry": "roofing", "country_code": "US",
             "observed_entity_count": 1, "entities": [{"entity_id": "co-1"}]},
            {"industry": "solar", "country_code": "GB",
             "observed_entity_count": 1, "entities": [{"entity_id": "co-1"}]},
        ],
    }


def commercial():
    return {
        "schema_version": "empire.commercial_exchange_snapshot.v1",
        "source": "canonical_empiredb_projection",
        "candidate_selection": "qualification_driven",
        "canonical_backend": "empiredb", "mode": "OBSERVE",
        "execution_authority": "none", "actual_revenue": False,
        "observed_at": "2026-10-26T09:00:00+00:00",
        "inventory_count": 3, "buyer_seat_count": 2,
        "verified_market_price_count": 0,
        "inventory": [
            {"prospect_id": "prospect-A", "state": "overflow_no_capacity"},
            {"prospect_id": "prospect-A", "state": "allocation_candidate"},
            {"prospect_id": "prospect-B", "state": "blocked_missing_evidence"},
        ],
        "buyer_seats": [
            {"buyer_id": "buyer-A", "seat_state": "blocked_missing_evidence",
             "observed_rate": 9999, "remaining_capacity": 50},
            {"buyer_id": "buyer-A", "seat_state": "active_capacity",
             "remaining_capacity": 2},
        ],
    }


def revenue():
    return {
        "schema_version": "empire.revenue_exchange.live_snapshot.v1",
        "source": "canonical_empiredb_revenue_exchange_observations",
        "mode": "OBSERVE", "execution_authority": "none",
        "read_only": True, "revenue_recognition": False,
        "generated_at": "2026-10-26T09:00:00+00:00",
        "market_count": 1,
        "markets": [{
            "market_key": "roofing::chicago",
            "reconciliation_evidence": None,
        }],
    }


def result(**kwargs):
    return build_tam_revenue_portfolio(
        tam_snapshot=tam(), now=NOW, **kwargs
    )


def test_registry_includes_exchange_buyer_and_supplier_without_additive_tam():
    output = result(commercial_exchange_snapshot=commercial())
    ids = {row["product_id"] for row in output["product_lines"]}
    assert "leads_exchange" in ids
    assert {"pay_per_call", "data_brokerage", "white_label", "storm_property",
            "heat_pump_eco", "jobs_contractor", "trading_research"} <= ids
    assert output["product_line_count"] == len(PRODUCT_LINES)
    assert output["observed_unique_market_entities"] == 1
    assert output["tam_state"] == "UNKNOWN"
    assert output["market_population_count"] is None
    exchange = next(x for x in output["product_lines"]
                    if x["product_id"] == "leads_exchange")
    assert {"lead_buyer", "publisher", "inventory_supplier"} == set(exchange["commercial_roles"])
    assert exchange["observed_sector_sample_rows"] == 2
    assert exchange["total_addressable_companies"] is None
    assert all(not x["counts_are_additive_across_products"] for x in output["product_lines"])


def test_exchange_counts_do_not_promote_blocked_buyers_or_duplicate_prospects():
    x = result(commercial_exchange_snapshot=commercial())["commercial_exchange"]
    assert x["inventory_rows"] == 3
    assert x["distinct_inventory_prospects"] == 2
    assert x["qualified_supply_prospects"] == 1
    assert x["overflow_prospects"] == 1
    assert x["blocked_inventory_rows"] == 1
    assert x["buyer_seats"] == 2
    assert x["observed_buyer_ids"] == 1
    assert x["active_buyer_seats"] == 1
    assert x["active_buyer_capacity"] == 2
    assert x["blocked_buyer_seats"] == 1
    assert x["verified_market_price_observations"] == 0


def test_revenue_market_is_not_reconciled_without_independent_evidence():
    x = result(revenue_exchange_snapshot=revenue())["revenue_exchange"]
    assert x["observed_markets"] == 1
    assert x["reconciled_markets"] == 0


def test_missing_optional_sources_are_unknown_not_zero():
    output = result()
    assert output["commercial_exchange"]["inventory_rows"] is None
    assert output["revenue_exchange"]["observed_markets"] is None
    assert output["decision_maker_count"] is None
    assert output["verified_email_count"] is None
    assert output["company_turnover_enrichment_count"] is None


def test_staleness_and_no_new_authority():
    output = result(commercial_exchange_snapshot=commercial())
    assert output["tam_snapshot_stale"] is True
    assert output["tam_snapshot_age_days"] == 16
    assert output["mode"] == "OBSERVE"
    assert output["new_outbound_authorized"] is False
    assert output["payment_authorized"] is False
    assert output["revenue_verified"] is False
    assert output["execution_authority"] == "none"


@pytest.mark.parametrize("mutation", [
    {"inventory_count": 99},
    {"buyer_seat_count": 0},
    {"source": "legacy_projection"},
    {"canonical_backend": "supabase"},
    {"actual_revenue": True},
    {"execution_authority": "send"},
])
def test_exchange_contract_fail_closed(mutation):
    x = commercial()
    x.update(mutation)
    with pytest.raises(ValueError):
        result(commercial_exchange_snapshot=x)


def test_revenue_source_does_not_self_certify_reconciliation_or_authority():
    x = revenue()
    x["execution_authority"] = "allocate"
    with pytest.raises(ValueError):
        result(revenue_exchange_snapshot=x)


def test_tam_scope_count_and_entity_truth_are_guarded():
    x = tam()
    x["observed_unique_entity_count"] = 2
    with pytest.raises(ValueError, match="unique entity count mismatch"):
        build_tam_revenue_portfolio(tam_snapshot=x, now=NOW)
    x = tam()
    x["market_scopes"][0]["observed_entity_count"] = 3
    with pytest.raises(ValueError, match="observed count mismatch"):
        build_tam_revenue_portfolio(tam_snapshot=x, now=NOW)


def test_missing_tam_source_cannot_fall_back_to_exchange_as_market_size():
    x = tam()
    x["source"] = "synthetic_seed"
    with pytest.raises(ValueError, match="noncanonical source"):
        build_tam_revenue_portfolio(
            tam_snapshot=x, commercial_exchange_snapshot=commercial(), now=NOW
        )


def test_existing_tam_cli_reads_saved_receipts_only(tmp_path, monkeypatch, capsys):
    """The existing TAM command exposes portfolio without refreshing the DB."""
    import json
    import sys
    from empire_os import tam_market_runtime

    for name, payload in (
        ("tam_market_intelligence", tam()),
        ("commercial_exchange", commercial()),
        ("revenue_exchange", revenue()),
    ):
        folder = tmp_path / "runtime" / name
        folder.mkdir(parents=True)
        (folder / "latest.json").write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        sys, "argv",
        ["tam_market_runtime", "--portfolio", "--repo-root", str(tmp_path)],
    )
    assert tam_market_runtime.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "empire.tam-revenue-portfolio.v2"
    assert payload["observed_unique_market_entities"] == 1
    assert payload["commercial_exchange"]["qualified_supply_prospects"] == 1
    assert payload["execution_authority"] == "none"


def test_saved_receipt_loader_rejects_symlink(tmp_path):
    import json
    from empire_os.tam_revenue_portfolio import (
        read_tam_revenue_portfolio_from_runtime,
    )

    folder = tmp_path / "tam_market_intelligence"
    folder.mkdir()
    other = tmp_path / "receipt.json"
    other.write_text(json.dumps(tam()), encoding="utf-8")
    (folder / "latest.json").symlink_to(other)
    with pytest.raises(ValueError, match="unsafe runtime receipt"):
        read_tam_revenue_portfolio_from_runtime(tmp_path)


def test_market_gap_projections_are_scoped_and_deduplicated():
    x = commercial()
    x["inventory"] = [
        {"prospect_id": "p1", "state": "overflow_no_capacity",
         "niche_family": "roofing", "metro": "Denver, CO"},
        {"prospect_id": "p1", "state": "allocation_candidate",
         "niche_family": "roofing", "metro": "denver, co"},
        {"prospect_id": "p2", "state": "blocked_missing_evidence",
         "niche_family": "solar", "metro": "Denver, CO"},
    ]
    x["buyer_seats"] = [
        {"buyer_id": "b1", "seat_state": "blocked_missing_evidence",
         "activation_reason": "buyer_inactive",
         "niche_family": "roofing", "metro": "denver, co",
         "remaining_capacity": 500},
        {"buyer_id": "b2", "seat_state": "blocked_missing_evidence",
         "activation_reason": "buyer_not_commercially_activated",
         "niche_family": "roofing", "metro": None,
         "remaining_capacity": 300},
    ]
    gaps = result(commercial_exchange_snapshot=x)["leads_exchange_market_gaps"]
    assert gaps["market_count"] == 1
    assert gaps["niche_summaries"] == [{
        "niche": "roofing",
        "observed_market_count": 1,
        "overflow_prospect_market_assignments": 1,
        "qualified_prospect_market_assignments": 1,
        "markets_missing_active_seats": 1,
    }]
    assert gaps["market_assignment_counts_are_distinct_companies"] is False
    assert gaps["overflow_market_count"] == 1
    assert gaps["markets_missing_active_seats"] == 1
    assert gaps["unscoped_buyer_seats"] == 1
    assert gaps["qualified_supply_missing_market_context"] == 0
    assert gaps["buyer_seat_activation_blockers"] == {
        "buyer_inactive": 1, "buyer_not_commercially_activated": 1,
    }
    top = gaps["top_markets"][0]
    assert top["niche"] == "roofing"
    assert top["metro"] == "denver, co"
    assert top["qualified_inventory_prospects"] == 1
    assert top["overflow_prospects"] == 1
    assert top["same_market_observed_buyer_seats"] == 1
    assert top["same_market_active_capacity"] == 0
    assert top["qualified_buyer_count"] is None
    assert top["market_price_verified"] is False
    assert top["research_priority"] == "OVERFLOW_NO_ACTIVE_MARKET_SEAT"


def test_scoped_market_active_seat_never_implies_buyer_fit():
    x = commercial()
    x["inventory"] = [
        {"prospect_id": "p1", "state": "overflow_no_capacity",
         "niche_family": "plumbing", "metro": "Chicago, IL"},
        {"prospect_id": "p2", "state": "blocked_missing_evidence",
         "niche_family": None, "metro": None},
        {"prospect_id": "p3", "state": "blocked_missing_evidence",
         "niche_family": None, "metro": None},
    ]
    x["buyer_seats"] = [
        {"buyer_id": "b1", "seat_state": "active_capacity",
         "niche_family": "plumbing", "metro": "chicago, il",
         "remaining_capacity": 3},
        {"buyer_id": "b2", "seat_state": "blocked_missing_evidence",
         "activation_reason": "test_hold",
         "niche_family": "plumbing", "metro": "Houston, TX"},
    ]
    gaps = result(commercial_exchange_snapshot=x)["leads_exchange_market_gaps"]
    top = gaps["top_markets"][0]
    assert top["same_market_active_buyer_seats"] == 1
    assert top["same_market_active_capacity"] == 3
    assert top["buyer_eligibility_verified"] is False
    assert top["research_priority"] == "CHECK_CORRIDOR_PRICE_AND_ELIGIBILITY"
    assert gaps["markets_missing_active_seats"] == 0


def test_missing_market_geography_cannot_be_silently_assigned():
    x = commercial()
    x["inventory"] = [
        {"prospect_id": "p1", "state": "overflow_no_capacity",
         "niche_family": "roofing", "metro": None},
        {"prospect_id": "p1", "state": "allocation_candidate",
         "niche_family": "roofing", "metro": None},
        {"prospect_id": "p2", "state": "blocked_missing_evidence",
         "niche_family": "roofing", "metro": "Denver"},
    ]
    gaps = result(commercial_exchange_snapshot=x)["leads_exchange_market_gaps"]
    assert gaps["market_count"] == 0
    assert gaps["qualified_supply_missing_market_context"] == 1
    assert gaps["unique_scoped_supply_prospects"] == 0
    assert gaps["top_markets"] == []


def test_missing_exchange_market_report_stays_unknown_not_zero():
    gaps = result()["leads_exchange_market_gaps"]
    assert gaps["source_available"] is False
    assert gaps["market_count"] is None
    assert gaps["unscoped_buyer_seats"] is None
    assert gaps["top_markets"] == []
