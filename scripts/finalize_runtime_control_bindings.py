#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

from empire_os.runtime_promotion_guard import (
    atomic_binding_write, binding_writer_lock,
    validate_control_proof, PromotionProofError,
)

ROOT = Path("/srv/empire_os")

BINDINGS = (
    ROOT
    / "runtime/control_plane/"
      "runtime_control_bindings_latest.json"
)

PROOF_PATHS = {
    "campaign_runtime":
        ROOT
        / "runtime/campaigns_control/"
          "campaign_runtime_observer_latest.json",

    "campaign_outcomes":
        ROOT
        / "runtime/campaigns_control/"
          "campaign_measured_outcome_latest.json",

    "agent_tasks":
        ROOT
        / "runtime/agent_tasks_control/"
          "agent_tasks_runtime_observer_latest.json",

    "opportunities_runtime":
        ROOT
        / "runtime/opportunities_control/"
          "opportunities_runtime_observer_latest.json",

    "opportunities_final":
        ROOT
        / "runtime/opportunities_control/"
          "opportunities_final_controls_latest.json",

    "opportunities_quarantine":
        ROOT
        / "runtime/opportunities_control/"
          "opportunity_quarantine_latest.json",
}


def load(name):
    path = PROOF_PATHS[name]

    if not path.exists():
        raise SystemExit(
            f"FAIL: proof missing: {path}"
        )

    return json.loads(
        path.read_text()
    )


