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
    / "runtime/orders_payments_revenue_control/"
      "orders_payments_revenue_runtime_latest.json"
)

PROOF_REL = (
    "runtime/orders_payments_revenue_control/"
    "orders_payments_revenue_runtime_latest.json"
)

TARGETS = {
    "canonical_identity",
    "duplicate_detection",
    "entity_classification",
    "input_quality",
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

proved = validate_control_proof(proof, lane="orders_payments_revenue", allowed=TARGETS)

data = json.loads(
    BINDINGS.read_text()
)

lane = next(
    row
    for row in data["lanes"]
    if row["lane"]
        == "orders_payments_revenue"
)

templates = next(
    row
    for row in data["lanes"]
    if row["lane"]
        == "conversations_replies"
)["controls"]

controls = lane["controls"]

promoted = []

for control in sorted(proved):

    current = controls[control]

    if (
        isinstance(current, dict)
        and current.get(
            "status"
        ) == "VERIFIED_RUNTIME"
    ):
        continue

    row = copy.deepcopy(
        templates[control]
    )

    row["lane"] = (
        "orders_payments_revenue"
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
            "orders_payments_revenue_runtime_observer",
            [
                "orders_payments_revenue_runtime_observer",
                "empiredb.bsc_payment_requests",
                "empiredb.bsc_payment_evidence",
                "empiredb.fulfilment_orders",
                "empiredb.revenue_exchange_observations",
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
            "100B verified the control against the "
            "live canonical BSC/USDT payment, "
            "fulfilment and revenue schemas with "
            "fail-closed read-only evaluators. "
            "Current commercial population is empty; "
            "this is control proof, not payment proof."
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

tmp = BINDINGS.with_suffix(
    ".json.tmp100b"
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
