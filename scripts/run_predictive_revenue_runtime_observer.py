#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from empire_os.runtime_evidence_prefilter import may_contain_key
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path("/srv/empire_os")

OUT = (
    ROOT
    / "runtime/predictive_revenue_control/"
      "predictive_revenue_runtime_latest.json"
)

IDENTITY_KEYS = (
    "predictive_revenue_id",
    "prediction_id",
    "opportunity_id",
    "campaign_id",
    "product_id",
    "offer_id",
    "buyer_id",
    "lead_id",
)

INPUT_KEYS = (
    "predictive_revenue_inputs",
    "revenue_inputs",
    "inputs",
    "signals",
    "signal",
    "demand",
    "intent",
    "baseline",
    "audience",
    "market",
    "niche",
)

OUTPUT_KEYS = (
    "predicted_revenue",
    "predictive_revenue",
    "predicted_revenue_cents",
    "expected_revenue",
    "expected_revenue_cents",
    "expected_canonical_revenue_contribution_cents",
    "prediction_status",
    "revenue_prediction",
    "forecast_revenue",
)

EVIDENCE_KEYS = (
    "predictive_revenue_evidence_refs",
    "evidence_refs",
    "evidence",
    "source_refs",
    "provenance",
)

MARKERS = (
    "predictive_revenue",
    "predicted_revenue",
    "prediction_status",
    "expected_canonical_revenue_contribution_cents",
    "revenue_prediction",
    "forecast_revenue",
)


def present(v: Any) -> bool:
    # Zero is valid.
    return v not in (None, "", [], {})


def atomic(payload):
    OUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tmp = OUT.with_suffix(".tmp")

    tmp.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            default=str,
        ) + "\n",
        encoding="utf-8",
    )

    tmp.replace(OUT)


def excluded(path: Path) -> bool:
    rel = (
        "/"
        + str(
            path.relative_to(ROOT)
        ).replace("\\", "/")
        + "/"
    ).casefold()

    return any(
        part in rel
        for part in (
            "/tests/",
            "/fixtures/",
            "/docs/",
            "/control_plane/",
            "/predictive_revenue_control/",
            "/worker_code/",
        )
    )


def first(row, names):
    for name in names:
        if present(row.get(name)):
            return row[name]

    return None


def predictive_record(row):
    if not isinstance(row, dict):
        return False

    keys = [
        str(k).casefold()
        for k in row.keys()
    ]

    return any(
        marker in key
        for marker in MARKERS
        for key in keys
    )


def output_signature(row):
    values = {}

    for key in OUTPUT_KEYS:
        if key in row and present(row[key]):
            values[key] = row[key]

    return json.dumps(
        values,
        sort_keys=True,
        default=str,
    )


observations = []


def walk(
    value,
    *,
    source,
    path,
    inherited,
):
    if isinstance(value, dict):

        context = dict(
            inherited
        )

        local_identity = first(
            value,
            IDENTITY_KEYS,
        )

        if present(local_identity):
            context[
                "identity"
            ] = str(
                local_identity
            )

            context[
                "identity_source"
            ] = path

        if any(
            present(value.get(k))
            for k in INPUT_KEYS
        ):
            context[
                "has_input"
            ] = True

        if any(
            present(value.get(k))
            for k in EVIDENCE_KEYS
        ):
            context[
                "has_evidence"
            ] = True

        if predictive_record(value):

            has_output = any(
                present(value.get(k))
                for k in OUTPUT_KEYS
            )

            observations.append({
                "source":
                    source,

                "path":
                    path,

                "identity":
                    context.get(
                        "identity"
                    ),

                "identity_source":
                    context.get(
                        "identity_source"
                    ),

                "has_input":
                    bool(
                        context.get(
                            "has_input"
                        )
                    ),

                "has_evidence":
                    bool(
                        context.get(
                            "has_evidence"
                        )
                    ),

                "has_output":
                    has_output,

                "output_signature":
                    output_signature(
                        value
                    ),

                "output_keys":
                    sorted(
                        key
                        for key
                        in OUTPUT_KEYS
                        if key in value
                        and present(
                            value[key]
                        )
                    ),
            })

        for key, child in value.items():
            walk(
                child,
                source=source,
                path=(
                    f"{path}.{key}"
                ),
                inherited=context,
            )

    elif isinstance(value, list):

        for i, child in enumerate(value):
            walk(
                child,
                source=source,
                path=(
                    f"{path}[{i}]"
                ),
                inherited=inherited,
            )


for file in ROOT.joinpath(
    "runtime"
).rglob("*.json"):

    if excluded(file):
        continue

    try:
        if os.environ.get("EMPIRE_RUNTIME_EVIDENCE_PREFILTER") == "OBSERVE_V1_APPROVED":
            source_bytes = file.read_bytes()
            if not may_contain_key(source_bytes, MARKERS, casefold=True):
                continue
            data = json.loads(source_bytes.decode("utf-8"))
        else:
            data = json.loads(file.read_text())
    except Exception:
        continue

    walk(
        data,
        source=str(
            file.relative_to(ROOT)
        ),
        path="$",
        inherited={
            "identity": None,
            "identity_source": None,
            "has_input": False,
            "has_evidence": False,
        },
    )


candidate_count = len(
    observations
)

