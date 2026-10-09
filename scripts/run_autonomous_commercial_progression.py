#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.autonomous_commercial_progression_runtime import (
    run_internal_cycle,
)
from empire_os.acp_runtime_authority import (
    load_acp_execution_authority,
)
from empire_os.next_best_action import (
    build_next_best_action_runtime,
    refresh_next_best_action_snapshot,
)


ROOT = Path("/srv/empire_os")


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--execute-internal",
        action="store_true",
        help="Request internal progression; does not grant mutation authority.",
    )

    args = parser.parse_args()

    try:
        snapshot = (
            refresh_next_best_action_snapshot(
                ROOT
            )
        )
    except Exception:
        snapshot = (
            build_next_best_action_runtime(
                ROOT
            )
        )

    execution_authority, authority_source = (
        load_acp_execution_authority()
    )

    result = run_internal_cycle(
        snapshot,
        execute=args.execute_internal,
        execution_authority=execution_authority,
    )

    # Receipt evidence only. Never expose capability contents.
    result["execution_authority_source"] = authority_source

    print(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
            default=str,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
