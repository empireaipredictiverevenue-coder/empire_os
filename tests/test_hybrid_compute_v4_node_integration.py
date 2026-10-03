from empire_os.hybrid_compute_policy import (
    LocalCandidateEvidence,
    recommend_registered_local,
)
from empire_os.node_runtime_catalog import (
    ProbeResult,
    build_runtime_registry,
)


def healthy(endpoint: str) -> ProbeResult:
    return ProbeResult(
        healthy=True,
        status_code=200,
        endpoint=endpoint,
    )


def offline(endpoint: str) -> ProbeResult:
    return ProbeResult(
        healthy=False,
        status_code=None,
        endpoint=endpoint,
        error="offline",
    )


def candidates():
    return (
        LocalCandidateEvidence(
            candidate_id=
                "qwen25-coder-1_5b-llamacpp",
            provider="llamacpp",
            model="qwen2.5-coder:1.5b",
            quality=0.68,
            reliability=1.0,
            latency_ms=11927.037,
            sample_count=5,
            benchmark_verified=True,
        ),
        LocalCandidateEvidence(
            candidate_id=
                "qwen25-coder-7b-ollama",
            provider="ollama",
            model="qwen2.5-coder:7b",
            quality=0.82,
            reliability=1.0,
            latency_ms=51738.21,
            sample_count=5,
            benchmark_verified=True,
        ),
        LocalCandidateEvidence(
            candidate_id=
                "qwen25-coder-14b-ollama",
            provider="ollama",
            model="qwen2.5-coder:14b",
            quality=0.90,
            reliability=1.0,
            latency_ms=128399.919,
            sample_count=5,
            benchmark_verified=True,
        ),
        LocalCandidateEvidence(
            candidate_id=
                "qwen3-coder-30b-ollama",
            provider="ollama",
            model="qwen3-coder:30b",
            quality=0.95,
            reliability=1.0,
            latency_ms=38382.794,
            sample_count=5,
            benchmark_verified=True,
        ),
    )


def test_fast_profile_uses_healthy_1_5b():
    result = recommend_registered_local(
        candidates(),
        registry=build_runtime_registry(
            probe=healthy
        ),
        quality_floor=0.65,
        latency_ceiling_ms=15000,
    )

    assert (
        result.selected_model
        == "qwen2.5-coder:1.5b"
    )

    assert result.route_applied is False
    assert result.can_execute is False
    assert result.production_authority is False


def test_strong_profile_uses_healthy_30b():
    result = recommend_registered_local(
        candidates(),
        registry=build_runtime_registry(
            probe=healthy
        ),
        quality_floor=0.85,
        latency_ceiling_ms=60000,
    )

    assert (
        result.selected_model
        == "qwen3-coder:30b"
    )

    assert result.route_applied is False
    assert result.can_execute is False
    assert result.production_authority is False


def test_offline_nodes_produce_no_recommendation():
    result = recommend_registered_local(
        candidates(),
        registry=build_runtime_registry(
            probe=offline
        ),
        quality_floor=0.65,
        latency_ceiling_ms=60000,
    )

    assert result.selected_model is None
    assert result.route_applied is False
    assert result.can_execute is False
    assert result.production_authority is False

    assert (
        "canonical_node_health_applied"
        in result.reason_codes
    )
