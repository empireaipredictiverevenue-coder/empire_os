#!/usr/bin/env python3
"""Run the first Empire Hybrid Compute matched shadow benchmark."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.hybrid_compute_benchmark import (
    BenchmarkCase,
    candidate_identity,
    execute_candidate,
    summarize_runs,
)
from empire_os.llm_gateway import LLMGateway
from empire_os.model_registry import ModelRegistry
from empire_os.model_router import ModelRouter


ROOT = Path(__file__).resolve().parents[1]

OUTPUT_DIR = (
    ROOT
    / "runtime"
    / "hybrid_compute"
)

LOCAL_MODEL_ID = (
    "local-qwen25-coder-1.5b"
)


CASES = (
    BenchmarkCase(
        case_id="authority_separation",
        task="reasoning",
        prompt=(
            "Explain why an AI compute router must keep "
            "model selection separate from execution authority. "
            "Include the concepts route, execution, authority, "
            "and fail closed."
        ),
        required_groups=(
            ("route", "routing"),
            ("execution", "execute"),
            ("authority", "permission"),
            ("fail closed", "fail-closed"),
        ),
    ),
    BenchmarkCase(
        case_id="production_verification",
        task="summarization",
        prompt=(
            "Summarize this operating rule: observe the current "
            "state, diagnose the cause, make one bounded change, "
            "verify it with tests and live evidence, record the "
            "result, and do not mark failures as complete."
        ),
        required_groups=(
            ("observe", "observation"),
            ("diagnose", "cause"),
            ("test", "verify"),
            ("evidence", "live"),
            ("failure", "failed"),
        ),
    ),
    BenchmarkCase(
        case_id="safe_worker_design",
        task="coding",
        prompt=(
            "Give a concise design for a production worker that "
            "may receive the same job twice. Include idempotency, "
            "validation, bounded retry, checkpointing and tests. "
            "Do not write code."
        ),
        required_groups=(
            ("idempotent", "idempotency"),
            ("validat",),
            ("retry",),
            ("checkpoint",),
            ("test",),
        ),
    ),
    BenchmarkCase(
        case_id="unknown_truth",
        task="reasoning",
        prompt=(
            "Explain how a production decision system should "
            "handle missing cost and quality evidence. Include "
            "unknown, evidence, estimation, and promotion."
        ),
        required_groups=(
            ("unknown",),
            ("evidence",),
            ("estimate", "estimation"),
            ("promotion", "promote"),
        ),
    ),
)


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def safe_current_client(
    *,
    gateway: LLMGateway,
    case: BenchmarkCase,
):
    decision = gateway.route(
        [
            {
                "role": "user",
                "content": case.prompt,
            }
        ],
        task=case.task,
        stakes="normal",
        require_reasoning=False,
        require_vision=False,
    )

    spec = decision.model

    identity = candidate_identity(
        spec,
        estimated_cost=(
            decision.estimated_cost
        ),
    )

    client = gateway._client(
        spec.provider,
        spec.model,
        60,
    )

    return decision, identity, client


def main() -> int:
    registry = ModelRegistry()
    router = ModelRouter(registry)
    gateway = LLMGateway(
        registry=registry,
        router=router,
    )

    local_spec = registry.get(
        LOCAL_MODEL_ID
    )

    if local_spec is None:
        raise RuntimeError(
            f"{LOCAL_MODEL_ID} missing"
        )

    if (
        str(
            local_spec.deployment
            or ""
        ).lower()
        != "local"
    ):
        raise RuntimeError(
            "local benchmark candidate "
            "is not canonically local"
        )

    if (
        str(
            local_spec.health
            or ""
        ).lower()
        != "local_verified"
    ):
        raise RuntimeError(
            "local benchmark candidate "
            "is not local_verified"
        )

    local_identity = (
        candidate_identity(
            local_spec,
            estimated_cost=0.0,
        )
    )

    local_client = gateway._client(
        local_spec.provider,
        local_spec.model,
        60,
    )

    health_method = getattr(
        local_client,
        "health",
        None,
    )

    if (
        callable(health_method)
        and health_method() is not True
    ):
        raise RuntimeError(
            "local candidate unhealthy"
        )

    runs = []

    for case in CASES:
        decision, current_identity, (
            current_client
        ) = safe_current_client(
            gateway=gateway,
            case=case,
        )

        current_run = execute_candidate(
            client=current_client,
            candidate=current_identity,
            case=case,
        )

        current_run["lane"] = (
            "canonical_current"
        )

        current_run["router"] = {
            "route": decision.route,
            "score": decision.score,
            "reasoning_gain": (
                decision.reasoning_gain
            ),
            "rationale": (
                decision.rationale
            ),
        }

        local_run = execute_candidate(
            client=local_client,
            candidate=local_identity,
            case=case,
        )

        local_run["lane"] = (
            "forced_local_shadow"
        )

        runs.extend(
            (
                current_run,
                local_run,
            )
        )

        print(
            json.dumps(
                {
                    "case": case.case_id,
                    "canonical": {
                        "model_id":
                            current_identity.model_id,
                        "provider":
                            current_identity.provider,
                        "ok":
                            current_run["ok"],
                        "coverage":
                            current_run["coverage"],
                        "latency_ms":
                            current_run["latency_ms"],
                    },
                    "local": {
                        "model_id":
                            local_identity.model_id,
                        "provider":
                            local_identity.provider,
                        "ok":
                            local_run["ok"],
                        "coverage":
                            local_run["coverage"],
                        "latency_ms":
                            local_run["latency_ms"],
                    },
                },
                sort_keys=True,
            )
        )

    current_runs = [
        row
        for row in runs
        if row["lane"]
        == "canonical_current"
    ]

    local_runs = [
        row
        for row in runs
        if row["lane"]
        == "forced_local_shadow"
    ]

    payload = {
        "schema_version": (
            "empire.hybrid_compute."
            "matched-benchmark.v3"
        ),
        "observed_at": utc_now(),
        "mode": "shadow_benchmark",
        "production_authority": False,
        "route_applied": False,
        "commercial_authority": False,
        "business_data_used": False,
        "raw_model_output_persisted": False,
        "local_candidate_model_id": (
            LOCAL_MODEL_ID
        ),
        "case_count": len(CASES),
        "run_count": len(runs),
        "canonical_summary": (
            summarize_runs(
                current_runs
            )
        ),
        "local_summary": (
            summarize_runs(
                local_runs
            )
        ),
        "runs": runs,
        "promotion_ready": False,
        "promotion_reason": (
            "matched evidence only; "
            "repeatability and safety "
            "verification required"
        ),
    }

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    stamp = datetime.now(
        timezone.utc
    ).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    path = OUTPUT_DIR / (
        f"v3_matched_benchmark_{stamp}.json"
    )

    latest = (
        OUTPUT_DIR
        / "v3_matched_benchmark_latest.json"
    )

    encoded = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    ) + "\n"

    path.write_text(encoded)
    latest.write_text(encoded)

    print()
    print(
        json.dumps(
            {
                "evidence_path": str(path),
                "canonical_summary": (
                    payload[
                        "canonical_summary"
                    ]
                ),
                "local_summary": (
                    payload[
                        "local_summary"
                    ]
                ),
                "promotion_ready": False,
            },
            indent=2,
            sort_keys=True,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