def evidence_fresh(name, lane):
    """Require contemporaneous OBSERVE source before trusting positive claims."""
    proof=load(name)
    try:
        if proof.get("lane") != lane or proof.get("mode") != "OBSERVE":
            raise ValueError("incorrect source authority")
        if any(proof.get(k) is True for k in
               ("outbound", "db_write", "campaign_state_mutated",
                "action_authority_granted", "payment_execution")):
            raise ValueError("consequential authority present")
        stamp=datetime.fromisoformat(
            str(proof.get("generated_at") or "").replace("Z","+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("naive source timestamp")
        age=datetime.now(timezone.utc)-stamp.astimezone(timezone.utc)
        if not timedelta(0)<=age<=timedelta(days=7):
            raise ValueError("stale or future source evidence")
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"FAIL: {name} source proof stale or untrusted") from exc
    return proof


def rel(name):
    return str(
        PROOF_PATHS[name]
        .relative_to(ROOT)
    )


def shaped(
    existing,
    *,
    scalar,
    sequence,
):
    if isinstance(existing, list):
        return list(sequence)

    return scalar


with binding_writer_lock(BINDINGS):
    original_bindings = BINDINGS.read_bytes()
    data = json.loads(
        original_bindings.decode("utf-8")
    )

    lanes = {
        row["lane"]: row
        for row in data["lanes"]
    }

    # Cross-lane evidence cannot be borrowed: Conversations & Replies
    # may remain legitimately unverified without blocking independent
    # Campaign / Agent Tasks / Opportunities proof validation.
    # Never treat an unverified conversation control as a template.


    proofs = defaultdict(
        lambda: defaultdict(list)
    )


    # --------------------------------------------------
    # CAMPAIGNS
    # --------------------------------------------------

    campaign_runtime = evidence_fresh("campaign_runtime", "campaigns")

    if campaign_runtime.get("status") == "VERIFIED_RUNTIME":
        try:
            certified=validate_control_proof(
                campaign_runtime, lane="campaigns",
                allowed=set(lanes["campaigns"]["controls"]))
        except PromotionProofError as exc:
            raise SystemExit("FAIL: campaign observer proof invalid") from exc
        for control in certified:
            proofs[
                "campaigns"
            ][control].append(
                rel("campaign_runtime")
            )


    campaign_outcomes = evidence_fresh("campaign_outcomes", "campaigns")

    if (
        campaign_outcomes.get(
            "output_quality_proved"
        )
        is True
    ):
        proofs[
            "campaigns"
        ]["output_quality"].append(
            rel("campaign_outcomes")
        )

    if (
        campaign_outcomes.get(
            "outcome_linkage_proved"
        )
        is True
        and int(
            campaign_outcomes.get(
                "exact_outcome_match_count",
                0,
            )
        ) > 0
    ):
        proofs[
            "campaigns"
        ]["outcome_linkage"].append(
            rel("campaign_outcomes")
        )


    # --------------------------------------------------
    # AGENT TASKS
    # --------------------------------------------------

    agent_tasks = evidence_fresh("agent_tasks", "agent_tasks")

    if (
        agent_tasks.get("status")
        == "VERIFIED_RUNTIME"
        and int(
            agent_tasks.get(
                "task_count",
                0,
            )
        ) > 0
    ):
        try:
            certified=validate_control_proof(
                agent_tasks, lane="agent_tasks",
                allowed=set(lanes["agent_tasks"]["controls"]))
        except PromotionProofError as exc:
            raise SystemExit("FAIL: agent task observer proof invalid") from exc
        for control in certified:
            proofs[
                "agent_tasks"
            ][control].append(
                rel("agent_tasks")
            )


    # --------------------------------------------------
    # OPPORTUNITIES
    # --------------------------------------------------

    opp_runtime = evidence_fresh("opportunities_runtime", "opportunities")

    if (
        opp_runtime.get("status")
        == "VERIFIED_RUNTIME"
        and int(
            opp_runtime.get(
                "opportunity_count",
                0,
            )
        ) > 0
    ):
        try:
            certified=validate_control_proof(
                opp_runtime, lane="opportunities",
                allowed=set(lanes["opportunities"]["controls"]))
        except PromotionProofError as exc:
            raise SystemExit("FAIL: opportunity observer proof invalid") from exc
        for control in certified:
            proofs[
                "opportunities"
            ][control].append(
                rel("opportunities_runtime")
            )


    opp_final = evidence_fresh("opportunities_final", "opportunities")

    if (
        opp_final.get(
            "entity_classification_proved"
        )
        is True
    ):
        proofs[
            "opportunities"
        ]["entity_classification"].append(
            rel("opportunities_final")
        )

    if (
        opp_final.get(
            "outcome_linkage_proved"
        )
        is True
        and int(
            opp_final.get(
                "exact_outcome_match_count",
                0,
            )
        ) > 0
    ):
        proofs[
            "opportunities"
        ]["outcome_linkage"].append(
            rel("opportunities_final")
        )


    opp_quarantine = evidence_fresh("opportunities_quarantine", "opportunities")

    if (
        opp_quarantine.get("status")
        == "VERIFIED_RUNTIME"
        and opp_quarantine.get(
            "control_active"
        )
        is True
        and int(
            opp_quarantine.get(
                "evaluated_count",
                0,
            )
        ) > 0
    ):
        proofs[
            "opportunities"
        ]["quarantine"].append(
            rel("opportunities_quarantine")
        )


    # --------------------------------------------------
    # PROMOTION
    # --------------------------------------------------

    targets = (
        "campaigns",
        "agent_tasks",
        "opportunities",
    )

    promoted = defaultdict(list)
    preserved = defaultdict(list)


    for lane_name in targets:
        lane = lanes[
            lane_name
        ]

        controls = lane[
            "controls"
        ]

        for control, sources in sorted(
            proofs[lane_name].items()
        ):
            if control not in controls:
                continue

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
                preserved[
                    lane_name
                ].append(control)

                continue

            # Promote only an EXISTING control in its own canonical lane.
            # An unrelated verified conversation row is not evidence for it.
            if (not isinstance(current, dict)
                or current.get("lane") != lane_name
                or current.get("control") != control
                or current.get("status") not in ("UNVERIFIED", "HOLD", "HOLD_REVIEW_REQUIRED")):
                raise SystemExit(
                    f"FAIL: invalid same-lane canonical slot: {lane_name}.{control}"
                )
            template = copy.deepcopy(current)

            template[
                "lane"
            ] = lane_name

            template[
                "control"
            ] = control

            template[
                "status"
            ] = "VERIFIED_RUNTIME"

            if "artifact_paths" in template:
                template[
                    "artifact_paths"
                ] = shaped(
                    template[
                        "artifact_paths"
                    ],
                    scalar=sources[0],
                    sequence=sources,
                )

            if "active_units" in template:
                unit = (
                    "global_runtime_binding_finalizer"
                )

                template[
                    "active_units"
                ] = shaped(
                    template[
                        "active_units"
                    ],
                    scalar=unit,
                    sequence=[unit],
                )

            if "matched_keys" in template:
                template[
                    "matched_keys"
                ] = shaped(
                    template[
                        "matched_keys"
                    ],
                    scalar=control,
                    sequence=[
                        control,
                        "VERIFIED_RUNTIME",
                    ],
                )

            if "reason" in template:
                template[
                    "reason"
                ] = (
                    "Verified by canonical production "
                    "runtime proof and promoted by the "
                    "global final binding pass. "
                    "OBSERVE semantics preserved."
                )

            # Proven control existence is NOT a calibrated likelihood.
            # Keep the lane-owner confidence unchanged.

            controls[
                control
            ] = template

            promoted[
                lane_name
            ].append(control)


    # --------------------------------------------------
    # FINAL CANONICAL COUNTS
    # --------------------------------------------------

    counts = {}
    remaining = {}

    for lane_name in targets:
        controls = lanes[
            lane_name
        ]["controls"]

        verified = sorted(
            name
            for name, row
            in controls.items()
            if isinstance(row, dict)
            and row.get(
                "status"
            )
            == "VERIFIED_RUNTIME"
        )

        open_controls = sorted(
            name
            for name, row
            in controls.items()
            if not (
                isinstance(row, dict)
                and row.get(
                    "status"
                )
                == "VERIFIED_RUNTIME"
            )
        )

        counts[
            lane_name
        ] = len(verified)

        remaining[
            lane_name
        ] = open_controls


    # No campaign conversion proof is a legitimate OBSERVE business
    # state, not a reason to fabricate a verified outcome. Require the
    # precise evidence-backed control set, not an unconditional 11/11.
    measured_campaign_outcome = (
        campaign_outcomes.get("outcome_linkage_proved") is True
        and int(campaign_outcomes.get("exact_outcome_match_count", 0)) > 0
    )
    for lane_name in (
        "campaigns",
        "agent_tasks",
        "opportunities",
    ):
        expected_remaining = (
            {"outcome_linkage"}
            if lane_name == "campaigns" and not measured_campaign_outcome
            else set()
        )
        if set(remaining[lane_name]) != expected_remaining:
            raise SystemExit(
                "FAIL: global finalizer evidence mismatch "
                f"for {lane_name}; verified="
                f"{counts[lane_name]}/11; remaining="
                + ",".join(remaining[lane_name])
            )


    # Optional audit metadata if the current canonical
    # document already supports top-level metadata.
    if isinstance(data, dict):
        data[
            "global_runtime_binding_finalized_at"
        ] = datetime.now(
            timezone.utc
        ).isoformat()


    atomic_binding_write(
        BINDINGS,
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        expected_bytes=original_bindings,
    )

for lane_name in targets:
    print(
        lane_name.upper()
        + "_CANONICAL:",
        counts[
            lane_name
        ],
        "/11",
    )

    print(
        lane_name.upper()
        + "_REMAINING:",
        ",".join(
            remaining[
                lane_name
            ]
        )
        or "none",
    )

print(
    "GLOBAL_CANONICAL_WRITE: PASS"
)
