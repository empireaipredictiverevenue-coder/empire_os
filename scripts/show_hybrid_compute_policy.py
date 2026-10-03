#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from empire_os.hybrid_compute_policy import (
    derive_provider_observations,
    load_local_evidence,
    recommend_local,
)


ROOT = Path(__file__).resolve().parents[1]

LOCAL = (
    ROOT
    / "runtime"
    / "hybrid_compute"
    / "local_escalation_v2_latest.json"
)

V3 = (
    ROOT
    / "runtime"
    / "hybrid_compute"
    / "v3_matched_benchmark_latest.json"
)


candidates = load_local_evidence(
    LOCAL
)

provider_health = (
    derive_provider_observations(
        V3
    )
)


profiles = {
    "bounded_fast": {
        "quality_floor": 0.65,
        "latency_ceiling_ms": 20000,
    },
    "standard": {
        "quality_floor": 0.80,
        "latency_ceiling_ms": 60000,
    },
    "high_quality": {
        "quality_floor": 0.90,
        "latency_ceiling_ms": 60000,
    },
    "very_high_quality": {
        "quality_floor": 0.96,
        "latency_ceiling_ms": None,
    },
}


decisions = {
    name: asdict(
        recommend_local(
            candidates,
            **config,
        )
    )
    for name, config
    in profiles.items()
}


payload = {
    "policy_version":
        "empire-hybrid-compute-policy-v1",
    "mode":
        "shadow",
    "route_applied":
        False,
    "production_authority":
        False,
    "economic_ready":
        False,
    "provider_observations": [
        asdict(row)
        for row
        in provider_health
    ],
    "local_candidates": [
        asdict(row)
        for row
        in candidates
    ],
    "profiles":
        decisions,
}


print(
    json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )
)
