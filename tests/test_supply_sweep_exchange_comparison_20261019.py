"""Safe internal view of two distinct lead-supply populations."""
from datetime import datetime, timezone
import json

import pytest

from scripts.review_supply_sweeps_and_exchange_20261019 import (
    compare_private_inventory, main
)
from tests.test_lead_exchange_live_inventory_20261019 import fixture


NOW = datetime(2026, 10, 19, 13, 40, tzinfo=timezone.utc)


def sweep():
    return {
        "schema_version": "empire.recc_solar_supply_sweep.v1",
        "source_id": "gb_recc_solar",
        "state": "COMPLETED",
        "unique_research_observations": 16,
        "observed_at": NOW.isoformat(),
        "commercial_exchange_inventory_added": 0,
        "canonical_empiredb_writes": False,
        "outbound_authorized": False,
    }


def test_aggregate_never_promotes_research_into_stock():
    r = compare_private_inventory(exchange=fixture(), source_sweep=sweep(), now=NOW)
    assert r["canonical_exchange_selected_inventory"] == 4
    assert r["distinct_private_source_research_observations"] == 16
    assert r["increment_to_exchange_from_sweep"] == 0
    assert r["canonical_exchange_delivery_ready"] == 0
    assert not r["outbound_authorized"]
    assert "private-buyer-001" not in json.dumps(r)
    assert "prospect-1" not in json.dumps(r)
    assert "never-expose@example.com" not in json.dumps(r)


def test_invalid_source_sweep_claims_never_count():
    for field, value in [
        ("commercial_exchange_inventory_added", 1),
        ("canonical_empiredb_writes", True),
        ("outbound_authorized", True),
        ("source_id", "reddit"),
        ("unique_research_observations", 999),
    ]:
        data = sweep()
        data[field] = value
        with pytest.raises(ValueError):
            compare_private_inventory(exchange=fixture(), source_sweep=data, now=NOW)


def test_cli_from_local_snapshots_no_db_or_outbound(tmp_path, capsys):
    d = fixture()
    d["observed_at"] = datetime.now(timezone.utc).isoformat()
    s = sweep()
    e = tmp_path / "exchange.json"
    r = tmp_path / "source.json"
    e.write_text(json.dumps(d))
    r.write_text(json.dumps(s))
    assert main([
        "--read-only", "--exchange", str(e), "--sweep", str(r)
    ]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["canonical_exchange_selected_inventory"] == 4
    assert output["distinct_private_source_research_observations"] == 16
    assert e.read_text() == json.dumps(d)
    assert r.read_text() == json.dumps(s)


def test_cli_malformed_source_no_text_leak(tmp_path, capsys):
    e = tmp_path / "exchange.json"
    r = tmp_path / "source.json"
    e.write_text("PERSONAL CUSTOMER DATA")
    r.write_text(json.dumps(sweep()))
    assert main(["--read-only", "--exchange", str(e), "--sweep", str(r)]) == 2
    assert "PERSONAL CUSTOMER" not in capsys.readouterr().out
