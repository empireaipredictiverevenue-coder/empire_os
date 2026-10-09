#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

from empire_os.lead_smart_launch_readiness import (
    build_launch_readiness,
)
from empire_os.buyer_supply_policy import lead_smart_confirmed_roofing_policy


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
    policy = lead_smart_confirmed_roofing_policy(
        source_ref="gmail:1a10c6b2530f2951"
    )
    direct = policy["routing"]["direct_route_requirements"]
    result = build_launch_readiness(
        tracking=load(TRACKING),
        zip_gate=load(ZIP_GATE),
        routing=load(ROUTING),

        operating_hours=policy["operating_hours"],

        # Verified source: Lead Smart Support Agent 9 October 2026.
        timezone_confirmation=policy["operating_hours_confirmation"],

        # Pass-through is contractually required on Direct, but evidence
        # of the runtime caller-ANI path has not been independently proved.
        caller_id_pass_through_verified=(
            direct["caller_id_pass_through_verified"] is True
        ),

        buyer_landing_page_approved=(
            policy["routing"]["landing_review_report"]["approved"] is True
        ),

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
