#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from empire_os.lead_smart_zip_activation import (
    build_zip_targeting_gate,
)


SNAPSHOT = Path(
    "runtime/revenue/lead_smart/"
    "coverage/latest.json"
)

INTELLIGENCE = Path(
    "runtime/revenue/lead_smart/"
    "coverage/intelligence/latest.json"
)

ROOT = Path(
    "runtime/revenue/lead_smart/"
    "coverage/activation"
)

LATEST = ROOT / "latest.json"


def load(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(
            f"required evidence missing: {path}"
        )

    return json.loads(
        path.read_text()
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def main() -> int:
    result = build_zip_targeting_gate(
        snapshot=load(SNAPSHOT),
        intelligence=load(
            INTELLIGENCE
        ),
    )

    result["evidence_refs"] = {
        "coverage_snapshot":
            "sha256:" + sha256(
                SNAPSHOT
            ),

        "coverage_intelligence":
            "sha256:" + sha256(
                INTELLIGENCE
            ),
    }

    ROOT.mkdir(
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
                "schema_version":
                    result[
                        "schema_version"
                    ],

                "mode":
                    result["mode"],

                "zip_count":
                    result[
                        "zip_count"
                    ],

                "zip_targeting_gate_verified":
                    result[
                        "zip_targeting_gate_verified"
                    ],

                "zip_coverage_activation_verified":
                    result[
                        "zip_coverage_activation_verified"
                    ],

                "provider_runtime_route_verified":
                    result[
                        "provider_runtime_route_verified"
                    ],

                "provider_payout_guaranteed":
                    result[
                        "provider_payout_guaranteed"
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

                "latest_path":
                    str(LATEST),
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
