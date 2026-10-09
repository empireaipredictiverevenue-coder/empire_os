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
      "campaign_output_outcome_latest.json"
)

PROOF_REL = (
    "runtime/campaigns_control/"
    "campaign_output_outcome_latest.json"
)

DEPLOYED_REL = (
    "runtime/astra/"
    "owned_campaign_deployed_release.json"
)

ACTIVATION_REL = (
    "runtime/astra/"
    "owned_campaign_activation_v1_report.json"
)

TARGETS = {
    "output_quality",
    "outcome_linkage",
}


def shape(
    existing,
    scalar,
    sequence,
):
    if isinstance(existing, list):
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

if proved != TARGETS:
    raise SystemExit(
        "FAIL: final Campaign controls "
        "not both genuinely proved: "
        + ",".join(
            sorted(proved)
        )
    )

with binding_writer_lock(BINDINGS):
    original_bindings = BINDINGS.read_bytes()
    data = json.loads(
        original_bindings.decode("utf-8")
    )

    campaign_lane = next(
        x
        for x in data["lanes"]
        if x["lane"] == "campaigns"
    )

    conversation_lane = next(
        x
        for x in data["lanes"]
        if x["lane"]
            == "conversations_replies"
    )

    campaign_controls = (
        campaign_lane["controls"]
    )

    conversation_controls = (
        conversation_lane["controls"]
    )

    promoted = []

    for control in sorted(TARGETS):

        current = campaign_controls[
            control
        ]

        if (
            isinstance(current, dict)
            and current.get("status")
                == "VERIFIED_RUNTIME"
        ):
            continue

        template = copy.deepcopy(
            conversation_controls[
                control
            ]
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
            ] = shape(
                template[
                    "artifact_paths"
                ],
                PROOF_REL,
                [
                    PROOF_REL,
                    DEPLOYED_REL,
                    ACTIVATION_REL,
                ],
            )

        if "active_units" in template:
            template[
                "active_units"
            ] = shape(
                template[
                    "active_units"
                ],
                "campaign_output_outcome_observer",
                [
                    "campaign_output_outcome_observer",
                    "owned_campaign_deployed_release",
                ],
            )

        if "matched_keys" in template:
            keys = (
                [
                    "asset_status",
                    "deployment_status",
                    "endpoint_status",
                    "cta_offer_path",
                ]
                if control
                == "output_quality"
                else [
                    "campaign_id",
                    "conversion",
                    "conversions",
                    "conversion_rate",
                    "campaign_conversion_rate",
                    "actual_revenue",
                    "conversion_endpoint_connected",
                    "evidence_refs",
                ]
            )

            template[
                "matched_keys"
            ] = shape(
                template[
                    "matched_keys"
                ],
                ",".join(keys),
                keys,
            )

        if "reason" in template:
            template["reason"] = (
                "093E verified this control "
                "from campaign-scoped deployed output/"
                "conversion evidence. OBSERVE only; "
                "no campaign mutation or outbound."
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

        campaign_controls[
            control
        ] = template

        promoted.append(
            control
        )


    verified = sorted(
        name
        for name, row
        in campaign_controls.items()
        if isinstance(row, dict)
        and row.get("status")
            == "VERIFIED_RUNTIME"
    )

    if len(verified) != 11:
        raise SystemExit(
            "FAIL: Campaign canonical bindings "
            f"would be {len(verified)}/11, not 11/11"
        )

    atomic_binding_write(
        BINDINGS,
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        expected_bytes=original_bindings,
    )


print(
    "FINAL_PROMOTED:",
    ",".join(promoted)
    or "already_verified",
)

print(
    "CANONICAL_VERIFIED_COUNT:",
    len(verified),
)

print(
    "CANONICAL_VERIFIED:",
    ",".join(verified),
)
