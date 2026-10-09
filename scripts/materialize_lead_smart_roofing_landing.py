#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


SOURCE = Path(
    "templates/lead_smart/roofing/page.tsx"
)

TARGET = Path(
    "runtime/hermes_control/worker_code/"
    "apps/empire-public-site/src/app/"
    "roofing/page.tsx"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def materialize() -> dict[str, object]:
    if not SOURCE.exists():
        raise RuntimeError(
            f"canonical source missing: {SOURCE}"
        )

    payload = SOURCE.read_bytes()

    TARGET.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = TARGET.with_name(
        TARGET.name + ".tmp"
    )

    temporary.write_bytes(payload)
    temporary.replace(TARGET)

    source_hash = sha256(SOURCE)
    target_hash = sha256(TARGET)

    if source_hash != target_hash:
        raise RuntimeError(
            "materialized landing hash mismatch"
        )

    return {
        "source": str(SOURCE),
        "target": str(TARGET),
        "source_sha256": source_hash,
        "target_sha256": target_hash,
        "in_sync": True,
        "deployment_performed": False,
        "routing_changed": False,
        "traffic_changed": False,
        "execution_authority": "NONE",
    }


def check() -> dict[str, object]:
    source_exists = SOURCE.exists()
    target_exists = TARGET.exists()

    source_hash = (
        sha256(SOURCE)
        if source_exists
        else None
    )

    target_hash = (
        sha256(TARGET)
        if target_exists
        else None
    )

    return {
        "source": str(SOURCE),
        "target": str(TARGET),
        "source_exists": source_exists,
        "target_exists": target_exists,
        "source_sha256": source_hash,
        "target_sha256": target_hash,
        "in_sync": (
            source_exists
            and target_exists
            and source_hash == target_hash
        ),
        "deployment_performed": False,
        "execution_authority": "NONE",
    }


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--check",
        action="store_true",
    )

    args = parser.parse_args()

    result = (
        check()
        if args.check
        else materialize()
    )

    import json

    print(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
    )

    if args.check and not result["in_sync"]:
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