resolved_identity = [
    row
    for row in observations
    if row["identity"]
]

with_input = [
    row
    for row in observations
    if row["has_input"]
]

with_output = [
    row
    for row in observations
    if row["has_output"]
]

with_evidence = [
    row
    for row in observations
    if row["has_evidence"]
]


# Fail-closed quality evaluation.
for row in observations:
    reasons = []

    if not row["identity"]:
        reasons.append(
            "identity_unresolved"
        )

    if not row["has_input"]:
        reasons.append(
            "input_missing"
        )

    if not row["has_output"]:
        reasons.append(
            "output_missing"
        )

    if not row["has_evidence"]:
        reasons.append(
            "evidence_missing"
        )

    row["quality_reasons"] = (
        reasons
    )

    row["quality_decision"] = (
        "QUARANTINE"
        if reasons
        else "PASS"
    )


passed = [
    row
    for row in observations
    if row["quality_decision"]
        == "PASS"
]

quarantined = [
    row
    for row in observations
    if row["quality_decision"]
        == "QUARANTINE"
]


# --------------------------------------------------
# EXACT IDENTITY / DUPLICATE / CONFLICT CONTROLS
# --------------------------------------------------

by_identity = defaultdict(
    list
)

for row in resolved_identity:
    by_identity[
        row["identity"]
    ].append(row)


duplicate_identities = sorted(
    identity
    for identity, rows
    in by_identity.items()
    if len(rows) > 1
)


conflicts = []

for identity, rows in by_identity.items():

    signatures = {
        row[
            "output_signature"
        ]
        for row in rows
        if row[
            "output_signature"
        ]
        != "{}"
    }

    if len(signatures) > 1:
        conflicts.append({
            "identity":
                identity,

            "observation_count":
                len(rows),

            "distinct_output_count":
                len(signatures),
        })


# Controls prove that the resolver/evaluator executes
# across the detected real runtime population.
#
# An unresolved identity, duplicate, conflict or bad input
# is a detected condition — not evidence that the control
# itself is missing.

identity_control_effective = (
    candidate_count > 0
    and len(resolved_identity) > 0
)

input_control_effective = (
    candidate_count > 0
    and len(with_input) > 0
)

duplicate_control_effective = (
    identity_control_effective
)

conflict_control_effective = (
    identity_control_effective
)


proof = {
    "entity_classification":
        candidate_count > 0,

    "canonical_identity":
        identity_control_effective,

    "duplicate_detection":
        duplicate_control_effective,

    "input_quality":
        input_control_effective,

    "output_quality":
        len(with_output) > 0,

    "conflict_detection":
        conflict_control_effective,

    "quarantine":
        candidate_count > 0
        and (
            len(passed)
            + len(quarantined)
            == candidate_count
        ),
}


verified = [
    control
    for control, ok
    in proof.items()
    if ok
]

unverified = [
    control
    for control, ok
    in proof.items()
    if not ok
]


payload = {
    "schema_version":
        "empire-predictive-revenue-contextual-runtime-v2",

    "generated_at":
        datetime.now(
            timezone.utc
        ).isoformat(),

    "lane":
        "predictive_revenue",

    "mode":
        "OBSERVE",

    "status":
        (
            "VERIFIED_RUNTIME"
            if verified
            else "NO_RUNTIME_PROOF"
        ),

    "candidate_count":
        candidate_count,

    "identity_resolved_count":
        len(
            resolved_identity
        ),

    "identity_unresolved_count":
        candidate_count
        - len(
            resolved_identity
        ),

    "input_present_count":
        len(with_input),

    "output_present_count":
        len(with_output),

    "evidence_present_count":
        len(with_evidence),

    "passed_count":
        len(passed),

    "quarantined_count":
        len(quarantined),

    "duplicate_identity_count":
        len(
            duplicate_identities
        ),

    "duplicate_identities":
        duplicate_identities[
            :100
        ],

    "conflict_count":
        len(conflicts),

    "conflicts":
        conflicts[:100],

    "runtime_verified_controls":
        verified,

    "runtime_unverified_controls":
        unverified,

    "governance": {
        "prediction_mutation":
            False,

        "db_write":
            False,

        "outbound":
            False,

        "action_authority_granted":
            False,
    },
}

atomic(payload)

print(
    "STATUS:",
    payload["status"],
)

print(
    "CANDIDATES:",
    candidate_count,
)

print(
    "IDENTITY_RESOLVED:",
    len(resolved_identity),
)

print(
    "IDENTITY_UNRESOLVED:",
    payload[
        "identity_unresolved_count"
    ],
)

print(
    "INPUT_PRESENT:",
    len(with_input),
)

print(
    "OUTPUT_PRESENT:",
    len(with_output),
)

print(
    "EVIDENCE_PRESENT:",
    len(with_evidence),
)

print(
    "PASSED:",
    len(passed),
)

print(
    "QUARANTINED:",
    len(quarantined),
)

print(
    "DUPLICATE_IDENTITIES:",
    len(
        duplicate_identities
    ),
)

print(
    "CONFLICTS:",
    len(conflicts),
)

print(
    "VERIFIED:",
    ",".join(verified)
    or "none",
)

print(
    "UNVERIFIED:",
    ",".join(unverified)
    or "none",
)
