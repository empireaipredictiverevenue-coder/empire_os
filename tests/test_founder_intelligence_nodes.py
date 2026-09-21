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
