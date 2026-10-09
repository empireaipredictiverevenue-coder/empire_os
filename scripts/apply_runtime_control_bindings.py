# EMPIRE_WAVE_090B
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from empire_os.detection_fabric import (
    lane_risk,
)


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


def measured_campaign_outcome_proven():
    proof = ROOT / "runtime/campaigns_control/campaign_measured_outcome_latest.json"
    try:
        data = json.loads(proof.read_text())
    except (OSError, ValueError):
        return False
    return (
        data.get("outcome_linkage_proved") is True
        and "outcome_linkage" in (data.get("runtime_verified_controls") or [])
        and int(data.get("exact_outcome_match_count") or 0) > 0
    )


def atomic_write(path, payload):
    """Durably publish Fabric output with a unique sibling temp file."""
    target = Path(path)
    fd, name = tempfile.mkstemp(prefix=f'.{target.name}.', suffix='.tmp', dir=target.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, default=str)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, target)
        dirfd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main():

    if (
        not FABRIC.exists()
        or not BINDINGS.exists()
    ):
        raise SystemExit(
            "090B FAIL: fabric/bindings artifact missing"
        )

    fabric = json.loads(
        FABRIC.read_text()
    )

    bindings = json.loads(
        BINDINGS.read_text()
    )

    bind_index = {
        lane[
            "lane"
        ]:
            lane

        for lane
        in bindings.get(
            "lanes",
            [],
        )
    }

    for lane in fabric.get(
        "lanes",
        [],
    ):

        binding = bind_index.get(
            lane[
                "lane"
            ],
            {},
        )

        controls = binding.get(
            "controls",
            {},
        )

        for control, state in (
            lane.get(
                "controls",
                {}
            ).items()
        ):

            # An older Fabric snapshot cannot retain an outcome claim after
            # its exact Campaign measurement has been invalidated.
            if lane["lane"] == "campaigns" and control == "outcome_linkage" and not measured_campaign_outcome_proven():
                state["status"] = "SOURCE_EVIDENCE_ONLY" if state.get("source_evidence") else "MISSING_OR_UNVERIFIED"
                state["runtime_evidence"] = None
                continue

            # Existing VERIFIED_RUNTIME evidence,
            # such as the buyer reference lane,
            # is never downgraded.
            if (
                state.get(
                    "status"
                )
                == "VERIFIED_RUNTIME"
            ):
                continue

            proof = controls.get(
                control
            )

            if (
                proof
                and proof.get(
                    "status"
                )
                == "VERIFIED_RUNTIME"
            ):

                state[
                    "status"
                ] = "VERIFIED_RUNTIME"

                state[
                    "runtime_evidence"
                ] = {
                    "artifact_paths":
                        proof.get(
                            "artifact_paths",
                            [],
                        ),

                    "matched_keys":
                        proof.get(
                            "matched_keys",
                            [],
                        ),

                    "active_units":
                        proof.get(
                            "active_units",
                            [],
                        ),

                    "confidence":
                        proof.get(
                            "confidence"
                        ),

                    "adjudication":
                        proof.get(
                            "reason"
                        ),
                }

        verified = [
            name
            for name, item
            in lane[
                "controls"
            ].items()
            if item[
                "status"
            ] == "VERIFIED_RUNTIME"
        ]

        source_only = [
            name
            for name, item
            in lane[
                "controls"
            ].items()
            if item[
                "status"
            ] == "SOURCE_EVIDENCE_ONLY"
        ]

        missing = [
            name
            for name, item
            in lane[
                "controls"
            ].items()
            if item[
                "status"
            ] == "MISSING_OR_UNVERIFIED"
        ]

        unverified = [
            name
            for name, item
            in lane[
                "controls"
            ].items()
            if item[
                "status"
            ] != "VERIFIED_RUNTIME"
        ]

        lane[
            "verified_runtime_controls"
        ] = verified

        lane[
            "source_evidence_only_controls"
        ] = source_only

        lane[
            "missing_or_unverified_controls"
        ] = missing

        lane[
            "runtime_unverified_controls"
        ] = unverified

        lane[
            "runtime_verified_control_count"
        ] = len(
            verified
        )

        lane[
            "runtime_unverified_control_count"
        ] = len(
            unverified
        )

        lane[
            "risk"
        ] = lane_risk(
            lane[
                "lane_status"
            ],
            (
                item[
                    "status"
                ]
                for item
                in lane[
                    "controls"
                ].values()
            ),
        )

    active = [
        lane
        for lane
        in fabric[
            "lanes"
        ]
        if lane[
            "lane_status"
        ] != "NOT_DETECTED"
    ]

    fabric[
        "verified_runtime_control_count"
    ] = sum(
        lane[
            "runtime_verified_control_count"
        ]
        for lane in active
    )

    fabric[
        "source_evidence_control_count"
    ] = sum(
        len(
            lane[
                "source_evidence_only_controls"
            ]
        )
        for lane in active
    )

    fabric[
        "missing_control_count"
    ] = sum(
        len(
            lane[
                "missing_or_unverified_controls"
            ]
        )
        for lane in active
    )

    fabric[
        "runtime_unverified_control_count"
    ] = sum(
        lane[
            "runtime_unverified_control_count"
        ]
        for lane in active
    )

    fabric[
        "missing_or_unverified_control_count"
    ] = fabric[
        "runtime_unverified_control_count"
    ]

    risk_order = {
        "HIGH": 0,
        "MEDIUM": 1,
        "LOW": 2,
        "CONTROLLED": 3,
    }

    priorities = []

    for lane in active:

        if lane[
            "risk"
        ] == "CONTROLLED":
            continue

        priorities.append(
            {
                "lane":
                    lane[
                        "lane"
                    ],

                "risk":
                    lane[
                        "risk"
                    ],

                "runtime_verified_control_count":
                    lane[
                        "runtime_verified_control_count"
                    ],

                "runtime_unverified_control_count":
                    lane[
                        "runtime_unverified_control_count"
                    ],

                "missing_control_count":
                    len(
                        lane[
                            "missing_or_unverified_controls"
                        ]
                    ),

                "runtime_unverified_controls":
                    lane[
                        "runtime_unverified_controls"
                    ],

                "missing_controls":
                    lane[
                        "missing_or_unverified_controls"
                    ],

                "source_evidence_only_controls":
                    lane[
                        "source_evidence_only_controls"
                    ],
            }
        )

    priorities.sort(
        key=lambda item: (
            risk_order.get(
                item[
                    "risk"
                ],
                9,
            ),
            -item[
                "runtime_unverified_control_count"
            ],
            -item[
                "missing_control_count"
            ],
            item[
                "lane"
            ],
        )
    )

    fabric[
        "priority_lanes"
    ] = priorities

    fabric[
        "runtime_binding_overlay"
    ] = {
        "schema_version":
            bindings.get(
                "schema_version"
            ),

        "generated_at":
            bindings.get(
                "generated_at"
            ),

        "rule":
            bindings.get(
                "verification_rule"
            ),

        "authority":
            "OBSERVE",
    }

    atomic_write(
        FABRIC,
        fabric,
    )

    print(
        json.dumps(
            {
                "status":
                    "PASS",

                "verified_runtime_controls":
                    fabric[
                        "verified_runtime_control_count"
                    ],

                "runtime_unverified_controls":
                    fabric[
                        "runtime_unverified_control_count"
                    ],

                "priority_lanes":
                    priorities,

                "authority":
                    "OBSERVE",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
