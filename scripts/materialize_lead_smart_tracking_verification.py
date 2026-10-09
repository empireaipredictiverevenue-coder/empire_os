#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from empire_os.lead_smart_tracking_verification import (
    build_tracking_verification,
)


SOURCE = Path(
    "runtime/revenue/lead_smart/"
    "ringba/tracking_observation/latest.json"
)

ROOT = Path(
    "runtime/revenue/lead_smart/"
    "ringba/tracking_verification"
)

LATEST = ROOT / "latest.json"


def main() -> int:
    if not SOURCE.exists():
        raise RuntimeError(
            "tracking observation missing"
        )

    source_bytes = SOURCE.read_bytes()

    source_sha256 = (
        hashlib.sha256(
            source_bytes
        ).hexdigest()
    )

    observation = json.loads(
        source_bytes
    )

    verification = (
        build_tracking_verification(
            observation,
            source_sha256=source_sha256,
        )
    )

    ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    snapshots = (
        ROOT / "snapshots"
    )

    snapshots.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = (
        json.dumps(
            verification,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    stamp = (
        verification[
            "verified_at"
        ]
        .replace("-", "")
        .replace(":", "")
        .replace("+00:00", "Z")
        .replace(".", "_")
    )

    snapshot_path = (
        snapshots
        / (
            f"{stamp}_"
            f"{source_sha256[:12]}.json"
        )
    )

    if not snapshot_path.exists():
        snapshot_path.write_text(
            payload
        )

    tmp = (
        ROOT
        / ".latest.json.tmp"
    )

    tmp.write_text(
        payload
    )

    tmp.replace(
        LATEST
    )

    print(
        json.dumps(
            {
                "status":
                    verification["state"],

                "tracking_verified":
                    verification[
                        "tracking_verified"
                    ],

                "verification_scope":
                    verification[
                        "verification_scope"
                    ],

                "verification_path":
                    verification[
                        "verification_path"
                    ],

                "source_age_seconds":
                    verification[
                        "source_age_seconds"
                    ],

                "source_sha256":
                    source_sha256,

                "snapshot_path":
                    str(
                        snapshot_path
                    ),

                "latest_path":
                    str(LATEST),

                "routing_verified":
                    False,

                "routing_enabled":
                    False,

                "traffic_enabled":
                    False,

                "execution_authority":
                    "NONE",
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
