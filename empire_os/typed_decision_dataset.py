"""Frozen typed-decision evaluation datasets.

Provides deterministic dataset validation, content hashing and manifests.
Fixtures may be synthetic/test-only; they can never be treated as production or
commercial evidence.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Any, Iterable, Mapping


TASK_SCHEMAS = {
    "reply_classification": {
        "labels": ("unsubscribe", "negative", "later", "objection", "positive", "question", "other"),
        "input_fields": ("body_text",),
    },
    "keyword_intent": {
        "labels": (
            "category", "problem", "product", "commercial", "comparison",
            "territory", "event_trigger", "agency_white_label",
            "enterprise_api", "education",
        ),
        "input_fields": ("query",),
    },
    "source_quality": {
        "labels": ("accept", "review", "quarantine", "reject"),
        "input_fields": ("source_ref", "evidence_summary"),
    },
    "buyer_corridor_fit": {
        "labels": ("strong_fit", "possible_fit", "weak_fit", "insufficient_evidence"),
        "input_fields": ("buyer_ref", "corridor_ref"),
    },
    "agent_routing": {
        "labels": ("deterministic", "quant", "search", "research", "coding", "general_reasoning", "human_review"),
        "input_fields": ("task_text",),
    },
    "guardrail_classification": {
        "labels": ("allow", "review", "block"),
        "input_fields": ("candidate_action",),
    },
}


def _text(v: Any) -> str:
    return str(v or "").strip()


@dataclass(frozen=True)
class DatasetCase:
    case_id: str
    task_key: str
    inputs: Mapping[str, Any]
    ground_truth: str
    label_source: str
    source_ref: str
    synthetic_test_fixture: bool = False

    def validate(self) -> None:
        if not _text(self.case_id):
            raise ValueError("case_id required")
        if self.task_key not in TASK_SCHEMAS:
            raise ValueError("unsupported task_key")
        schema = TASK_SCHEMAS[self.task_key]
        if self.ground_truth not in schema["labels"]:
            raise ValueError("ground_truth not allowed for task")
        if not _text(self.label_source):
            raise ValueError("label_source required")
        if not _text(self.source_ref):
            raise ValueError("source_ref required")
        missing = [
            field for field in schema["input_fields"]
            if self.inputs.get(field) in (None, "")
        ]
        if missing:
            raise ValueError("missing input fields: " + ",".join(missing))

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "case_id": self.case_id,
            "task_key": self.task_key,
            "inputs": dict(sorted(self.inputs.items())),
            "ground_truth": self.ground_truth,
            "label_source": self.label_source,
            "source_ref": self.source_ref,
            "synthetic_test_fixture": self.synthetic_test_fixture,
        }


def case_from_mapping(raw: Mapping[str, Any]) -> DatasetCase:
    return DatasetCase(
        case_id=_text(raw.get("case_id")),
        task_key=_text(raw.get("task_key")),
        inputs=dict(raw.get("inputs") or {}),
        ground_truth=_text(raw.get("ground_truth")),
        label_source=_text(raw.get("label_source")),
        source_ref=_text(raw.get("source_ref")),
        synthetic_test_fixture=bool(raw.get("synthetic_test_fixture", False)),
    )


def freeze_dataset(
    rows: Iterable[Mapping[str, Any]],
    *,
    dataset_id: str,
    version: str,
) -> dict[str, Any]:
    dataset_id = _text(dataset_id)
    version = _text(version)
    if not dataset_id:
        raise ValueError("dataset_id required")
    if not version:
        raise ValueError("version required")

    cases = [case_from_mapping(row) for row in rows]
    seen: set[str] = set()
    task_keys: set[str] = set()
    for case in cases:
        case.validate()
        if case.case_id in seen:
            raise ValueError("duplicate case_id")
        seen.add(case.case_id)
        task_keys.add(case.task_key)

    canonical_cases = sorted(
        (case.canonical_dict() for case in cases),
        key=lambda item: item["case_id"],
    )
    payload = json.dumps(
        canonical_cases,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()

    synthetic_count = sum(
        1 for case in canonical_cases if case["synthetic_test_fixture"]
    )
    real_count = len(canonical_cases) - synthetic_count

    by_task: dict[str, int] = {}
    by_label: dict[str, int] = {}
    for case in canonical_cases:
        by_task[case["task_key"]] = by_task.get(case["task_key"], 0) + 1
        key = f'{case["task_key"]}:{case["ground_truth"]}'
        by_label[key] = by_label.get(key, 0) + 1

    return {
        "schema_version": "typed_decision_dataset_manifest.v1",
        "dataset_id": dataset_id,
        "version": version,
        "sha256": digest,
        "case_count": len(canonical_cases),
        "task_keys": sorted(task_keys),
        "by_task": dict(sorted(by_task.items())),
        "by_label": dict(sorted(by_label.items())),
        "synthetic_test_fixture_count": synthetic_count,
        "real_labeled_case_count": real_count,
        "eligible_for_production_promotion_evidence": (
            len(canonical_cases) > 0 and synthetic_count == 0
        ),
        "commercial_evidence": False,
        "cases": canonical_cases,
    }


def verify_frozen_dataset(manifest: Mapping[str, Any]) -> dict[str, Any]:
    cases = manifest.get("cases") or []
    rebuilt = freeze_dataset(
        cases,
        dataset_id=_text(manifest.get("dataset_id")),
        version=_text(manifest.get("version")),
    )
    expected = _text(manifest.get("sha256"))
    return {
        "schema_version": "typed_decision_dataset_verification.v1",
        "valid": bool(expected) and rebuilt["sha256"] == expected,
        "expected_sha256": expected or None,
        "observed_sha256": rebuilt["sha256"],
        "case_count": rebuilt["case_count"],
        "synthetic_test_fixture_count": rebuilt["synthetic_test_fixture_count"],
        "real_labeled_case_count": rebuilt["real_labeled_case_count"],
        "eligible_for_production_promotion_evidence": rebuilt[
            "eligible_for_production_promotion_evidence"
        ],
        "commercial_evidence": False,
    }


def dataset_readiness(manifest: Mapping[str, Any], *, minimum_per_label: int = 20) -> dict[str, Any]:
    if minimum_per_label < 1:
        raise ValueError("minimum_per_label must be positive")
    verification = verify_frozen_dataset(manifest)
    blockers: list[str] = []
    if not verification["valid"]:
        blockers.append("dataset_hash_invalid")
    if verification["synthetic_test_fixture_count"] > 0:
        blockers.append("synthetic_test_fixtures_present")
    if verification["real_labeled_case_count"] == 0:
        blockers.append("no_real_labeled_cases")

    task_keys = manifest.get("task_keys") or []
    by_label = manifest.get("by_label") or {}
    for task in task_keys:
        labels = TASK_SCHEMAS.get(task, {}).get("labels", ())
        for label in labels:
            count = int(by_label.get(f"{task}:{label}", 0))
            if count < minimum_per_label:
                blockers.append(
                    f"insufficient_label_samples:{task}:{label}:{count}"
                )

    return {
        "schema_version": "typed_decision_dataset_readiness.v1",
        "ready_for_provider_promotion_eval": not blockers,
        "blockers": blockers,
        "minimum_per_label": minimum_per_label,
        "production_mutation": False,
        "execution_authority": "none",
    }


def reply_classifier_fixture_rows() -> list[dict[str, Any]]:
    """Explicitly synthetic regression fixtures mirroring governed reply classes."""
    samples = [
        ("r-unsub-1", "Please unsubscribe me.", "unsubscribe"),
        ("r-unsub-2", "Remove me from this list.", "unsubscribe"),
        ("r-neg-1", "No thanks, not interested.", "negative"),
        ("r-neg-2", "This is not for us.", "negative"),
        ("r-later-1", "Not right now, check back next quarter.", "later"),
        ("r-later-2", "Try again later.", "later"),
        ("r-obj-1", "This is too expensive.", "objection"),
        ("r-obj-2", "We already use another provider.", "objection"),
        ("r-pos-1", "Interested, tell me more.", "positive"),
        ("r-pos-2", "Let's talk and book a call.", "positive"),
        ("r-q-1", "How does the pricing work?", "question"),
        ("r-q-2", "Can you send more information?", "question"),
        ("r-other-1", "Thanks for the note.", "other"),
        ("r-other-2", "Received.", "other"),
    ]
    return [
        {
            "case_id": case_id,
            "task_key": "reply_classification",
            "inputs": {"body_text": text},
            "ground_truth": label,
            "label_source": "deterministic_regression_fixture",
            "source_ref": f"fixture:{case_id}",
            "synthetic_test_fixture": True,
        }
        for case_id, text, label in samples
    ]
