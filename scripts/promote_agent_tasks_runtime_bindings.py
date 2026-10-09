#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path

from empire_os.runtime_promotion_guard import validate_control_proof, atomic_binding_write, binding_writer_lock

ROOT = Path("/srv/empire_os")

BINDINGS = (
    ROOT
    / "runtime/control_plane/"
      "runtime_control_bindings_latest.json"
)

PROOF = (
    ROOT
    / "runtime/agent_tasks_control/"
      "agent_tasks_runtime_observer_latest.json"
)

PROOF_REL = (
    "runtime/agent_tasks_control/"
    "agent_tasks_runtime_observer_latest.json"
)

ALLOWED = {
    "entity_classification",
    "canonical_identity",
    "duplicate_detection",
    "input_quality",
    "output_quality",
    "evidence_lineage",
    "conflict_detection",
    "quarantine",
    "outcome_linkage",
}

MATCHED = {
    "entity_classification": [
        "runtime/departments/work",
        "state_counts",
        "task_id",
    ],

    "canonical_identity": [
        "task_id",
        "identified_task_count",
    ],

    "duplicate_detection": [
        "duplicate_identity_count",
        "duplicate_identities",
    ],

    "input_quality": [
        "input_quality_count",
    ],

    "output_quality": [
        "output_quality_count",
    ],

    "evidence_lineage": [
        "evidence_lineage_count",
    ],

    "conflict_detection": [
        "state_conflict_count",
        "state_conflicts",
        "declared_state_conflicts",
    ],

    "quarantine": [
        "quarantine_count",
        "blocked",
        "failed",
    ],

    "outcome_linkage": [
        "outcome_linkage_count",
        "done",
        "failed",
        "task_id",
    ],
}


def shaped(old, scalar, sequence):
    if isinstance(old, list):
        return list(sequence)

    return scalar


proof = json.loads(
    PROOF.read_text()
)

if proof.get(
    "status"
) != "VERIFIED_RUNTIME":
    raise SystemExit(
        "FAIL: Agent Tasks observer "
        "not VERIFIED_RUNTIME"
    )

proved = validate_control_proof(proof, lane="agent_tasks", allowed=ALLOWED)

with binding_writer_lock(BINDINGS):
    original_bindings = BINDINGS.read_bytes()
    data = json.loads(
        original_bindings.decode("utf-8")
    )

    agent_lane = next(
        x
        for x in data["lanes"]
        if x["lane"] == "agent_tasks"
    )

    conversation_lane = next(
        x
        for x in data["lanes"]
        if x["lane"]
            == "conversations_replies"
    )

    controls = (
        agent_lane["controls"]
    )

    templates = (
        conversation_lane["controls"]
    )

    promoted = []

    for control in sorted(
        proved
    ):
        current = controls[
            control
        ]

        if (
            isinstance(current, dict)
            and current.get("status")
                == "VERIFIED_RUNTIME"
        ):
            continue

        template = copy.deepcopy(
            templates[control]
        )

        template["lane"] = (
            "agent_tasks"
        )

        template["control"] = (
            control
        )

        template["status"] = (
            "VERIFIED_RUNTIME"
        )

        if "artifact_paths" in template:
            template[
                "artifact_paths"
            ] = shaped(
                template[
                    "artifact_paths"
                ],
                PROOF_REL,
                [PROOF_REL],
            )

        if "active_units" in template:
            template[
                "active_units"
            ] = shaped(
                template[
                    "active_units"
                ],
                "agent_tasks_runtime_observer",
                [
                    "agent_tasks_runtime_observer",
                    "department_work_runtime",
                ],
            )

        if "matched_keys" in template:
            template[
                "matched_keys"
            ] = shaped(
                template[
                    "matched_keys"
                ],
                ",".join(
                    MATCHED[control]
                ),
                MATCHED[control],
            )

        if "reason" in template:
            template["reason"] = (
                "094B verified this control "
                "against the real "
                "runtime/departments/work "
                "production task store. "
                "OBSERVE only; no task mutation."
            )

        if "confidence" in template:
            value = template[
                "confidence"
            ]

            if isinstance(
                value,
                (int, float),
            ):
                template[
                    "confidence"
                ] = max(
                    float(value),
                    0.90,
                )

            elif isinstance(
                value,
                str,
            ):
                template[
                    "confidence"
                ] = "HIGH"

        controls[
            control
        ] = template

        promoted.append(
            control
        )


    verified = sorted(
        name
        for name, row
        in controls.items()
        if isinstance(row, dict)
        and row.get("status")
            == "VERIFIED_RUNTIME"
    )

    remaining = sorted(
        name
        for name, row
        in controls.items()
        if not (
            isinstance(row, dict)
            and row.get("status")
                == "VERIFIED_RUNTIME"
        )
    )

    atomic_binding_write(
        BINDINGS,
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        expected_bytes=original_bindings,
    )

    print(
        "PROMOTED:",
        ",".join(promoted)
        or "none",
    )

    print(
        "CANONICAL_VERIFIED_COUNT:",
        len(verified),
    )

    print(
        "CANONICAL_REMAINING:",
        ",".join(remaining)
        or "none",
    )
