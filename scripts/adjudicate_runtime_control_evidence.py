# EMPIRE_WAVE_090B
from __future__ import annotations

import json
from pathlib import Path

from empire_os.detection_fabric import (
    CONTROL_NAMES,
)
from empire_os.runtime_control_adjudication import (
    adjudicate_control,
)
from empire_os.truth_quality_control import (
    now_iso,
)


ROOT = Path("/srv/empire_os")

INPUT = (
    ROOT
    / "runtime/control_plane/"
    "runtime_evidence_candidates_latest.json"
)

OUTPUT = (
    ROOT
    / "runtime/control_plane/"
    "runtime_control_bindings_latest.json"
)


def atomic_write(
    path,
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
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    tmp.replace(path)


def main():

    if not INPUT.exists():
        raise SystemExit(
            "090B FAIL: 090A candidate artifact missing"
        )

    candidates = json.loads(
        INPUT.read_text()
    )

    lane_results = []

    for lane in candidates.get(
        "lanes",
        [],
    ):

        name = lane[
            "lane"
        ]

        active_units = [
            item[
                "unit"
            ]

            for item
            in lane.get(
                "units",
                [],
            )

            if item.get(
                "active_state"
            )
            in {
                "active",
                "activating",
            }
        ]

        control_candidates = (
            lane.get(
                "control_candidates",
                {}
            )
        )

        controls = {}

        for control in CONTROL_NAMES:

            candidate = (
                control_candidates.get(
                    control,
                    {}
                )
            )

            result = adjudicate_control(
                root=ROOT,
                lane=name,
                control=control,
                artifact_paths=list(
                    candidate.get(
                        "artifact_paths",
                        []
                    )
                ),
                active_units=active_units,
            )

            controls[
                control
            ] = result.as_dict()

        verified = [
            name
            for name, result
            in controls.items()
            if result[
                "status"
            ] == "VERIFIED_RUNTIME"
        ]

        unverified = [
            name
            for name, result
            in controls.items()
            if result[
                "status"
            ] != "VERIFIED_RUNTIME"
        ]

        lane_results.append(
            {
                "lane":
                    name,

                "verified_runtime_control_count":
                    len(
                        verified
                    ),

                "unverified_control_count":
                    len(
                        unverified
                    ),

                "verified_controls":
                    verified,

                "unverified_controls":
                    unverified,

                "controls":
                    controls,
            }
        )

    payload = {
        "schema_version":
            "empire-runtime-control-bindings-v1",

        "generated_at":
            now_iso(),

        "authority":
            "OBSERVE",

        "automatic_action_authority":
            False,

        "verification_rule":
            (
                "recent structured runtime JSON + "
                "exact control signature + runtime metadata"
            ),

        "lanes":
            lane_results,

        "governance": {
            "source_text_can_verify":
                False,

            "filename_can_verify":
                False,

            "generic_keyword_can_verify":
                False,

            "db_write":
                False,

            "outbound":
                False,

            "traffic":
                False,

            "funds":
                False,
        },
    }

    atomic_write(
        OUTPUT,
        payload,
    )

    print(
        json.dumps(
            {
                "status":
                    "PASS",

                "lanes": [
                    {
                        "lane":
                            lane[
                                "lane"
                            ],

                        "verified":
                            lane[
                                "verified_runtime_control_count"
                            ],

                        "unverified":
                            lane[
                                "unverified_control_count"
                            ],

                        "verified_controls":
                            lane[
                                "verified_controls"
                            ],
                    }

                    for lane
                    in lane_results
                ],

                "authority":
                    "OBSERVE",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
