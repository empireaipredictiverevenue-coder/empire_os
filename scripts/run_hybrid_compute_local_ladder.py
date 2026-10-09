#!/usr/bin/env python3

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import statistics
import argparse
from dataclasses import asdict
import sys

# Support direct invocation without PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from empire_os.hybrid_compute_benchmark import (
    BenchmarkCase,
    CandidateIdentity,
    execute_candidate,
)
from empire_os.model_registry import ModelRegistry
from empire_os.local_benchmark_preflight import LocalBenchmarkClient, preflight


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


LOCAL_CANDIDATE_IDS = (
    "local-qwen25-coder-1.5b",
    "local-qwen25-coder-7b",
    "local-qwen25-coder-14b",
    "local-qwen3-coder-30b",
)


def canonical_candidates():
    """Resolve benchmark identities from the canonical model registry.

    The benchmark owns only the bounded candidate set. Provider, physical
    model identity, deployment and canonical status come from ModelRegistry.
    """
    registry = ModelRegistry()
    candidates = []

    for model_id in LOCAL_CANDIDATE_IDS:
        spec = registry.get(model_id)

        if spec is None:
            raise RuntimeError(
                f"canonical benchmark model missing from registry: {model_id}"
            )

        if spec.deployment != "local":
            raise RuntimeError(
                f"benchmark candidate is not local: {model_id}"
            )

        if spec.provider not in {"ollama", "llamacpp"}:
            raise RuntimeError(
                f"unsupported local benchmark provider: "
                f"{model_id}:{spec.provider}"
            )

        candidates.append(
            {
                "model_id": spec.model_id,
                "provider": spec.provider,
                "model": spec.model,
                "deployment": spec.deployment,
                "registry_status": "CANONICAL",
            }
        )

    return tuple(candidates)


CANDIDATES = canonical_candidates()


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


# Benchmark thresholds, not a governed production promotion policy.
QUALITY_THRESHOLDS = dict(success_rate=1.0, mean_coverage=0.9, minimum_case_coverage=0.8)
PRIOR_1_5B_EVIDENCE = dict(
    source='user_supplied_prior_benchmark', success_rate=1.0, mean_coverage=0.7375,
    production_verification_coverage=0.2, assessment='available but quality-limited')


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Bounded local shadow benchmark; no promotion')
    parser.add_argument('--candidate', choices=[c['model_id'] for c in CANDIDATES])
    parser.add_argument('--preflight-only', action='store_true')
    parser.add_argument('--preflight-timeout', type=float, default=25)
    parser.add_argument('--case-timeout', type=float, default=45)
    parser.add_argument('--output', type=Path, default=OUTDIR / 'local_ladder_latest.json')
    args = parser.parse_args(argv)
    if not 0 < args.preflight_timeout <= 120:
        parser.error('--preflight-timeout must be >0 and <=120 seconds')
    if not 0 < args.case_timeout <= 90:
        parser.error('--case-timeout must be >0 and <=90 seconds')
    return args


def checkpoint(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def run(args, *, client_factory=LocalBenchmarkClient, admit=preflight):
    candidates = [c for c in CANDIDATES if not args.candidate or c['model_id'] == args.candidate]
    payload = dict(
        schema_version='empire.hybrid_compute.local-ladder.v2', observed_at=utcnow(),
        mode='preflight_only' if args.preflight_only else 'shadow_benchmark',
        production_authority=False, route_applied=False, commercial_authority=False,
        business_data_used=False, raw_model_output_persisted=False, promotion_ready=False,
        candidate_count=len(candidates), case_count=len(CASES), run_count=0,
        actual_call_count=0, complete=False, summaries={}, runs=[],
        quality_thresholds=QUALITY_THRESHOLDS, prior_1_5b_evidence=PRIOR_1_5B_EVIDENCE,
        preflight_timeout_seconds=args.preflight_timeout, case_timeout_seconds=args.case_timeout,
    )
    checkpoint(args.output, payload)
    for config in candidates:
        identity = CandidateIdentity(config['model_id'], config['provider'], config['model'], 'local', False, None)
        client = client_factory(config, args.case_timeout)
        admission = admit(client, args.preflight_timeout)
        rows = []
        report = dict(provider=config['provider'], model=config['model'],
                      registry_status=config['registry_status'], **admission,
                      promotion_ready=False, promotion_eligible=False)
        payload['summaries'][config['model_id']] = report
        # Model-major order, identical context and keep_alive avoid deliberate
        # per-case reloads. Eviction/concurrent callers remain external.
        for case in CASES:
            reason = admission['skipped_reason'] or ('preflight_only' if args.preflight_only else None)
            if reason:
                row = dict(case_id=case.case_id, case_fingerprint=case.fingerprint(),
                           candidate=asdict(identity), ok=False, failure=None,
                           coverage=0.0, latency_ms=0.0, raw_output_persisted=False,
                           observation_status='skipped', model_call_executed=False,
                           skipped_reason=reason)
            else:
                row = execute_candidate(client=client, candidate=identity, case=case)
                row.update(observation_status='executed', model_call_executed=True, skipped_reason=None)
            row.update(lane='local_ladder_shadow', registry_status=config['registry_status'])
            rows.append(row)
            payload['runs'].append(row)
            payload['run_count'] += 1
            payload['actual_call_count'] += int(row['model_call_executed'])
            report.update(summary([r for r in rows if r['model_call_executed']]))
            report['skipped_count'] = sum(not r['model_call_executed'] for r in rows)
            report['status'] = admission['skipped_reason'] or 'viable_not_benchmarked'
            if not args.preflight_only and admission['preflight_ok'] and len(rows) == len(CASES):
                passed = (report['success_rate'] == QUALITY_THRESHOLDS['success_rate']
                          and report['mean_coverage'] >= QUALITY_THRESHOLDS['mean_coverage']
                          and min(r['coverage'] for r in rows) >= QUALITY_THRESHOLDS['minimum_case_coverage'])
                report['status'] = 'benchmark_passed' if passed else 'viable_but_quality_failed'
                report['promotion_eligible'] = passed
                # Governed promotion evidence/approval is outside this runner.
            checkpoint(args.output, payload)
        print(json.dumps({config['model_id']: report}, sort_keys=True), flush=True)
    payload['complete'] = True
    checkpoint(args.output, payload)
    return payload


def main(argv=None):
    args = parse_args(argv)
    run(args)
    print(json.dumps({'evidence_path': str(args.output), 'promotion_ready': False}))


if __name__ == '__main__':
    main()
