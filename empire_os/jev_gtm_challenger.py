"""JEV challenger evaluation against the existing frozen-dataset contracts.

Evaluates equal real-labelled holdouts only; never trains, routes traffic,
selects a provider or treats reviewer-supplied metadata as authentication.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from empire_os.typed_decision_dataset import (
    TASK_SCHEMAS, freeze_dataset, verify_frozen_dataset, dataset_readiness,
)
from empire_os.typed_decision_eval import (
    observation_from_mapping, evaluate_provider_outputs,
)


def _indexed(
    rows: Sequence[Mapping[str, Any]],
    cases: Mapping[str, Mapping[str, Any]],
    *,
    task_key: str,
) -> list[dict[str, Any]]:
    if len(rows) != len(cases):
        raise ValueError("evaluation rows do not cover identical holdout cases")
    ids = [row.get("case_id") for row in rows if isinstance(row, Mapping)]
    if len(ids) != len(rows) or len(set(ids)) != len(ids):
        raise ValueError("unknown or duplicate evaluation case")
    by_id: dict[str, dict[str, Any]] = {}
    for raw in rows:
        item = dict(raw)
        case_id = item.get("case_id")
        if not isinstance(case_id, str) or case_id not in cases or case_id in by_id:
            raise ValueError("unknown or duplicate evaluation case")
        case = cases[case_id]
        if (item.get("task_key") != task_key or
                item.get("ground_truth") != case["ground_truth"] or
                item.get("source_ref") != case["source_ref"]):
            raise ValueError("evaluation row contradicts frozen label evidence")
        if item.get("predicted") not in TASK_SCHEMAS[task_key]["labels"]:
            raise ValueError("prediction label not defined by canonical task")
        observation_from_mapping(item).validate()
        by_id[case_id] = item
    return [by_id[key] for key in sorted(cases)]


def evaluate_jev_gtm_challenger(
    *,
    dataset: Mapping[str, Any],
    incumbent_outputs: Sequence[Mapping[str, Any]],
    challenger_outputs: Sequence[Mapping[str, Any]],
    independent_review_refs: Sequence[str] = (),
    minimum_real_cases: int = 100,
    minimum_per_label: int = 20,
) -> dict[str, Any]:
    if minimum_real_cases < 100 or minimum_per_label < 1:
        raise ValueError("minimum real-case requirements cannot be relaxed")
    validity = verify_frozen_dataset(dataset)
    if not validity["valid"]:
        raise ValueError("frozen dataset hash mismatch")
    rebuilt = freeze_dataset(
        dataset["cases"],
        dataset_id=dataset["dataset_id"],
        version=dataset["version"],
    )
    tasks = rebuilt["task_keys"]
    if len(tasks) != 1:
        raise ValueError("holdout must contain exactly one canonical task")
    task = tasks[0]
    cases = {row["case_id"]: row for row in rebuilt["cases"]}
    incumbent = _indexed(incumbent_outputs, cases, task_key=task)
    challenger = _indexed(challenger_outputs, cases, task_key=task)
    for name, rows in (("incumbent", incumbent), ("challenger", challenger)):
        providers = {(row["provider_key"], row["model_key"]) for row in rows}
        if len(providers) != 1:
            raise ValueError(name + " must use one provider/model")
    if ({(r["provider_key"], r["model_key"]) for r in incumbent}
            == {(r["provider_key"], r["model_key"]) for r in challenger}):
        raise ValueError("incumbent and challenger must have different identities")
    n = len(cases)
    incumbent_report = evaluate_provider_outputs(
        incumbent, minimum_samples=minimum_real_cases,
    )
    challenger_report = evaluate_provider_outputs(
        challenger, minimum_samples=minimum_real_cases,
    )
    dataset_gate = dataset_readiness(rebuilt, minimum_per_label=minimum_per_label)
    evidence_reviews = sorted({ref.strip() for ref in independent_review_refs
                               if isinstance(ref, str) and ref.strip()})
    false_positive_interest = sum(
        item["predicted"] == "positive" and cases[item["case_id"]]["ground_truth"] != "positive"
        for item in challenger
    ) if task == "reply_classification" else None
    missed_unsubscribes = sum(
        cases[item["case_id"]]["ground_truth"] == "unsubscribe"
        and item["predicted"] != "unsubscribe"
        for item in challenger
    ) if task == "reply_classification" else None
    blockers: list[str] = []
    if rebuilt["synthetic_test_fixture_count"]:
        blockers.append("synthetic_cases_cannot_prove_production_readiness")
    if not dataset_gate["ready_for_provider_promotion_eval"]:
        blockers.append("dataset_label_coverage_incomplete")
    if n < minimum_real_cases:
        blockers.append("insufficient_real_holdout_cases")
    if not evidence_reviews:
        blockers.append("independent_review_references_missing")
    if challenger_report["macro_f1"] < incumbent_report["macro_f1"]:
        blockers.append("challenger_macro_f1_below_incumbent")
    if challenger_report["confidence_brier_score"] > incumbent_report["confidence_brier_score"]:
        blockers.append("challenger_calibration_worse")
    if missed_unsubscribes:
        blockers.append("challenger_missed_unsubscribe")
    # Reviewer references are caller-supplied text, not independently authenticated
    # provenance. Passing offline metrics can only produce a human-review candidate.
    metrics_pass = not blockers
    blockers.append("independent_reviewer_authentication_not_verified")
    # Exact holdout parity prevents comparing different or cherry-picked cases.
    return {
        "schema_version": "empire.jev.gtm_challenger_eval.v1",
        "task_key": task,
        "dataset_sha256": rebuilt["sha256"],
        "dataset_case_count": n,
        "real_label_count": rebuilt["real_labeled_case_count"],
        "synthetic_case_count": rebuilt["synthetic_test_fixture_count"],
        "independent_review_reference_count": len(evidence_reviews),
        "reviews_cryptographically_authenticated": False,
        "incumbent": {
            "provider": incumbent_report["provider_key"],
            "model": incumbent_report["model_key"],
            "macro_f1": incumbent_report["macro_f1"],
            "confidence_brier_score": incumbent_report["confidence_brier_score"],
            "p95_latency_ms": incumbent_report["p95_latency_ms"],
        },
        "challenger": {
            "provider": challenger_report["provider_key"],
            "model": challenger_report["model_key"],
            "macro_f1": challenger_report["macro_f1"],
            "confidence_brier_score": challenger_report["confidence_brier_score"],
            "p95_latency_ms": challenger_report["p95_latency_ms"],
            "false_positive_interest_count": false_positive_interest,
            "missed_unsubscribe_count": missed_unsubscribes,
        },
        "offline_metrics_pass": metrics_pass,
        "promotion_evidence_review_ready": False,
        "blockers": blockers,
        "model_selected": False,
        "live_routing_activated": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }
