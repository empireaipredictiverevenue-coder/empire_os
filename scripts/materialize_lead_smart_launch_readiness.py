#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

from empire_os.lead_smart_launch_readiness import (
    build_launch_readiness,
)


TRACKING = Path(
    "runtime/revenue/lead_smart/"
    "ringba/tracking_verification/latest.json"
)

ZIP_GATE = Path(
    "runtime/revenue/lead_smart/"
    "coverage/activation/latest.json"
)

ROUTING = Path(
    "runtime/revenue/lead_smart/"
    "ringba/routing_observation/latest.json"
)

OUT = Path(
    "runtime/revenue/lead_smart/"
    "launch_readiness/latest.json"
)


def load(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(
            f"missing evidence: {path}"
        )

    return json.loads(
        path.read_text()
    )


def main() -> int:
    result = build_launch_readiness(
        tracking=load(TRACKING),
        zip_gate=load(ZIP_GATE),
        routing=load(ROUTING),

        landing_publication_authorized=
            False,

        founder_live_traffic_authorized=
            False,
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

    tmp.write_text(payload)
    tmp.replace(OUT)

    print(payload, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
