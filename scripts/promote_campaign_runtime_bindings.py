#!/usr/bin/env python3

from __future__ import annotations

import copy
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from empire_os.runtime_promotion_guard import validate_control_proof, PromotionProofError

ROOT = Path("/srv/empire_os")

BINDINGS = (
    ROOT
    / "runtime/control_plane/"
      "runtime_control_bindings_latest.json"
)

OBSERVER = (
    ROOT
    / "runtime/campaigns_control/"
      "campaign_runtime_observer_latest.json"
)

OBSERVER_REL = (
    "runtime/campaigns_control/"
    "campaign_runtime_observer_latest.json"
)

DEPLOYED_REL = (
    "runtime/astra/"
    "owned_campaign_deployed_release.json"
)

# Promote only controls proven by the Campaign observer.
# Include entity_classification: the observer proves it, and
# the canonical closure assertion already requires it.
TARGETS = {
    "entity_classification",
    "canonical_identity",
    "conflict_detection",
    "duplicate_detection",
    "evidence_lineage",
    "input_quality",
    "quarantine",
}

MATCHED = {
    "entity_classification": [
        "campaign_ids",
        "campaigns",
    ],

    "canonical_identity": [
        "campaign_id",
        "campaign_key",
        "canonical_campaigns_sha256",
    ],

    "conflict_detection": [
        "duplicate_campaign_ids",
        "canonical_campaigns_sha256",
    ],

    "duplicate_detection": [
        "duplicate_campaign_ids",
        "identified_campaign_count",
    ],

    "evidence_lineage": [
        "evidence_refs",
        "deployment_evidence_refs",
        "canonical_campaigns_sha256",
        "source_sha256",
    ],

    "input_quality": [
        "audience",
        "defined_audience",
        "channel",
        "channels",
        "campaign_objective",
        "conversion_objective",
        "binding_offer",
        "cta_offer_path",
    ],

    "quarantine": [
        "campaigns_blocked",
        "blocked_campaigns",
        "quarantined_campaigns",
        "quarantine",
    ],
}


def collect_rows(
    node: Any,
    *,
    parent=None,
    key=None,
    path="$",
    found=None,
):
    if found is None:
        found = []

    if isinstance(node, dict):

        if {
            "lane",
            "control",
            "status",
        }.issubset(node):

            found.append({
                "row": node,
                "parent": parent,
                "key": key,
                "path": path,
            })

        for k, value in node.items():
            collect_rows(
                value,
                parent=node,
                key=k,
                path=f"{path}.{k}",
                found=found,
            )

    elif isinstance(node, list):

        for i, value in enumerate(node):
            collect_rows(
                value,
                parent=node,
                key=i,
                path=f"{path}[{i}]",
                found=found,
            )

    return found


def shaped(
    original,
    *,
    scalar,
    sequence,
):
    if isinstance(original, list):
        return list(sequence)

    if isinstance(original, tuple):
        return list(sequence)

    return scalar


bindings = json.loads(
    BINDINGS.read_text()
)

observer = json.loads(
    OBSERVER.read_text()
)

# Campaign observer also reports action_authority as a control; it is
# not execution permission. Validate it but never promote it here.
try:
    verified = validate_control_proof(
        observer, lane="campaigns", allowed=TARGETS | {"action_authority"}
    )
except PromotionProofError as exc:
    raise SystemExit(f"FAIL: campaign proof rejected: {exc}") from exc

missing_proof = TARGETS - verified
if missing_proof:
    raise SystemExit("FAIL: observer does not prove: " + ",".join(sorted(missing_proof)))

proved = verified & TARGETS

records = collect_rows(
    bindings
)

campaign_records = [
    x
    for x in records
    if x["row"].get("lane") == "campaigns"
    and x["row"].get("control")
]

verified_campaign_records = [
    x
    for x in campaign_records
    if x["row"].get("status")
        == "VERIFIED_RUNTIME"
]

conversation_records = [
    x
    for x in records
    if x["row"].get("lane")
        == "conversations_replies"
    and x["row"].get("status")
        == "VERIFIED_RUNTIME"
    and x["row"].get("control")
]

print(
    "EXISTING_CAMPAIGN_ROWS:",
    len(verified_campaign_records),
)

print(
    "CONVERSATION_TEMPLATE_ROWS:",
    len(conversation_records),
)

if not verified_campaign_records:
    raise SystemExit(
        "FAIL: no existing canonical campaign bindings"
    )

if not conversation_records:
    raise SystemExit(
        "FAIL: no accepted conversation templates"
    )


# Find the actual container holding the existing
# canonical campaign rows.
groups = defaultdict(list)

for rec in verified_campaign_records:
    groups[id(rec["parent"])].append(
        rec
    )

selected_group = max(
    groups.values(),
    key=len,
)

parent = selected_group[0][
    "parent"
]

if parent is None:
    raise SystemExit(
        "FAIL: campaign binding parent unresolved"
    )

# All canonical Campaign bindings should resolve to
# the same parent container.
if len(selected_group) != len(
    verified_campaign_records
):
    raise SystemExit(
        "FAIL: campaign bindings span multiple "
        "containers; refusing ambiguous write"
    )

parent_path = (
    selected_group[0]["path"]
    .rsplit(".", 1)[0]
)

print(
    "CANONICAL_PARENT_TYPE:",
    type(parent).__name__,
)

print(
    "CANONICAL_PARENT_PATH:",
    parent_path,
)


conversation_templates = {
    rec["row"]["control"]: rec
    for rec in conversation_records
}

existing_campaign = {
    rec["row"]["control"]: rec
    for rec in verified_campaign_records
}

