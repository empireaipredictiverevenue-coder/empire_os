"""Offline evaluation + shadow records for typed decision providers.

Provider-neutral. No network calls, credentials, routing mutation, or side
effects. It evaluates already-observed provider outputs against labeled cases.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, asdict
from math import ceil
from statistics import mean
from typing import Any, Iterable, Mapping, Sequence


def _text(v: Any) -> str:
    return str(v or "").strip()


def _num(v: Any, name: str) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    return x


def _prob(v: Any, name: str) -> float:
    x = _num(v, name)
    if not 0 <= x <= 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return x


@dataclass(frozen=True)
class EvalObservation:
    case_id: str
    task_key: str
    provider_key: str
    model_key: str
    ground_truth: str
    predicted: str
    confidence: float
    latency_ms: float
    input_tokens: int | None
    cost_cents: float | None
    source_ref: str

    def validate(self) -> None:
        for field in (
            "case_id", "task_key", "provider_key", "model_key",
            "ground_truth", "predicted", "source_ref",
        ):
            if not _text(getattr(self, field)):
                raise ValueError(f"{field} required")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if self.latency_ms < 0:
            raise ValueError("latency_ms must be nonnegative")
        if self.input_tokens is not None and self.input_tokens < 0:
            raise ValueError("input_tokens must be nonnegative")
        if self.cost_cents is not None and self.cost_cents < 0:
            raise ValueError("cost_cents must be nonnegative")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


def observation_from_mapping(raw: Mapping[str, Any]) -> EvalObservation:
    input_tokens = raw.get("input_tokens")
    if input_tokens is not None:
        input_tokens = int(input_tokens)
    cost_cents = raw.get("cost_cents")
    if cost_cents is not None:
        cost_cents = _num(cost_cents, "cost_cents")

    obs = EvalObservation(
        case_id=_text(raw.get("case_id")),
        task_key=_text(raw.get("task_key")),
        provider_key=_text(raw.get("provider_key")),
        model_key=_text(raw.get("model_key")),
        ground_truth=_text(raw.get("ground_truth")),
        predicted=_text(raw.get("predicted")),
        confidence=_prob(raw.get("confidence"), "confidence"),
        latency_ms=_num(raw.get("latency_ms"), "latency_ms"),
        input_tokens=input_tokens,
        cost_cents=cost_cents,
        source_ref=_text(raw.get("source_ref")),
    )
    obs.validate()
    return obs


def _percentile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, ceil(q * len(ordered)) - 1))
    return ordered[idx]


def _macro_f1(rows: Sequence[EvalObservation]) -> float:
    labels = sorted({r.ground_truth for r in rows} | {r.predicted for r in rows})
    f1s = []
    for label in labels:
        tp = sum(1 for r in rows if r.ground_truth == label and r.predicted == label)
        fp = sum(1 for r in rows if r.ground_truth != label and r.predicted == label)
        fn = sum(1 for r in rows if r.ground_truth == label and r.predicted != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall else 0.0
        )
        f1s.append(f1)
    return mean(f1s) if f1s else 0.0


def _confidence_brier(rows: Sequence[EvalObservation]) -> float:
    # Binary correctness calibration: confidence should estimate P(prediction correct).
    return mean(
        (r.confidence - (1.0 if r.predicted == r.ground_truth else 0.0)) ** 2
        for r in rows
    )


def _calibration_buckets(
    rows: Sequence[EvalObservation],
    bucket_count: int = 10,
) -> list[dict[str, Any]]:
    buckets: dict[int, list[EvalObservation]] = defaultdict(list)
    for row in rows:
        idx = min(bucket_count - 1, int(row.confidence * bucket_count))
        buckets[idx].append(row)

    result = []
    for idx in range(bucket_count):
        members = buckets.get(idx, [])
        if not members:
            continue
        result.append({
            "lower": round(idx / bucket_count, 2),
            "upper": round((idx + 1) / bucket_count, 2),
            "sample_count": len(members),
            "mean_confidence": round(mean(r.confidence for r in members), 6),
            "observed_accuracy": round(
                mean(1.0 if r.predicted == r.ground_truth else 0.0 for r in members),
                6,
            ),
        })
    return result


def evaluate_provider_outputs(
    rows: Iterable[Mapping[str, Any]],
    *,
    minimum_samples: int = 20,
) -> dict[str, Any]:
    if minimum_samples < 1:
        raise ValueError("minimum_samples must be positive")

    observations = [observation_from_mapping(raw) for raw in rows]
    if not observations:
        return {
            "schema_version": "typed_decision_eval.v1",
            "available": False,
            "reason": "no_observations",
            "execution_authority": "none",
        }

    task_keys = {r.task_key for r in observations}
    provider_keys = {r.provider_key for r in observations}
    model_keys = {r.model_key for r in observations}
    if len(task_keys) != 1:
        raise ValueError("evaluation batch must contain one task_key")
    if len(provider_keys) != 1:
        raise ValueError("evaluation batch must contain one provider_key")
    if len(model_keys) != 1:
        raise ValueError("evaluation batch must contain one model_key")

    n = len(observations)
    correct = sum(1 for r in observations if r.predicted == r.ground_truth)
    latencies = [r.latency_ms for r in observations]

    known_costs = [r.cost_cents for r in observations if r.cost_cents is not None]
    known_tokens = [r.input_tokens for r in observations if r.input_tokens is not None]
    total_cost = sum(known_costs) if len(known_costs) == n else None
    total_tokens = sum(known_tokens) if len(known_tokens) == n else None
    cost_per_million_tokens_cents = None
    if total_cost is not None and total_tokens and total_tokens > 0:
        cost_per_million_tokens_cents = total_cost * 1_000_000 / total_tokens

    return {
        "schema_version": "typed_decision_eval.v1",
        "available": n >= minimum_samples,
        "reason": None if n >= minimum_samples else "insufficient_samples",
        "task_key": next(iter(task_keys)),
        "provider_key": next(iter(provider_keys)),
        "model_key": next(iter(model_keys)),
        "sample_count": n,
        "minimum_samples": minimum_samples,
        "accuracy": round(correct / n, 6),
        "macro_f1": round(_macro_f1(observations), 6),
        "confidence_brier_score": round(_confidence_brier(observations), 6),
        "calibration_buckets": _calibration_buckets(observations),
        "p50_latency_ms": round(_percentile(latencies, .50), 3),
        "p95_latency_ms": round(_percentile(latencies, .95), 3),
        "mean_latency_ms": round(mean(latencies), 3),
        "total_cost_cents": round(total_cost, 6) if total_cost is not None else None,
        "total_input_tokens": total_tokens,
        "cost_per_million_input_tokens_cents": (
            round(cost_per_million_tokens_cents, 6)
            if cost_per_million_tokens_cents is not None else None
        ),
        "source_refs": sorted({r.source_ref for r in observations}),
        "provider_activation": False,
        "production_routing": False,
        "execution_authority": "none",
    }


def compare_eval_reports(reports: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    reviewed = []
    for raw in reports:
        if raw.get("available") is not True:
            continue
        required = (
            "provider_key", "model_key", "task_key", "sample_count",
            "accuracy", "macro_f1", "confidence_brier_score",
            "p95_latency_ms",
        )
        if any(raw.get(k) is None for k in required):
            continue
        reviewed.append({
            "provider_key": _text(raw.get("provider_key")),
            "model_key": _text(raw.get("model_key")),
            "task_key": _text(raw.get("task_key")),
            "sample_count": int(raw.get("sample_count")),
            "accuracy": _num(raw.get("accuracy"), "accuracy"),
            "macro_f1": _num(raw.get("macro_f1"), "macro_f1"),
            "confidence_brier_score": _num(
                raw.get("confidence_brier_score"), "confidence_brier_score"
            ),
            "p95_latency_ms": _num(raw.get("p95_latency_ms"), "p95_latency_ms"),
            "cost_per_million_input_tokens_cents": raw.get(
                "cost_per_million_input_tokens_cents"
            ),
        })

    tasks = {r["task_key"] for r in reviewed}
    if len(tasks) > 1:
        raise ValueError("provider comparison must use one task_key")

    # Do not pick a production winner. Sort for operator review by accuracy,
    # calibration, latency in that order.
    reviewed.sort(
        key=lambda r: (
            r["accuracy"],
            -r["confidence_brier_score"],
            -r["p95_latency_ms"],
            r["provider_key"],
        ),
        reverse=True,
    )
    for idx, item in enumerate(reviewed, 1):
        item["review_rank"] = idx

    return {
        "schema_version": "typed_decision_eval_comparison.v1",
        "task_key": next(iter(tasks)) if tasks else None,
        "reports": reviewed,
        "winner_selected": False,
        "production_provider_selected": False,
        "provider_activation": False,
        "execution_authority": "none",
    }


def build_shadow_decision(raw: Mapping[str, Any]) -> dict[str, Any]:
    required = (
        "shadow_id",
        "task_key",
        "case_ref",
        "incumbent_provider",
        "incumbent_decision",
        "candidate_provider",
        "candidate_decision",
        "candidate_confidence",
        "decision_schema_ref",
    )
    missing = [field for field in required if raw.get(field) in (None, "")]
    if missing:
        raise ValueError("missing shadow fields: " + ",".join(missing))

    confidence = _prob(raw.get("candidate_confidence"), "candidate_confidence")
    agreement = _text(raw.get("incumbent_decision")) == _text(
        raw.get("candidate_decision")
    )

    return {
        "schema_version": "typed_decision_shadow.v1",
        "shadow_id": _text(raw.get("shadow_id")),
        "task_key": _text(raw.get("task_key")),
        "case_ref": _text(raw.get("case_ref")),
        "decision_schema_ref": _text(raw.get("decision_schema_ref")),
        "incumbent": {
            "provider": _text(raw.get("incumbent_provider")),
            "decision": _text(raw.get("incumbent_decision")),
        },
        "candidate": {
            "provider": _text(raw.get("candidate_provider")),
            "decision": _text(raw.get("candidate_decision")),
            "confidence": confidence,
        },
        "agreement": agreement,
        "verified_outcome_ref": _text(raw.get("verified_outcome_ref")) or None,
        "candidate_controlled_live_routing": False,
        "execution_performed": False,
        "execution_authority": "none",
    }


def summarize_shadow_records(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    records = [build_shadow_decision(row) for row in rows]
    if not records:
        return {
            "schema_version": "typed_decision_shadow_summary.v1",
            "available": False,
            "reason": "no_shadow_records",
            "execution_authority": "none",
        }
    tasks = {r["task_key"] for r in records}
    if len(tasks) != 1:
        raise ValueError("shadow summary must contain one task_key")
    agreements = sum(1 for r in records if r["agreement"])
    outcome_linked = sum(1 for r in records if r["verified_outcome_ref"])
    return {
        "schema_version": "typed_decision_shadow_summary.v1",
        "available": True,
        "task_key": next(iter(tasks)),
        "sample_count": len(records),
        "agreement_rate": round(agreements / len(records), 6),
        "disagreement_count": len(records) - agreements,
        "outcome_linked_count": outcome_linked,
        "candidate_controlled_live_routing": False,
        "production_routing": False,
        "execution_authority": "none",
    }
