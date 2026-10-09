#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from empire_os.revenue_capacity_board import (
    build_revenue_capacity_board_runtime,
)


ROOT = Path("/srv/empire_os")

OUTPUT = (
    ROOT
    / "runtime"
    / "revenue_capacity_board"
    / "latest.json"
)


def main() -> int:
    board = (
        build_revenue_capacity_board_runtime(
            ROOT
        )
    )

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp = OUTPUT.with_suffix(
        ".json.tmp"
    )

    temp.write_text(
        json.dumps(
            board,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    temp.replace(
        OUTPUT
    )

    print(
        json.dumps(
            board,
            indent=2,
            sort_keys=True,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
