#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )

from empire_os.lead_smart_effective_pilot_state import (
    build_effective_pilot_state,
)

from scripts.materialize_lead_smart_roofing_pilot import (
    build_review,
)


TRACKING = Path(
    "runtime/revenue/lead_smart/"
    "ringba/tracking_verification/latest.json"
)

ROUTING = Path(
    "runtime/revenue/lead_smart/"
    "ringba/routing_observation/latest.json"
)

COVERAGE = Path(
    "runtime/revenue/lead_smart/"
    "coverage/intelligence/latest.json"
)

ZIP_GATE = Path(
    "runtime/revenue/lead_smart/"
    "coverage/activation/latest.json"
)

OUT = Path(
    "runtime/revenue/lead_smart/"
    "effective_pilot_state/latest.json"
)


def load(
    path: Path,
) -> dict:
    if not path.exists():
        raise RuntimeError(
            f"missing evidence: {path}"
        )

    return json.loads(
        path.read_text()
    )


def digest(
    path: Path,
) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def main() -> int:
    base = build_review()

    result = (
        build_effective_pilot_state(
            base_review=
                base,

            tracking_verification=
                load(TRACKING),

            routing_observation=
                load(ROUTING),

            coverage_intelligence=
                load(COVERAGE),

            zip_activation=
                load(ZIP_GATE),

            evidence_refs={
                "tracking_verification":
                    (
                        "sha256:"
                        + digest(
                            TRACKING
                        )
                    ),

                "routing_observation":
                    (
                        "sha256:"
                        + digest(
                            ROUTING
                        )
                    ),

                "coverage_intelligence":
                    (
                        "sha256:"
                        + digest(
                            COVERAGE
                        )
                    ),

                "zip_activation":
                    (
                        "sha256:"
                        + digest(
                            ZIP_GATE
                        )
                    ),
            },
        )
    )

    OUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = (
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    tmp = OUT.with_suffix(
        ".tmp"
    )

    tmp.write_text(
        payload
    )

    tmp.replace(
        OUT
    )

    print(
        json.dumps(
            {
                "schema_version":
                    result[
                        "schema_version"
                    ],

                "mode":
                    result["mode"],

                "tracking_verified":
                    result[
                        "tracking"
                    ]["verified"],

                "routing_configuration_observed":
                    result[
                        "routing"
                    ][
                        "configuration_observed"
                    ],

                "routing_runtime_verified":
                    result[
                        "routing"
                    ][
                        "runtime_verified"
                    ],

                "coverage_observed":
                    result[
                        "coverage"
                    ]["observed"],

                "zip_activation_verified":
                    result[
                        "coverage"
                    ][
                        "activation_verified"
                    ],

                "call_cta_enabled":
                    result[
                        "call_cta_enabled"
                    ],

                "routing_enabled":
                    result[
                        "routing_enabled"
                    ],

                "traffic_enabled":
                    result[
                        "traffic_enabled"
                    ],

                "execution_authority":
                    result[
                        "execution_authority"
                    ],

                "output":
                    str(OUT),
            },
            indent=2,
            sort_keys=True,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
