import empire_os.solar_economics_readiness as readiness


def test_economics_readiness_refuses_to_infer_cash_cost_or_margin():
    observations = [{
        "status": "success",
        "product_code": "solar_opportunity_map_gb",
        "currency": "GBP",
        "resource_observation": {
            "wall_seconds": 4.2,
            "user_cpu_seconds": 1.3,
            "system_cpu_seconds": 0.2,
            "max_rss_kb": 30000,
            "artifact_bytes": 12000,
        },
        "monetary_cost": {
            "state": "UNKNOWN",
            "amount_minor": None,
        },
        "acquisition_cost_basis": {
            "state": "UNKNOWN",
        },
    }]

    result = readiness.build_economics_readiness(observations)

    assert result["successful_observation_count"] == 1
    assert result["resource_summary"]["median_wall_seconds"] == 4.2
    assert result["monetary_fulfilment_cost_state"] == "UNKNOWN"
    assert result["acquisition_cost_state"] == "UNKNOWN"
    assert result["margin_policy_state"] == "UNKNOWN"
    assert result["binding_economics_ready"] is False
    assert "cash_allocation_rule_unverified" in result["readiness_blockers"]
    assert "acquisition_cost_basis_unverified" in result["readiness_blockers"]
    assert "founder_margin_policy_unverified" in result["readiness_blockers"]
    assert result["cost_inferred_from_resource_usage"] is False
    assert result["margin_inferred"] is False


def test_empty_economics_readiness_is_fail_closed():
    result = readiness.build_economics_readiness([])

    assert result["observation_count"] == 0
    assert result["fulfilment_resource_evidence"] == "UNKNOWN"
    assert result["binding_economics_ready"] is False
    assert "no_successful_fulfilment_resource_observation" in result["readiness_blockers"]
