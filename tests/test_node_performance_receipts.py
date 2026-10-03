from datetime import (
    datetime,
    timedelta,
    timezone,
)
import json

import pytest

from empire_os.node_performance_receipts import (
    load_benchmark_receipts,
    performance_map,
    receipt_snapshot,
)


def payload(
    *,
    observed_at=None,
):
    return {
        "schema_version":
            "empire.local-escalation.v2",
        "complete": True,
        "completed_observation_count": 10,
        "expected_observation_count": 10,
        "production_authority": False,
        "route_changed": False,
        "winner_promoted": False,
        "execution_authority": "none",
        "observed_at": (
            observed_at
            or datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "reports": {
            "qwen25-coder-1_5b-llamacpp": {
                "provider": "llamacpp",
                "model":
                    "qwen2.5-coder:1.5b",
                "mean_coverage": 0.68,
                "reliability": 1.0,
                "mean_latency_ms": 11927.0,
                "sample_count": 5,
                "benchmark_verified": True,
            },
            "qwen3-coder-30b-ollama": {
                "provider": "ollama",
                "model":
                    "qwen3-coder:30b",
                "mean_coverage": 0.95,
                "reliability": 1.0,
                "mean_latency_ms": 33902.0,
                "sample_count": 5,
                "benchmark_verified": True,
            },
        },
    }


def write_payload(
    tmp_path,
    value,
):
    path = tmp_path / "evidence.json"

    path.write_text(
        json.dumps(value)
    )

    return path


def test_load_maps_exact_model_identity(
    tmp_path,
):
    receipts = load_benchmark_receipts(
        write_payload(
            tmp_path,
            payload(),
        ),
        source_commit="abc123",
    )

    assert set(receipts) == {
        "qwen25-coder-1_5b",
        "ollama-qwen3-coder-30b",
    }

    strong = receipts[
        "ollama-qwen3-coder-30b"
    ]

    assert strong.quality == 0.95
    assert strong.reliability == 1.0
    assert strong.matched_sample_count == 5
    assert strong.benchmark_verified is True

    assert (
        strong.economic_memory_verified
        is False
    )

    assert (
        strong.verified_outcome_score
        is None
    )

    assert (
        strong.infrastructure_cost_known
        is False
    )

    assert strong.marginal_cost_gbp == 0.0


def test_performance_map_never_invents_outcome(
    tmp_path,
):
    receipts = load_benchmark_receipts(
        write_payload(
            tmp_path,
            payload(),
        )
    )

    performance = performance_map(
        receipts
    )

    strong = performance[
        "ollama-qwen3-coder-30b"
    ]

    assert (
        strong.verified_outcome_score
        is None
    )

    assert (
        strong.economic_memory_verified
        is False
    )

    assert strong.benchmark_verified is True


def test_stale_benchmark_rejected(
    tmp_path,
):
    stale = (
        datetime.now(timezone.utc)
        - timedelta(days=30)
    ).isoformat()

    with pytest.raises(
        ValueError,
        match="stale",
    ):
        load_benchmark_receipts(
            write_payload(
                tmp_path,
                payload(
                    observed_at=stale,
                ),
            )
        )


def test_authority_contamination_rejected(
    tmp_path,
):
    value = payload()

    value["production_authority"] = True

    with pytest.raises(
        ValueError,
        match="authority",
    ):
        load_benchmark_receipts(
            write_payload(
                tmp_path,
                value,
            )
        )


def test_unknown_model_identity_rejected(
    tmp_path,
):
    value = payload()

    value["reports"] = {
        "mystery": {
            "provider": "unknown",
            "model": "mystery",
            "mean_coverage": 1.0,
            "reliability": 1.0,
            "mean_latency_ms": 1.0,
            "sample_count": 5,
            "benchmark_verified": True,
        }
    }

    with pytest.raises(
        ValueError,
        match="unrecognized",
    ):
        load_benchmark_receipts(
            write_payload(
                tmp_path,
                value,
            )
        )


def test_snapshot_preserves_zero_authority(
    tmp_path,
):
    receipts = load_benchmark_receipts(
        write_payload(
            tmp_path,
            payload(),
        )
    )

    snapshot = receipt_snapshot(
        receipts,
        source_path="evidence.json",
    )

    assert (
        snapshot["production_authority"]
        is False
    )

    assert snapshot["route_changed"] is False

    assert (
        snapshot["execution_authority"]
        == "none"
    )

    assert (
        snapshot[
            "verified_commercial_outcomes_used"
        ]
        is False
    )
