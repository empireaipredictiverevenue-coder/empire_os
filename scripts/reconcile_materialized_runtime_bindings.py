#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from empire_os.runtime_promotion_guard import atomic_binding_write, binding_writer_lock

ROOT = Path("/srv/empire_os")

FABRIC = (
    ROOT
    / "runtime/control_plane/"
      "detection_fabric_latest.json"
)

BINDINGS = (
    ROOT
    / "runtime/control_plane/"
      "runtime_control_bindings_latest.json"
)

fabric = json.loads(
    FABRIC.read_text()
)

with binding_writer_lock(BINDINGS):
    original_bindings = BINDINGS.read_bytes()
    bindings = json.loads(
        original_bindings.decode("utf-8")
    )

    fabric_lanes = {
        row["lane"]: row
        for row in fabric["lanes"]
    }

    binding_lanes = {
        row["lane"]: row
        for row in bindings["lanes"]
    }

    template_lane = binding_lanes[
        "conversations_replies"
    ]

    templates = template_lane[
        "controls"
    ]

    ALL_CONTROLS = set(
        templates.keys()
    )

    assert len(ALL_CONTROLS) == 11, (
        "Expected 11 canonical controls"
    )

    # Explicit founder gate. This reconciler is NEVER
    # allowed to infer or activate this authority.
    FOUNDER_GATE = (
        "consent_suppression",
        "action_authority",
    )


    def independently_verified(lane_name, control, row):
        """Verify extra canonical evidence without manufacturing a Fabric verdict."""
        for relative in row.get("artifact_paths") or []:
            if not isinstance(relative, str) or not relative.startswith("runtime/"):
                continue
            candidate = (ROOT / relative).resolve()
            if not candidate.is_relative_to(ROOT.resolve()) or not candidate.is_file():
                continue
            try:
                proof = json.loads(candidate.read_text())
            except (OSError, ValueError):
                continue
            if not isinstance(proof, dict):
                continue
            if proof.get("lane") != lane_name or proof.get("mode") != "OBSERVE":
                continue
            if control not in (proof.get("runtime_verified_controls") or []):
                continue
            if proof.get("status") != "VERIFIED_RUNTIME":
                # Some explicit control-proof ledgers omit aggregate status;
                # in that case require the corresponding positive control assertion.
                if proof.get("status") is not None or proof.get(control + "_proved") is not True:
                    continue
            if any(proof.get(flag) is True for flag in (
                "action_authority_granted", "outbound", "db_write", "campaign_state_mutated"
            )):
                continue
            stamp = proof.get("generated_at")
            if not isinstance(stamp, str):
                continue
            try:
                observed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - observed).total_seconds()
            except (ValueError, TypeError):
                continue
            if observed.tzinfo is None or age < -300 or age > 7 * 86400:
                continue
            return True
        return False


    def shaped(
        existing,
        scalar,
        sequence,
    ):
        if isinstance(existing, list):
            return list(sequence)

        return scalar


    promoted = []

    for lane_name, flane in sorted(
        fabric_lanes.items()
    ):

        if lane_name not in binding_lanes:
            raise SystemExit(
                f"FAIL: binding lane missing: {lane_name}"
            )

        count = int(
            flane.get(
                "runtime_verified_control_count",
                0,
            )
        )

        remaining = set(
            flane.get(
                "runtime_unverified_controls",
                [],
            )
        )

        materialized_verified = (
            ALL_CONTROLS
            - remaining
        )

        if (
            len(materialized_verified)
            != count
        ):
            raise SystemExit(
                "FAIL: materialized count/remaining "
                f"disagree for {lane_name}: "
                f"{count} vs "
                f"{len(materialized_verified)}"
            )

        controls = binding_lanes[
            lane_name
        ]["controls"]

        for control in sorted(
            materialized_verified
        ):

            if (
                lane_name,
                control,
            ) == FOUNDER_GATE:
                raise SystemExit(
                    "FAIL: founder-gated action_authority "
                    "unexpectedly materialized as verified"
                )

            current = controls[
                control
            ]

            if (
                isinstance(current, dict)
                and current.get("status")
                    == "VERIFIED_RUNTIME"
            ):
                continue

            row = copy.deepcopy(
                templates[
                    control
                ]
            )

            row["lane"] = (
                lane_name
            )

            row["control"] = (
                control
            )

            row["status"] = (
                "VERIFIED_RUNTIME"
            )

            proof_rel = (
                "runtime/control_plane/"
                "detection_fabric_latest.json"
            )

            if "artifact_paths" in row:
                row[
                    "artifact_paths"
                ] = shaped(
                    row["artifact_paths"],
                    proof_rel,
                    [proof_rel],
                )

            if "active_units" in row:
                row[
                    "active_units"
                ] = shaped(
                    row["active_units"],
                    "detection_fabric_runtime_adjudicator",
                    [
                        "detection_fabric_runtime_adjudicator",
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
                    "101A-R1 reconciled canonical binding "
                    "from the current materialized Detection "
                    "Fabric VERIFIED_RUNTIME verdict. "
                    "No execution authority is granted."
                )

            controls[
                control
            ] = row

            promoted.append(
                f"{lane_name}.{control}"
            )


    # Final founder-gate assertion.
    consent = binding_lanes[
        "consent_suppression"
    ]["controls"]

    assert (
        consent[
            "action_authority"
        ].get("status")
        != "VERIFIED_RUNTIME"
    ), (
        "Founder-gated consent authority was activated"
    )


    # Canonical must now match materialized truth lane by lane.
    for lane_name, flane in sorted(
        fabric_lanes.items()
    ):

        controls = binding_lanes[
            lane_name
        ]["controls"]

        canonical_verified = {
            control
            for control, row
            in controls.items()
            if (
                isinstance(row, dict)
                and row.get("status")
                    == "VERIFIED_RUNTIME"
            )
        }

        materialized_remaining = set(
            flane.get(
                "runtime_unverified_controls",
                [],
            )
        )

        materialized_verified = (
            ALL_CONTROLS
            - materialized_remaining
        )

        # The Detection Fabric snapshot is a lower bound. Other observers
        # may hold independently verified controls for the same lane.
        missing_from_canonical = materialized_verified - canonical_verified
        independently_claimed = canonical_verified - materialized_verified
        unproven_claims = sorted(
            control for control in independently_claimed
            if not independently_verified(lane_name, control, controls[control])
        )
        if missing_from_canonical or unproven_claims:
            raise SystemExit(
                "FAIL: reconciliation evidence incomplete for "
                f"{lane_name}; materialized_missing="
                f"{sorted(missing_from_canonical)} "
                f"unproven_canonical="
                f"{unproven_claims}"
            )


    bindings[
        "materialized_runtime_reconciled_at"
    ] = datetime.now(
        timezone.utc
    ).isoformat()

    atomic_binding_write(
        BINDINGS,
        json.dumps(bindings, indent=2, sort_keys=True) + "\n",
        expected_bytes=original_bindings,
    )


print(
    "PROMOTED_COUNT:",
    len(promoted),
)

for item in promoted:
    print(
        "PROMOTED:",
        item,
    )

print(
    "CANONICAL_RECONCILIATION: PASS"
)
