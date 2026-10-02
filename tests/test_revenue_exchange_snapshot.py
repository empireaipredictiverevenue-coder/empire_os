import json
from datetime import datetime, timezone

from empire_os.revenue_exchange_snapshot import (
    build_revenue_exchange_live_snapshot,
    write_revenue_exchange_live_snapshot,
)

NOW = datetime(2026, 10, 2, 10, 0, tzinfo=timezone.utc)


def row(**overrides):
    value = {
        "observation_key": "roofing-london-1",
        "niche": "roofing",
        "metro": "London",
        "qualified_inventory_count": 12,
        "active_buyer_capacity": 6,
        "verified_price_per_lead_cents": [7500, 10000],
        "observed_at": "2026-10-02T09:00:00+00:00",
        "source": "canonical_market_snapshot",
        "evidence": {"inventory_source": "canonical_prospects"},
        "created_at": "2026-10-02T09:01:00+00:00",
    }
    value.update(overrides)
    return value


def test_latest_per_market_is_deterministic_and_preserves_lineage():
    payload = build_revenue_exchange_live_snapshot([
        row(observation_key="old", observed_at="2026-10-02T08:00:00+00:00", qualified_inventory_count=3),
        row(observation_key="new", observed_at="2026-10-02T09:00:00+00:00", qualified_inventory_count=12),
        row(observation_key="solar", niche="solar", metro="Manchester"),
    ], generated_at=NOW)

    assert payload["market_count"] == 2
    roofing = next(x for x in payload["markets"] if x["market_key"] == "roofing::london")
    assert roofing["observation_key"] == "new"
    assert roofing["snapshot"]["qualified_inventory_count"] == 12
    assert roofing["source"] == "canonical_market_snapshot"
    assert roofing["evidence"]["inventory_source"] == "canonical_prospects"
    assert roofing["reconciliation_evidence"] is None
    assert roofing["blockers"] == ["independent_reconciliation_evidence_missing"]
    assert payload["source"] == "canonical_empiredb_revenue_exchange_observations"
    assert payload["execution_authority"] == "none"


def test_independent_reconciliation_evidence_requires_all_fields_and_refs():
    evidence = {
        "inventory_count": 12,
        "buyer_capacity": 6,
        "verified_prices_cents": [7500, 10000],
        "evidence_refs": ["inventory:1", "capacity:1", "price:1"],
    }
    payload = build_revenue_exchange_live_snapshot([row(evidence=evidence)], generated_at=NOW)
    market = payload["markets"][0]
    assert market["reconciliation_evidence"] == {
        "inventory_count": 12,
        "buyer_capacity": 6,
        "verified_prices_cents": [7500, 10000],
        "evidence_refs": ["inventory:1", "capacity:1", "price:1"],
    }
    assert market["blockers"] == []


def test_observation_never_self_certifies_missing_reconciliation():
    payload = build_revenue_exchange_live_snapshot([row(evidence={
        "inventory_count": 12,
        "buyer_capacity": 6,
        "verified_prices_cents": [7500, 10000],
    })], generated_at=NOW)
    assert payload["markets"][0]["reconciliation_evidence"] is None


def test_invalid_rows_fail_closed_without_coercion():
    payload = build_revenue_exchange_live_snapshot([
        row(active_buyer_capacity=-1),
        row(observation_key="valid"),
    ], generated_at=NOW)
    assert payload["market_count"] == 1
    assert payload["invalid_row_count"] == 1
    assert "invalid_revenue_exchange_rows_present" in payload["blockers"]


def test_empty_result_is_valid_but_explicitly_blocked():
    payload = build_revenue_exchange_live_snapshot([], generated_at=NOW)
    assert payload["market_count"] == 0
    assert payload["blockers"] == ["no_revenue_exchange_observations"]
    assert payload["read_only"] is True
    assert payload["payment_action"] is False
    assert payload["revenue_recognition"] is False


def test_atomic_writer_round_trips(tmp_path):
    payload = build_revenue_exchange_live_snapshot([row()], generated_at=NOW)
    target = write_revenue_exchange_live_snapshot(tmp_path, payload)
    loaded = json.loads(target.read_text())
    assert loaded["market_count"] == 1
    assert not target.with_suffix(".json.tmp").exists()
