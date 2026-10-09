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
    / "runtime/products_offers_control/"
      "products_offers_runtime_observer_latest.json"
)

PROOF_REL = (
    "runtime/products_offers_control/"
    "products_offers_runtime_observer_latest.json"
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

if proof.get(
    "status"
) != "VERIFIED_RUNTIME":
    raise SystemExit(
        "FAIL: Products/Offers observer "
        "not VERIFIED_RUNTIME"
    )

proved = validate_control_proof(proof, lane="products_offers", allowed=TARGETS)

with binding_writer_lock(BINDINGS):
    original_bindings = BINDINGS.read_bytes()
    data = json.loads(
        original_bindings.decode("utf-8")
    )

    lane = next(
        x
        for x in data["lanes"]
        if x["lane"]
            == "products_offers"
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

        current = controls[control]

        if (
            isinstance(current, dict)
            and current.get("status")
                == "VERIFIED_RUNTIME"
        ):
            continue

        row = copy.deepcopy(
            templates[control]
        )

        row["lane"] = (
            "products_offers"
        )

        row["control"] = control

        row["status"] = (
            "VERIFIED_RUNTIME"
        )

        if "artifact_paths" in row:
            row["artifact_paths"] = shaped(
                row["artifact_paths"],
                PROOF_REL,
                [PROOF_REL],
            )

        if "active_units" in row:
            row["active_units"] = shaped(
                row["active_units"],
                "products_offers_runtime_observer",
                [
                    "products_offers_runtime_observer",
                    "empiredb.commercial_products",
                    "empiredb.commercial_product_versions",
                    "empiredb.commercial_product_catalog_events",
                ],
            )

        if "matched_keys" in row:
            row["matched_keys"] = shaped(
                row["matched_keys"],
                control,
                [
                    control,
                    "VERIFIED_RUNTIME",
                ],
            )

        if "reason" in row:
            row["reason"] = (
                "099B verified this Products/Offers "
                "control against the canonical EmpireDB "
                "commercial product/version/event catalog. "
                "OBSERVE only; no commercial mutation."
            )

        controls[control] = row
        promoted.append(control)


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
