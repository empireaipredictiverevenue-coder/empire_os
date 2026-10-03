import json

from empire_os.hybrid_compute_policy import (
    derive_provider_observations,
    load_local_evidence,
    recommend_local,
)


def local_payload():
    return {
        "complete": True,
        "production_authority": False,
        "reports": {
            "small": {
                "provider": "llamacpp",
                "model": "small",
                "mean_coverage": 0.68,
                "reliability": 1.0,
                "mean_latency_ms": 12000,
                "sample_count": 5,
                "benchmark_verified": True,
            },
            "medium": {
                "provider": "ollama",
                "model": "medium",
                "mean_coverage": 0.82,
                "reliability": 1.0,
                "mean_latency_ms": 52000,
                "sample_count": 5,
                "benchmark_verified": True,
            },
            "large": {
                "provider": "ollama",
                "model": "large",
                "mean_coverage": 0.95,
                "reliability": 1.0,
                "mean_latency_ms": 38000,
                "sample_count": 5,
                "benchmark_verified": True,
            },
        },
    }


def test_low_quality_floor_prefers_fast_small(
    tmp_path,
):
    path = tmp_path / "local.json"

    path.write_text(
        json.dumps(
            local_payload()
        )
    )

    candidates = (
        load_local_evidence(path)
    )

    result = recommend_local(
        candidates,
        quality_floor=0.65,
    )

    assert (
        result.selected_candidate_id
        == "small"
    )

    assert result.route_applied is False
    assert result.can_execute is False
    assert (
        result.production_authority
        is False
    )


def test_high_quality_floor_uses_measured_large(
    tmp_path,
):
    path = tmp_path / "local.json"

    path.write_text(
        json.dumps(
            local_payload()
        )
    )

    result = recommend_local(
        load_local_evidence(path),
        quality_floor=0.80,
    )

    # The larger observed candidate beats "medium"
    # on both quality and measured latency.
    assert (
        result.selected_candidate_id
        == "large"
    )


def test_quality_above_local_evidence_escalates(
    tmp_path,
):
    path = tmp_path / "local.json"

    path.write_text(
        json.dumps(
            local_payload()
        )
    )

    result = recommend_local(
        load_local_evidence(path),
        quality_floor=0.99,
    )

    assert (
        result.selected_candidate_id
        is None
    )

    assert (
        "no_local_candidate_meets_constraints"
        in result.reason_codes
    )


def test_latency_ceiling_fails_closed(
    tmp_path,
):
    path = tmp_path / "local.json"

    path.write_text(
        json.dumps(
            local_payload()
        )
    )

    result = recommend_local(
        load_local_evidence(path),
        quality_floor=0.80,
        latency_ceiling_ms=10000,
    )

    assert (
        result.selected_candidate_id
        is None
    )


def test_provider_hard_block_and_degraded(
    tmp_path,
):
    path = tmp_path / "v3.json"

    path.write_text(
        json.dumps({
            "runs": [
                {
                    "lane":
                        "canonical_current",
                    "candidate": {
                        "model_id":
                            "opencode-free",
                        "provider":
                            "opencode",
                    },
                    "ok": False,
                    "failure":
                        "zen_failed HTTP 403",
                },
                {
                    "lane":
                        "canonical_current",
                    "candidate": {
                        "model_id":
                            "gemini",
                        "provider":
                            "gemini",
                    },
                    "ok": False,
                    "failure":
                        "HTTP Error 503: "
                        "Service Unavailable",
                },
                {
                    "lane":
                        "canonical_current",
                    "candidate": {
                        "model_id":
                            "gemini",
                        "provider":
                            "gemini",
                    },
                    "ok": True,
                    "failure": None,
                },
            ]
        })
    )

    observations = {
        row.model_id: row
        for row in (
            derive_provider_observations(
                path
            )
        )
    }

    assert (
        observations[
            "opencode-free"
        ].status
        == "blocked_observed"
    )

    assert (
        observations[
            "opencode-free"
        ].hard_block_observed
        is True
    )

    assert (
        observations[
            "gemini"
        ].status
        == "degraded_observed"
    )

    assert (
        observations[
            "gemini"
        ].transient_failure_observed
        is True
    )
