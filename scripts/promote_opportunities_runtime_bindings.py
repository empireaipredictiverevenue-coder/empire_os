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
    / "runtime/opportunities_control/"
      "opportunities_runtime_observer_latest.json"
)

PROOF_REL = (
    "runtime/opportunities_control/"
    "opportunities_runtime_observer_latest.json"
)

TARGETS = {
    "canonical_identity",
    "conflict_detection",
    "duplicate_detection",
    "evidence_lineage",
    "input_quality",
    "outcome_linkage",
    "output_quality",
    "quarantine",
}


def shaped(old, scalar, sequence):
    if isinstance(old, list):
        return list(sequence)

    return scalar


proof = json.loads(
    PROOF.read_text()
)

proved = validate_control_proof(proof, lane="opportunities", allowed=TARGETS)

data = json.loads(
    BINDINGS.read_text()
)

lane = next(
    x
    for x in data["lanes"]
    if x["lane"] == "opportunities"
)

templates = next(
    x
    for x in data["lanes"]
    if x["lane"]
        == "conversations_replies"
)["controls"]

controls = lane["controls"]

promoted = []

for control in sorted(proved):

    if (
        controls[control].get("status")
        == "VERIFIED_RUNTIME"
    ):
        continue

    row = copy.deepcopy(
        templates[control]
    )

    row["lane"] = "opportunities"
    row["control"] = control
    row["status"] = "VERIFIED_RUNTIME"

    if "artifact_paths" in row:
        row["artifact_paths"] = shaped(
            row["artifact_paths"],
            PROOF_REL,
            [PROOF_REL],
        )

    if "active_units" in row:
        row["active_units"] = shaped(
            row["active_units"],
            "opportunities_runtime_observer",
            [
                "opportunities_runtime_observer",
                "opportunity_radar",
            ],
        )

    if "matched_keys" in row:
        row["matched_keys"] = shaped(
            row["matched_keys"],
            control,
            [control],
        )

    if "reason" in row:
        row["reason"] = (
            "095A verified this control against "
            "real non-fixture Opportunity Radar "
            "runtime artifacts. OBSERVE only."
        )

    controls[control] = row
    promoted.append(control)


verified = sorted(
    name
    for name, row in controls.items()
    if row.get("status")
        == "VERIFIED_RUNTIME"
)

remaining = sorted(
    name
    for name, row in controls.items()
    if row.get("status")
        != "VERIFIED_RUNTIME"
)

tmp = BINDINGS.with_suffix(
    ".json.tmp095a"
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
