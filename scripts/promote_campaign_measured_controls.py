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
    / "runtime/campaigns_control/"
      "campaign_measured_outcome_latest.json"
)

PROOF_REL = (
    "runtime/campaigns_control/"
    "campaign_measured_outcome_latest.json"
)


def shaped(old, scalar, sequence):
    if isinstance(old, list):
        return list(sequence)

    return scalar


proof = json.loads(
    PROOF.read_text()
)

proved = set(
    proof.get(
        "runtime_verified_controls",
        [],
    )
)

if "output_quality" not in proved:
    raise SystemExit(
        "FAIL: output_quality proof missing"
    )

with binding_writer_lock(BINDINGS):
    original_bindings = BINDINGS.read_bytes()
    data = json.loads(
        original_bindings.decode("utf-8")
    )

    campaign = next(
        x
        for x in data["lanes"]
        if x["lane"] == "campaigns"
    )

    conversation = next(
        x
        for x in data["lanes"]
        if x["lane"]
            == "conversations_replies"
    )

    controls = campaign["controls"]
    templates = conversation["controls"]

    targets = [
        "output_quality",
    ]

    if "outcome_linkage" in proved and proof.get("outcome_linkage_proved") is True and int(proof.get("exact_outcome_match_count", 0)) > 0:
        targets.append(
            "outcome_linkage"
        )
    else:
        # Revoke only the old campaign outcome claim sourced from this
        # measured resolver. Never preserve a stale verification when its
        # underlying measurement has been invalidated.
        prior = controls.get("outcome_linkage")
        if isinstance(prior, dict) and prior.get("status") == "VERIFIED_RUNTIME" and PROOF_REL in (prior.get("artifact_paths") or []):
            repaired = copy.deepcopy(prior)
            repaired["status"] = "UNVERIFIED"
            repaired["confidence"] = 0.0
            repaired["reason"] = "Measured campaign outcome evidence absent; previous proof revoked. OBSERVE only."
            repaired["artifact_paths"] = [PROOF_REL]
            controls["outcome_linkage"] = repaired

    for control in targets:
        template = copy.deepcopy(
            templates[control]
        )

        template["lane"] = "campaigns"
        template["control"] = control
        template["status"] = "VERIFIED_RUNTIME"

        if "artifact_paths" in template:
            template["artifact_paths"] = shaped(
                template["artifact_paths"],
                PROOF_REL,
                [PROOF_REL],
            )

        if "active_units" in template:
            template["active_units"] = shaped(
                template["active_units"],
                "campaign_measured_outcome_resolver",
                ["campaign_measured_outcome_resolver"],
            )

        if "matched_keys" in template:
            keys = (
                [
                    "asset_status",
                    "deployment_status",
                    "endpoint_status",
                    "cta_offer_path",
                ]
                if control == "output_quality"
                else [
                    "campaign_id",
                    "exact_outcome_matches",
                ]
            )

            template["matched_keys"] = shaped(
                template["matched_keys"],
                ",".join(keys),
                keys,
            )

        if "reason" in template:
            template["reason"] = (
                "Runtime-verified Campaign proof. "
                "output_quality derives from deployed "
                "output state; outcome_linkage, when "
                "present, requires exact deployed "
                "campaign identity plus measured outcome "
                "in a non-fixture runtime artifact."
            )

        controls[control] = template


    verified = sorted(
        name
        for name, row in controls.items()
        if isinstance(row, dict)
        and row.get("status")
            == "VERIFIED_RUNTIME"
    )

    atomic_binding_write(
        BINDINGS,
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        expected_bytes=original_bindings,
    )


print(
    "PROMOTED:",
    ",".join(targets),
)

print(
    "CANONICAL_VERIFIED_COUNT:",
    len(verified),
)
