import json

from empire_os.founder_intelligence_nodes import (
    build_intelligence_nodes_projection,
    get_intelligence_node_projection,
)


def test_nodes_projection_preserves_unknown_counts(tmp_path):
    runtime = tmp_path / "runtime"
    (runtime / "source_health").mkdir(parents=True)
    (runtime / "acquisition").mkdir(parents=True)
    (runtime / "source_health/latest.json").write_text(json.dumps({
        "source": "overpass",
    }))
    (runtime / "acquisition/latest.json").write_text(json.dumps({
        "source": "nws_alerts",
    }))
    payload = build_intelligence_nodes_projection(tmp_path)
    assert payload["node_count"] >= 13
    keys = {row["key"] for row in payload["nodes"]}
    assert {"volumetric", "natural_physical"} <= keys
    solar = next(row for row in payload["nodes"] if row["key"] == "solar_energy")
    hvac = next(row for row in payload["nodes"] if row["key"] == "hvac_climate")
    property_node = next(row for row in payload["nodes"] if row["key"] == "property")
    for node in (solar, hvac, property_node):
        assert "volumetric" in node["sensors"]
        assert "natural_physical" in node["sensors"]
    home = next(row for row in payload["nodes"] if row["key"] == "home_services")
    assert set(home["runtime_evidence"]["observed_sources"]) == {
        "overpass", "nws_alerts"
    }
    assert home["runtime_evidence"]["opportunity_count"] is None
    assert home["runtime_evidence"]["counts_unknown"] is True


def test_get_node_returns_none_for_unknown(tmp_path):
    assert get_intelligence_node_projection(tmp_path, "nope") is None



def test_energy_node_is_explicitly_incubated(tmp_path):
    payload = build_intelligence_nodes_projection(tmp_path)
    rows = {row["key"]: row for row in payload["nodes"]}

    assert "oil_gas_energy" in rows
    assert rows["oil_gas_energy"]["lifecycle_state"] == "INCUBATE"
    assert rows["oil_gas_energy"]["execution_authority"] == "intelligence_only"
    assert rows["private_capital"]["lifecycle_state"] == "ACTIVE_BUILD"
    assert rows["property"]["lifecycle_state"] == "ACTIVE_BUILD"



def test_property_node_uses_real_permit_evidence_without_inventing_opportunities(tmp_path):
    path = tmp_path / "runtime/acquisition/signal_inbox.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "permit": {
            "source": "permits_nyc",
            "status": "resolved",
            "metro": "NYC",
            "created_at": "2026-09-21T10:00:00+00:00",
            "raw": {"job__": "1"},
        }
    }))

    payload = build_intelligence_nodes_projection(tmp_path)
    rows = {row["key"]: row for row in payload["nodes"]}
    prop = rows["property"]["runtime_evidence"]

    assert prop["observation_count"] == 1
    assert prop["evidence_state"] == "EVIDENCE_AVAILABLE"
    assert "permits_nyc" in prop["observed_sources"]
    assert prop["opportunity_count"] is None
    assert prop["revenue_cents"] is None


def test_private_capital_node_stays_unknown_without_canonical_snapshot(tmp_path):
    payload = build_intelligence_nodes_projection(tmp_path)
    rows = {row["key"]: row for row in payload["nodes"]}
    pe = rows["private_capital"]["runtime_evidence"]

    assert pe["observation_count"] is None
    assert pe["evidence_state"] == "UNKNOWN"
    assert pe["opportunity_count"] is None
    assert pe["revenue_cents"] is None
