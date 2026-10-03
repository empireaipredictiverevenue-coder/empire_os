#!/usr/bin/env python3

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import statistics

from empire_os.hybrid_compute_benchmark import (
    BenchmarkCase,
    CandidateIdentity,
    execute_candidate,
)
from empire_os.llm_gateway import LLMGateway


ROOT = Path(__file__).resolve().parents[1]

OUTDIR = (
    ROOT
    / "runtime"
    / "hybrid_compute"
)

CASES = (
    BenchmarkCase(
        case_id="authority_separation",
        task="reasoning",
        prompt=(
            "Explain why an AI compute router must keep "
            "model selection separate from execution authority. "
            "Include route, execution, authority and fail closed."
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
            "Summarize this rule: observe current state, diagnose "
            "the cause, make one bounded change, verify with tests "
            "and live evidence, record the result, and never mark "
            "failures complete."
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
            "Give a concise design for a production worker that may "
            "receive the same job twice. Include idempotency, "
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
            "Explain how a production decision system should handle "
            "missing cost and quality evidence. Include unknown, "
            "evidence, estimation and promotion."
        ),
        required_groups=(
            ("unknown",),
            ("evidence",),
            ("estimate", "estimation"),
            ("promotion", "promote"),
        ),
    ),
)


CANDIDATES = (
    {
        "model_id":
            "local-qwen25-coder-1.5b",
        "provider":
            "llamacpp",
        "model":
            "qwen2.5-coder:1.5b",
        "deployment":
            "local",
        "registry_status":
            "CANONICAL",
    },
    {
        "model_id":
            "shadow-qwen25-coder-7b",
        "provider":
            "ollama",
        "model":
            "qwen2.5-coder:7b",
        "deployment":
            "local",
        "registry_status":
            "OBSERVED_NOT_CANONICAL",
    },
    {
        "model_id":
            "shadow-qwen25-coder-14b",
        "provider":
            "ollama",
        "model":
            "qwen2.5-coder:14b",
        "deployment":
            "local",
        "registry_status":
            "OBSERVED_NOT_CANONICAL",
    },
    {
        "model_id":
            "shadow-qwen3-coder-30b",
        "provider":
            "ollama",
        "model":
            "qwen3-coder:30b",
        "deployment":
            "local",
        "registry_status":
            "OBSERVED_NOT_CANONICAL",
    },
)


def utcnow():
    return datetime.now(
        timezone.utc
    ).isoformat()


def summary(rows):
    if not rows:
        return {
            "sample_count": 0,
            "successful_calls": 0,
            "success_rate": None,
            "mean_coverage": None,
            "mean_latency_ms": None,
            "median_latency_ms": None,
        }

    successful = [
        r
        for r in rows
        if r["ok"] is True
    ]

    return {
        "sample_count": len(rows),
        "successful_calls": len(
            successful
        ),
        "success_rate": round(
            len(successful)
            / len(rows),
            6,
        ),
        "mean_coverage": round(
            statistics.fmean(
                float(
                    r["coverage"]
                )
                for r in rows
            ),
            6,
        ),
        "mean_latency_ms": round(
            statistics.fmean(
                float(
                    r["latency_ms"]
                )
                for r in rows
            ),
            3,
        ),
        "median_latency_ms": round(
            statistics.median(
                float(
                    r["latency_ms"]
                )
                for r in rows
            ),
            3,
        ),
    }


def main():
    gateway = LLMGateway()

    all_runs = []

    for config in CANDIDATES:
        identity = CandidateIdentity(
            model_id=config["model_id"],
            provider=config["provider"],
            model=config["model"],
            deployment="local",

            # Total infrastructure cost has not
            # been benchmarked, so preserve unknown.
            cost_known=False,
            estimated_cost=None,
        )

        try:
            client = gateway._client(
                config["provider"],
                config["model"],
                180,
            )
        except Exception as exc:
            for case in CASES:
                all_runs.append({
                    "lane":
                        "local_ladder_shadow",
                    "registry_status":
                        config[
                            "registry_status"
                        ],
                    "case_id":
                        case.case_id,
                    "candidate": {
                        "model_id":
                            identity.model_id,
                        "provider":
                            identity.provider,
                        "model":
                            identity.model,
                        "deployment":
                            identity.deployment,
                        "cost_known":
                            False,
                        "estimated_cost":
                            None,
                    },
                    "ok": False,
                    "failure":
                        f"client_init:"
                        f"{type(exc).__name__}",
                    "coverage": 0.0,
                    "latency_ms": 0.0,
                    "raw_output_persisted":
                        False,
                })
            continue

        for case in CASES:
            print(
                f"RUN "
                f"{config['model']} "
                f"{case.case_id}",
                flush=True,
            )

            row = execute_candidate(
                client=client,
                candidate=identity,
                case=case,
            )

            row["lane"] = (
                "local_ladder_shadow"
            )

            row["registry_status"] = (
                config["registry_status"]
            )

            all_runs.append(row)

            print(
                json.dumps(
                    {
                        "model":
                            config["model"],
                        "case":
                            case.case_id,
                        "ok":
                            row["ok"],
                        "coverage":
                            row["coverage"],
                        "latency_ms":
                            row["latency_ms"],
                        "failure":
                            row["failure"],
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

    summaries = {}

    for config in CANDIDATES:
        model_id = config["model_id"]

        rows = [
            row
            for row in all_runs
            if (
                row["candidate"][
                    "model_id"
                ]
                == model_id
            )
        ]

        summaries[model_id] = {
            **summary(rows),
            "provider":
                config["provider"],
            "model":
                config["model"],
            "registry_status":
                config[
                    "registry_status"
                ],
        }

    payload = {
        "schema_version":
            "empire.hybrid_compute."
            "local-ladder.v1",
        "observed_at":
            utcnow(),
        "mode":
            "shadow_benchmark",
        "production_authority":
            False,
        "route_applied":
            False,
        "commercial_authority":
            False,
        "business_data_used":
            False,
        "raw_model_output_persisted":
            False,
        "promotion_ready":
            False,
        "candidate_count":
            len(CANDIDATES),
        "case_count":
            len(CASES),
        "run_count":
            len(all_runs),
        "summaries":
            summaries,
        "runs":
            all_runs,
    }

    OUTDIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    stamp = datetime.now(
        timezone.utc
    ).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    path = OUTDIR / (
        "local_ladder_"
        f"{stamp}.json"
    )

    latest = OUTDIR / (
        "local_ladder_latest.json"
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
                "evidence_path":
                    str(path),
                "summaries":
                    summaries,
                "promotion_ready":
                    False,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
