from pathlib import Path

import empire_os.solar_fulfilment_observation as obs


def test_resource_observation_keeps_cash_cost_unknown(tmp_path: Path):
    started = {
        "wall_started": 0.0,
        "user_cpu_started": 0.0,
        "system_cpu_started": 0.0,
        "max_rss_started_kb": 1.0,
    }
    json_path = tmp_path / "map.json"
    md_path = tmp_path / "map.md"
    json_path.write_text("{}")
    md_path.write_text("# map")

    result = obs.finish_resource_observation(
        started,
        prospect_id="p1",
        product_code="solar_opportunity_map_gb",
        currency="GBP",
        artifact_paths={
            "json_path": str(json_path),
            "markdown_path": str(md_path),
        },
        priority_actions=7,
        observed_sections=2,
        unavailable_sections=3,
    )

    assert result["product_code"] == "solar_opportunity_map_gb"
    assert result["monetary_cost"]["state"] == "UNKNOWN"
    assert result["monetary_cost"]["amount_minor"] is None
    assert result["fulfilment_cost_basis"]["state"] == "PARTIAL"
    assert result["acquisition_cost_basis"]["state"] == "UNKNOWN"
    assert result["margin_inferred"] is False
    assert result["resource_observation"]["artifact_bytes"] > 0
    assert result["actual_revenue"] is False


def test_resource_observation_is_written_private(tmp_path: Path):
    observation = {
        "prospect_id": "p1",
        "observed_at": "2026-09-23T22:30:00+00:00",
        "actual_revenue": False,
    }

    path = obs.write_resource_observation(
        observation,
        root=tmp_path,
    )

    assert path.exists()
    assert path.stat().st_mode & 0o777 == 0o600
    assert "p1-" in path.name
