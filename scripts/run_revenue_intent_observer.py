#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from empire_os.revenue_intent_observer import (
    normalize_file,
)
from empire_os.revenue_identity_handoff import (
    process_identity_handoffs,
)


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--source",
        required=True,
    )

    parser.add_argument(
        "--normalized",
        required=True,
    )

    parser.add_argument(
        "--queue",
        required=True,
    )

    parser.add_argument(
        "--lock",
        required=True,
    )

    parser.add_argument(
        "--route-limit",
        type=int,
        default=50,
    )

    parser.add_argument(
        "--process-limit",
        type=int,
        default=50,
    )

    args = parser.parse_args()

    report = normalize_file(
        Path(args.source),
        Path(args.normalized),
    )

    command = [
        sys.executable,
        str(
            Path(__file__).with_name(
                "run_intent_actor_cycle.py"
            )
        ),
        "--signal-inbox",
        args.normalized,
        "--queue",
        args.queue,
        "--lock",
        args.lock,
        "--route-limit",
        str(args.route_limit),
        "--process-limit",
        str(args.process_limit),
    ]

    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )

    if completed.stderr:
        print(
            completed.stderr,
            file=sys.stderr,
            end="",
        )

    if completed.returncode != 0:
        if completed.stdout:
            print(
                completed.stdout,
                end="",
            )

        return int(
            completed.returncode
        )

    cycle = json.loads(
        completed.stdout
    )

    routing = cycle.get(
        "routing",
        {},
    )

    processing = cycle.get(
        "processing",
        {},
    )

    considered = int(
        routing.get(
            "considered",
            0,
        )
        or 0
    )

    failed = int(
        processing.get(
            "failed",
            0,
        )
        or 0
    )

    if considered <= 0:
        raise RuntimeError(
            "Revenue Intent Observer consumed zero signals"
        )

    if failed:
        raise RuntimeError(
            f"Revenue Intent Observer actor failures={failed}"
        )

    identity_handoff = process_identity_handoffs(
        queue=Path(args.queue),
        state=(
            Path(args.queue).parent
            / "identity_handoff.json"
        ),
        lock=(
            Path(args.queue).parent
            / "identity_handoff.lock"
        ),
        limit=25,
    )

    output = {
        "schema_version":
            "empire.revenue_intent_observer.v2",
        "mode":
            "OBSERVE",
        "execution_authority":
            "none",
        "normalization": {
            "source_schema_version":
                report.get(
                    "source_schema_version"
                ),
            "source_collection_path":
                report.get(
                    "source_collection_path"
                ),
            "observation_count":
                report.get(
                    "observation_count"
                ),
        },
        "cycle":
            cycle,
        "identity_handoff":
            identity_handoff,
    }

    print(
        json.dumps(
            output,
            indent=2,
            sort_keys=True,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
