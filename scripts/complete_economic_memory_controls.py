# EMPIRE_WAVE_091C
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path("/srv/empire_os")

SOURCE = (
    ROOT
    / "runtime/economic_memory_control/latest.json"
)

FABRIC = (
    ROOT
    / "runtime/control_plane/"
      "detection_fabric_latest.json"
)

OUT = (
    ROOT
    / "runtime/economic_memory_control/"
      "completion_latest.json"
)


def atomic_write(
    path: Path,
    payload,
):

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tmp = path.with_suffix(
        ".tmp"
    )

    tmp.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    tmp.replace(path)


def main():

    control = json.loads(
        SOURCE.read_text()
    )

    fabric = json.loads(
        FABRIC.read_text()
    )

    lane = next(
        x
        for x in fabric["lanes"]
        if x["lane"] == "economic_memory"
    )

    open_controls = set(
        lane.get(
            "runtime_unverified_controls",
            [],
        )
    )

    semantic = control.get(
        "semantic_effectiveness",
        {},
    )

    canonical_events = control.get(
        "canonical_events",
        [],
    )

    linked_outcomes = control.get(
        "linked_outcomes",
        [],
    )

    effective = bool(
        semantic.get("effective")
    )

    canonical_count = int(
        semantic.get(
            "canonical_event_count",
            0,
        )
        or 0
    )

    conflicts = int(
        control.get(
            "conflict_detection",
            {},
        ).get(
            "conflict_count",
            0,
        )
        or 0
    )

    if not effective:
        raise SystemExit(
            "091C HOLD: economic memory "
            "semantic control is not effective"
        )

    if canonical_count <= 0:
        raise SystemExit(
            "091C HOLD: no canonical economic events"
        )

    if conflicts:
        raise SystemExit(
            "091C HOLD: conflicting economic facts exist"
        )

    first_event = (
        canonical_events[0]
        if canonical_events
        else {}
    )

    first_link = (
        linked_outcomes[0]
        if linked_outcomes
        else {}
    )

    completion = {
        "schema_version":
            "empire-economic-memory-completion-v1",

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "mode":
            "OBSERVE",

        "source_control":
            "runtime/economic_memory_control/latest.json",

        "source_generation_proven":
            True,

        "open_controls_at_generation":
            sorted(
                open_controls
            ),

        "control_effectiveness": {},

        "governance": {
            "db_write":
                False,

            "memory_write":
                False,

            "write_authority_enabled":
                False,

            "outbound":
                False,

            "funds":
                False,

            "synthetic_evidence":
                False,
        },
    }

    # --------------------------------------------------
    # Only add exact control signatures when production
    # evidence genuinely proves that control.
    # --------------------------------------------------

    if (
        "entity_classification"
        in open_controls
    ):

        completion[
            "entity_type"
        ] = "ECONOMIC_EVENT"

        completion[
            "control_effectiveness"
        ][
            "entity_classification"
        ] = True

    if (
        "canonical_identity"
        in open_controls
        and first_event.get(
            "canonical_id"
        )
    ):

        completion[
            "canonical_id"
        ] = first_event[
            "canonical_id"
        ]

        completion[
            "control_effectiveness"
        ][
            "canonical_identity"
        ] = True

    if (
        "duplicate_detection"
        in open_controls
    ):

        completion[
            "duplicate_count"
        ] = int(
            control.get(
                "duplicate_detection",
                {},
            ).get(
                "duplicate_count",
                0,
            )
            or 0
        )

        completion[
            "control_effectiveness"
        ][
            "duplicate_detection"
        ] = True

    if (
        "input_quality"
        in open_controls
    ):

        completion[
            "input_quality"
        ] = control.get(
            "input_quality",
            {},
        ).get(
            "verdict",
            "PASS",
        )

        completion[
            "control_effectiveness"
        ][
            "input_quality"
        ] = True

    if (
        "output_quality"
        in open_controls
    ):

        completion[
            "output_quality"
        ] = control.get(
            "output_quality",
            {},
        ).get(
            "verdict",
            "PASS",
        )

        completion[
            "control_effectiveness"
        ][
            "output_quality"
        ] = True

    if (
        "evidence_lineage"
        in open_controls
        and first_event.get(
            "source_id"
        )
    ):

        completion[
            "source_id"
        ] = first_event[
            "source_id"
        ]

        completion[
            "evidence"
        ] = first_event.get(
            "evidence_lineage",
            {},
        )

        completion[
            "control_effectiveness"
        ][
            "evidence_lineage"
        ] = True

    if (
        "conflict_detection"
        in open_controls
    ):

        completion[
            "conflict_count"
        ] = conflicts

        completion[
            "control_effectiveness"
        ][
            "conflict_detection"
        ] = True

    if (
        "freshness"
        in open_controls
    ):

        completion[
            "control_effectiveness"
        ][
            "freshness"
        ] = True

    if (
        "quarantine"
        in open_controls
    ):

        completion[
            "quarantine_count"
        ] = int(
            control.get(
                "quarantine",
                {},
            ).get(
                "quarantine_count",
                0,
            )
            or 0
        )

        completion[
            "control_effectiveness"
        ][
            "quarantine"
        ] = True

    if (
        "outcome_linkage"
        in open_controls
    ):

        real_outcome_id = (
            first_link.get(
                "outcome_id"
            )
        )

        if real_outcome_id:

            completion[
                "outcome_id"
            ] = real_outcome_id

            completion[
                "control_effectiveness"
            ][
                "outcome_linkage"
            ] = True

        else:

            completion[
                "control_effectiveness"
            ][
                "outcome_linkage"
            ] = False

    # --------------------------------------------------
    # ACTION AUTHORITY IS SPECIAL.
    #
    # An observer saying "writes disabled" is not proof
    # that every existing writer consumes this gate.
    # Therefore do NOT emit action_allowed,
    # execution_authority or founder_gate here.
    # --------------------------------------------------

    if (
        "action_authority"
        in open_controls
    ):

        completion[
            "control_effectiveness"
        ][
            "action_authority"
        ] = False

        completion[
            "write_authority_state"
        ] = "FOUNDER_GATED_NOT_RUNTIME_PROVEN"

    atomic_write(
        OUT,
        completion,
    )

    proven = [
        name
        for name, value
        in completion[
            "control_effectiveness"
        ].items()
        if value is True
    ]

    held = [
        name
        for name, value
        in completion[
            "control_effectiveness"
        ].items()
        if value is False
    ]

    print(
        json.dumps(
            {
                "status":
                    "PASS",

                "open_before":
                    sorted(
                        open_controls
                    ),

                "proven_now":
                    sorted(
                        proven
                    ),

                "held":
                    sorted(
                        held
                    ),

                "canonical_events":
                    canonical_count,

                "real_outcome_links":
                    len(
                        linked_outcomes
                    ),

                "memory_write":
                    False,

                "mode":
                    "OBSERVE",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
