#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path
from empire_os.runtime_promotion_guard import atomic_binding_write, binding_writer_lock

ROOT = Path("/srv/empire_os")

BINDINGS = (
    ROOT
    / "runtime/control_plane/"
      "runtime_control_bindings_latest.json"
)

PROOF = (
    ROOT
    / "runtime/opportunities_control/"
      "opportunities_final_controls_latest.json"
)

PROOF_REL = (
    "runtime/opportunities_control/"
    "opportunities_final_controls_latest.json"
)

TARGETS = {
    "entity_classification",
    "quarantine",
    "outcome_linkage",
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

proved = (
    set(
        proof.get(
            "runtime_verified_controls",
            [],
        )
    )
    & TARGETS
)

with binding_writer_lock(BINDINGS):
    original_bindings = BINDINGS.read_bytes()
    data = json.loads(
        original_bindings.decode("utf-8")
    )

    lane = next(
        x
        for x in data["lanes"]
        if x["lane"]
            == "opportunities"
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
            "opportunities"
        )

        row["control"] = (
            control
        )

        row["status"] = (
            "VERIFIED_RUNTIME"
        )

        if "artifact_paths" in row:
            row[
                "artifact_paths"
            ] = shaped(
                row["artifact_paths"],
                PROOF_REL,
                [PROOF_REL],
            )

        if "active_units" in row:
            row[
                "active_units"
            ] = shaped(
                row["active_units"],
                "opportunities_final_control_resolver",
                [
                    "opportunities_final_control_resolver",
                    "opportunity_radar",
                ],
            )

        if "matched_keys" in row:
            keys = (
                ["opportunity_id", "typed_namespace"]
                if control
                == "entity_classification"
                else
                ["quarantine_control_surface"]
                if control
                == "quarantine"
                else
                [
                    "opportunity_id",
                    "exact_outcome_matches",
                ]
            )

            row[
                "matched_keys"
            ] = shaped(
                row["matched_keys"],
                ",".join(keys),
                keys,
            )

        if "reason" in row:
            row["reason"] = (
                "095B verified this Opportunity "
                "control from real non-fixture "
                "runtime evidence. OBSERVE only."
            )

        controls[control] = row

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

    atomic_binding_write(
        BINDINGS,
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        expected_bytes=original_bindings,
    )


print(
    "OPPORTUNITY_FINAL_PROMOTED:",
    ",".join(promoted)
    or "none",
)

print(
    "OPPORTUNITY_CANONICAL_COUNT:",
    len(verified),
)

print(
    "OPPORTUNITY_CANONICAL_REMAINING:",
    ",".join(remaining)
    or "none",
)
