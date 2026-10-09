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
    / "runtime/leads_control/"
      "leads_runtime_observer_latest.json"
)

PROOF_REL = (
    "runtime/leads_control/"
    "leads_runtime_observer_latest.json"
)

TARGETS = {
    "canonical_identity",
    "duplicate_detection",
    "entity_classification",
    "input_quality",
    "outcome_linkage",
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
        "FAIL: Leads observer not VERIFIED_RUNTIME"
    )

proved = validate_control_proof(proof, lane="leads", allowed=TARGETS)

data = json.loads(
    BINDINGS.read_text()
)

lane = next(
    x
    for x in data["lanes"]
    if x["lane"] == "leads"
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
    current = controls[
        control
    ]

    if (
        isinstance(current, dict)
        and current.get(
            "status"
        )
        == "VERIFIED_RUNTIME"
    ):
        continue

    row = copy.deepcopy(
        templates[
            control
        ]
    )

    row["lane"] = "leads"
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
            "leads_runtime_observer",
            [
                "leads_runtime_observer",
                "empiredb.enriched_leads",
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
            "097B verified this Leads control "
            "against canonical EmpireDB lead/"
            "prospect runtime data. Only aggregate "
            "evidence is persisted; no PII values."
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
    ".json.tmp097b"
)

tmp.write_text(
    json.dumps(
        data,
        indent=2,
        sort_keys=True,
    ) + "\n",
    encoding="utf-8",
)

tmp.replace(
    BINDINGS
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
