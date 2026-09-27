"""Deterministic baselines for typed-decision evaluation."""
from __future__ import annotations

from typing import Any, Mapping

from empire_os.reply_classifier import classify_reply_text
from empire_os.typed_decision_dataset import case_from_mapping


def evaluate_reply_classifier_case(raw: Mapping[str, Any]) -> dict[str, Any]:
    case=case_from_mapping(raw)
    case.validate()
    if case.task_key!="reply_classification":
        raise ValueError("reply baseline only supports reply_classification")
    result=classify_reply_text(case.inputs.get("body_text",""),case.inputs.get("subject",""))
    return {
        "case_id":case.case_id,
        "task_key":case.task_key,
        "provider_key":"deterministic_rules",
        "model_key":"reply_classifier_v1",
        "ground_truth":case.ground_truth,
        "predicted":result["classification"],
        "confidence":float(result["confidence"]),
        "latency_ms":0.0,
        "input_tokens":None,
        "cost_cents":0.0,
        "source_ref":case.source_ref,
        "synthetic_test_fixture":case.synthetic_test_fixture,
    }


def evaluate_reply_classifier_dataset(manifest: Mapping[str, Any])->list[dict[str,Any]]:
    rows=[]
    for case in manifest.get("cases") or []:
        rows.append(evaluate_reply_classifier_case(case))
    return rows