for control in TARGETS:
    if control not in conversation_templates:
        raise SystemExit(
            "FAIL: missing accepted template: "
            + control
        )


def insert_dict_row(
    container,
    row,
    control,
):
    # Best case: existing campaign bindings are
    # keyed directly by control name.
    if any(
        rec["key"]
        == rec["row"].get("control")
        for rec in selected_group
    ):
        if control in container:
            existing = container[control]

            if not isinstance(existing, dict):
                raise RuntimeError(
                    f"existing slot is not a dict: {control}"
                )

            existing_control = existing.get(
                "control"
            )

            if existing_control not in (
                None,
                control,
            ):
                raise RuntimeError(
                    f"existing slot control mismatch: "
                    f"{control} != {existing_control}"
                )

            existing_lane = existing.get(
                "lane"
            )

            if existing_lane not in (
                None,
                "campaigns",
            ):
                raise RuntimeError(
                    f"existing slot lane mismatch: "
                    f"{control} -> {existing_lane}"
                )

            # Preserve already-verified canonical truth.
            if (
                existing.get("status")
                == "VERIFIED_RUNTIME"
            ):
                return control

            # This is the normal case: the canonical
            # Campaign control slot already exists but
            # is not yet runtime-verified.
            container[control] = row
            return control

        container[control] = row
        return control

    # Otherwise derive the canonical key format from
    # an existing Campaign binding.
    sample = selected_group[0]

    sample_key = str(
        sample["key"]
    )

    sample_control = str(
        sample["row"]["control"]
    )

    if sample_control in sample_key:
        new_key = sample_key.replace(
            sample_control,
            control,
            1,
        )

        if new_key in container:
            raise RuntimeError(
                f"key collision: {new_key}"
            )

        container[new_key] = row
        return new_key

    # Or derive from the same-control conversation
    # template key when lanes form part of the key.
    conv = conversation_templates[
        control
    ]

    conv_key = str(
        conv["key"]
    )

    if (
        conv["parent"] is parent
        and "conversations_replies"
        in conv_key
    ):
        new_key = conv_key.replace(
            "conversations_replies",
            "campaigns",
            1,
        )

        if new_key in container:
            raise RuntimeError(
                f"key collision: {new_key}"
            )

        container[new_key] = row
        return new_key

    raise RuntimeError(
        "unable to derive canonical dict key "
        f"for {control}"
    )


added = []

for control in sorted(TARGETS):

    if (
        control in existing_campaign
        and existing_campaign[
            control
        ]["row"].get("status")
            == "VERIFIED_RUNTIME"
    ):
        continue

    template = copy.deepcopy(
        conversation_templates[
            control
        ]["row"]
    )

    template["lane"] = (
        "campaigns"
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
            scalar=OBSERVER_REL,
            sequence=[
                OBSERVER_REL,
                DEPLOYED_REL,
            ],
        )

    if "active_units" in template:
        template[
            "active_units"
        ] = shaped(
            template[
                "active_units"
            ],
            scalar=(
                "campaign_runtime_observer"
            ),
            sequence=[
                "campaign_runtime_observer",
                "owned_campaign_deployed_release",
            ],
        )

    if "matched_keys" in template:
        template[
            "matched_keys"
        ] = shaped(
            template[
                "matched_keys"
            ],
            scalar=",".join(
                MATCHED[control]
            ),
            sequence=MATCHED[
                control
            ],
        )

    if "reason" in template:
        template["reason"] = (
            "093B real deployed Campaign runtime "
            "artifact proved this control; "
            "093D-R1 promotes that existing proof "
            "into the canonical binding schema. "
            "OBSERVE only; no send or mutation."
        )

    if "confidence" in template:

        old = template[
            "confidence"
        ]

        if isinstance(
            old,
            (int, float),
        ):
            template[
                "confidence"
            ] = max(
                float(old),
                0.90,
            )

        elif isinstance(
            old,
            str,
        ):
            template[
                "confidence"
            ] = "HIGH"

    if isinstance(
        parent,
        list,
    ):
        parent.append(
            template
        )

    elif isinstance(
        parent,
        dict,
    ):
        insert_dict_row(
            parent,
            template,
            control,
        )

    else:
        raise SystemExit(
            "FAIL: unsupported canonical parent type"
        )

    added.append(
        control
    )


# Re-scan the in-memory result.
after = collect_rows(
    bindings
)

campaign_verified = sorted({
    rec["row"]["control"]
    for rec in after
    if rec["row"].get("lane")
        == "campaigns"
    and rec["row"].get("status")
        == "VERIFIED_RUNTIME"
    and rec["row"].get("control")
})

# Require the observer-proven controls plus the previously
# verified action-authority and freshness bindings.
# Output-quality/outcome-linkage have separate evidence gates.
expected = {
    "action_authority",
    "freshness",
} | TARGETS

missing = (
    expected
    - set(campaign_verified)
)

if missing:
    raise SystemExit(
        "FAIL: promotion incomplete: "
        + ",".join(
            sorted(missing)
        )
    )


tmp = BINDINGS.with_suffix(
    ".json.tmp093d_r1"
)

tmp.write_text(
    json.dumps(
        bindings,
        indent=2,
        sort_keys=True,
    ) + "\n",
    encoding="utf-8",
)

tmp.replace(
    BINDINGS
)

print(
    "ADDED:",
    ",".join(added)
    or "none",
)

print(
    "CANONICAL_VERIFIED_COUNT:",
    len(campaign_verified),
)

print(
    "CANONICAL_VERIFIED:",
    ",".join(
        campaign_verified
    ),
)

print(
    "CANONICAL_BINDING_WRITE: PASS"
)
