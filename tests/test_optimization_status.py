from datetime import datetime, timezone

from empire_os.optimization_status import (
    build_optimization_status,
    refresh_optimization_status,
)
from empire_os.predictive_cloud_status import build_predictive_cloud_status


def test_optimization_status_reports_local_runtime_without_qpu_claim():
    result = build_optimization_status(
        env={},
        now=datetime(2026, 10, 2, 22, 0, tzinfo=timezone.utc),
    )

    assert result["status"] == "AVAILABLE"
    assert result["mode"] == "OBSERVE"
    assert result["capabilities"]["exact_binary_reference"] is True
    assert result["capabilities"]["empire_branch_bound"] is True
    assert result["capabilities"]["partitioned_empire_branch_bound"] is True
    assert result["capabilities"]["empire_quantum_inspired_annealing"] is True
    assert result["capabilities"]["empire_parallel_tempering"] is True
    assert result["capabilities"]["empire_qaoa_simulator"] is True
    assert result["capabilities"]["compute_job_protocol"] is True
    assert result["capabilities"]["greedy_binary_fallback"] is True
    assert result["capabilities"]["solver_policy"] is True
    assert result["capabilities"]["whole_business_optimization"] is True
    assert result["business_optimization_product"]["domain_count"] == 12
    assert result["business_optimization_product"][
        "third_party_runtime_required"
    ] is False
    assert result["external_qpu_enabled_count"] == 0
    assert result["external_qpu_called"] is False
    assert result["quantum_advantage_claimed"] is False
    assert result["execution_authority"] == "none"


def test_third_party_provider_flags_do_not_enable_service_execution():
    result = build_optimization_status(
        env={"EMPIRE_QPU_IBM_ENABLED": "true"},
    )

    assert result["third_party_services"]["execution_allowed"] is False
    assert result["third_party_services"]["provider_submission_allowed"] is False
    assert result["external_qpu_enabled_count"] == 0
    assert result["external_qpu_adapter_ready_count"] == 0
    assert result["third_party_runtime_allowed"] is False


def test_refresh_feeds_predictive_cloud_read_surface(tmp_path):
    refresh_optimization_status(tmp_path)

    status = build_predictive_cloud_status(
        tmp_path,
        now=datetime.now(timezone.utc),
    )

    component = status["components"]["optimization_fabric"]
    assert component["available"] is True
    assert component["freshness"] == "fresh"
    assert component["summary"]["empire_branch_bound"] is True
    assert component["summary"]["partitioned_empire_branch_bound"] is True
    assert component["summary"]["empire_parallel_tempering"] is True
    assert component["summary"]["empire_qaoa_simulator"] is True
    assert component["summary"]["benchmark_arena"] is True
    assert component["summary"]["compute_job_protocol"] is True
    assert component["summary"]["greedy_binary_fallback"] is True
    assert component["summary"]["solver_policy"] is True
    assert component["summary"]["whole_business_optimization"] is True
    assert component["summary"]["business_optimization_domain_count"] == 12
    assert component["summary"]["external_qpu_called"] is False
    assert component["execution_authority"] == "none"

def test_market_reference_packages_do_not_become_runtime_authority():
    result = build_optimization_status(env={})

    assert result["market_reference_capabilities"][
        "market_references_feed_production_policy"
    ] is False
    assert result["third_party_services"]["execution_allowed"] is False
    assert result["third_party_services"]["credential_use_allowed"] is False
    assert result["external_qpu_called"] is False
    assert result["quantum_advantage_claimed"] is False
