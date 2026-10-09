#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

from empire_os.lead_smart_ringba_routing_observer import (
    observe_from_environment,
)


OUT = Path(
    "runtime/revenue/lead_smart/"
    "ringba/routing_observation/latest.json"
)


def main() -> int:
    result = observe_from_environment()

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
        payload,
        end="",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
