# EMPIRE_WAVE_090C_C
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from empire_os.consent_suppression_governor_shadow import (
    python_paths_from_execstart,
    trace_local_graph,
)


ROOT = Path("/srv/empire_os")

CONTROL = (
    ROOT
    / "runtime/consent_suppression/latest.json"
)

OUT = (
    ROOT
    / "runtime/consent_suppression/"
      "governor_shadow_latest.json"
)


def unit_props(
    unit,
):

    result = subprocess.run(
        [
            "systemctl",
            "show",
            unit,
            "--property=ActiveState",
            "--property=SubState",
            "--property=UnitFileState",
            "--property=ExecMainStatus",
            "--property=ExecStart",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    props = {}

    for line in result.stdout.splitlines():

        if "=" not in line:
            continue

        key, value = line.split(
            "=",
            1,
        )

        props[
            key
        ] = value

    return props


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
        )
        + "\n",
        encoding="utf-8",
    )

    tmp.replace(
        path
    )


def main():

    control = json.loads(
        CONTROL.read_text()
    )

    coverage = (
        control.get(
            "semantic_coverage",
            {}
        )
    )

    if (
        coverage.get(
            "effectiveness"
        )
        != "EFFECTIVE_IDENTITY_BINDING"
    ):

        raise SystemExit(
            "090C-C HOLD: identity coverage not effective"
        )

    service = unit_props(
        "empire-outbound-governor.service"
    )

    timer = unit_props(
        "empire-outbound-governor.timer"
    )

    entries = (
        python_paths_from_execstart(
            service.get(
                "ExecStart",
                "",
            )
        )
    )

    # If systemd serialization hides the script path,
    # fall back only to the known existing worker path.
    fallback = (
        ROOT
        / "scripts/outbound_governor_worker.py"
    )

    if (
        not entries
        and fallback.exists()
    ):
        entries = [
            fallback
        ]

    all_nodes = {}

    for entry in entries:

        for node in trace_local_graph(
            entry
        ):

            all_nodes[
                node.path
            ] = node

    nodes = [
        all_nodes[
            key
        ]
        for key in sorted(
            all_nodes
        )
    ]

    suppression_nodes = [
        node
        for node in nodes
        if node.suppression_signals
    ]

    exact_table_consumers = [
        node.path
        for node in suppression_nodes
        if (
            "outbound_suppressions"
            in node.suppression_signals
        )
    ]

    decision_consumers = [
        node.path
        for node in suppression_nodes
        if any(
            signal in node.suppression_signals
            for signal in (
                "is_suppressed",
                "check_suppression",
                "suppressed",
            )
        )
    ]

    timer_active = (
        timer.get(
            "ActiveState"
        )
        == "active"
    )

    execution_path_present = bool(
        entries
    )

    suppression_path_present = bool(
        suppression_nodes
    )

    shadow_contract_proven = all(
        (
            timer_active,
            execution_path_present,
            suppression_path_present,
        )
    )

    # Existing suppression control says BLOCK/HOLD only.
    output = control[
        "output_quality"
    ]

    shadow_decision = {
        "block_count":
            int(
                output.get(
                    "block_count",
                    0,
                )
            ),

        "hold_count":
            int(
                output.get(
                    "hold_count",
                    0,
                )
            ),

        "allow_count":
            int(
                output.get(
                    "allow_decision_count",
                    0,
                )
            ),

        "fail_closed":
            (
                int(
                    output.get(
                        "allow_decision_count",
                        0,
                    )
                )
                == 0
            ),
    }

    # A healthy timer and traced suppression source are not sufficient.
    governance = control.get("governance")
    shadow_contract_proven = (
        shadow_contract_proven
        and shadow_decision["fail_closed"] is True
        and control.get("mode") == "OBSERVE"
        and control.get("live_action_authority_verified") is False
        and isinstance(governance, dict)
        and all(governance.get(key) is False
                for key in ("outbound", "db_write", "traffic", "funds"))
    )

    payload = {
        "schema_version":
            "empire-consent-governor-shadow-v1",

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "mode":
            "OBSERVE",

        "identity_coverage":
            coverage,

        "live_governor": {
            "service_active":
                service.get(
                    "ActiveState"
                ),

            "service_substate":
                service.get(
                    "SubState"
                ),

            "timer_active":
                timer.get(
                    "ActiveState"
                ),

            "timer_substate":
                timer.get(
                    "SubState"
                ),

            "timer_enabled":
                timer.get(
                    "UnitFileState"
                ),

            "entrypoints": [
                str(
                    p.relative_to(
                        ROOT
                    )
                )
                for p in entries
            ],
        },

        "execution_trace": {
            "node_count":
                len(
                    nodes
                ),

            "nodes": [
                node.as_dict()
                for node in nodes
            ],

            "suppression_nodes": [
                node.path
                for node
                in suppression_nodes
            ],

            "exact_table_consumers":
                exact_table_consumers,

            "decision_consumers":
                decision_consumers,
        },

        "shadow_decision":
            shadow_decision,

        "shadow_action_authority": {
            "verified":
                shadow_contract_proven,

            "live_execution_authority":
                False,

            "reason":
                (
                    "Live governor execution path contains "
                    "existing suppression logic, but this "
                    "wave does not modify or invoke send authority."
                ),
        },

        "outcome_linkage_verified":
            False,

        "governance": {
            "db_write":
                False,

            "outbound":
                False,

            "traffic":
                False,

            "funds":
                False,

            "governor_source_modified":
                False,

            "live_authority_changed":
                False,
        },
    }

    atomic_write(
        OUT,
        payload,
    )

    print(
        json.dumps(
            {
                "status":
                    (
                        "PASS"
                        if shadow_contract_proven
                        else "HOLD"
                    ),

                "timer_active":
                    timer_active,

                "entrypoints":
                    payload[
                        "live_governor"
                    ][
                        "entrypoints"
                    ],

                "trace_nodes":
                    len(
                        nodes
                    ),

                "suppression_nodes":
                    payload[
                        "execution_trace"
                    ][
                        "suppression_nodes"
                    ],

                "exact_table_consumers":
                    exact_table_consumers,

                "decision_consumers":
                    decision_consumers,

                "shadow_block":
                    shadow_decision[
                        "block_count"
                    ],

                "shadow_hold":
                    shadow_decision[
                        "hold_count"
                    ],

                "shadow_allow":
                    shadow_decision[
                        "allow_count"
                    ],

                "shadow_authority_verified":
                    shadow_contract_proven,

                "live_authority":
                    False,

                "mode":
                    "OBSERVE",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
