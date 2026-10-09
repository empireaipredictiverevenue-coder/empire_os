#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path

from empire_os.runtime_promotion_guard import validate_control_proof

ROOT = Path("/srv/empire_os")

BINDINGS = (
    ROOT
    / "runtime/control_plane/"
      "runtime_control_bindings_latest.json"
)

PROOF = (
    ROOT
    / "runtime/predictive_revenue_control/"
      "predictive_revenue_runtime_latest.json"
)

PROOF_REL = (
    "runtime/predictive_revenue_control/"
    "predictive_revenue_runtime_latest.json"
)

TARGETS = {
    "canonical_identity",
    "conflict_detection",
    "duplicate_detection",
    "entity_classification",
    "input_quality",
    "output_quality",
    "quarantine",
}


def shaped(
    old,
    scalar,
    sequence,
):
    if isinstance(old, list):
        return list(sequence)

    return scalar


proof = json.loads(
    PROOF.read_text()
)

if (
    proof.get("status")
    != "VERIFIED_RUNTIME"
):
    raise SystemExit(
        "FAIL: Predictive Revenue observer "
        "not VERIFIED_RUNTIME"
    )

proved = validate_control_proof(proof, lane="predictive_revenue", allowed=TARGETS)

data = json.loads(
    BINDINGS.read_text()
)

lane = next(
    x
    for x in data["lanes"]
    if x["lane"]
        == "predictive_revenue"
)

templates = next(
    x
    for x in data["lanes"]
    if x["lane"]
        == "conversations_replies"
)["controls"]

controls = lane[
    "controls"
]

promoted = []

for control in sorted(
    proved
):

    if (
        controls[control].get(
            "status"
        )
        == "VERIFIED_RUNTIME"
    ):
        continue

    row = copy.deepcopy(
        templates[control]
    )

    row["lane"] = (
        "predictive_revenue"
    )

    row["control"] = control

    row["status"] = (
        "VERIFIED_RUNTIME"
    )

    if "artifact_paths" in row:
        row[
            "artifact_paths"
        ] = shaped(
            row[
                "artifact_paths"
            ],
            PROOF_REL,
            [PROOF_REL],
        )

    if "active_units" in row:
        row[
            "active_units"
        ] = shaped(
            row["active_units"],
            "predictive_revenue_runtime_observer",
            [
                "predictive_revenue_runtime_observer",
            ],
        )

    if "matched_keys" in row:
        row[
            "matched_keys"
        ] = shaped(
            row["matched_keys"],
            control,
            [
                control,
                "VERIFIED_RUNTIME",
            ],
        )

    if "reason" in row:
        row["reason"] = (
            "096B verified this Predictive Revenue "
            "control against real non-fixture "
            "runtime evidence using a fail-closed "
            "OBSERVE evaluator."
        )

    controls[
        control
    ] = row

    promoted.append(
        control
    )


verified = sorted(
    name
    for name, row
    in controls.items()
    if row.get("status")
        == "VERIFIED_RUNTIME"
)

remaining = sorted(
    name
    for name, row
    in controls.items()
    if row.get("status")
        != "VERIFIED_RUNTIME"
)

tmp = BINDINGS.with_suffix(
    ".json.tmp096b"
)

tmp.write_text(
    json.dumps(
        data,
        indent=2,
        sort_keys=True,
    ) + "\n"
)

tmp.replace(BINDINGS)

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
