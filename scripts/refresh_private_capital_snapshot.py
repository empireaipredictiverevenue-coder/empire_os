#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.parse
from pathlib import Path
from typing import Any

from empire_os.private_capital_snapshot import fetch_private_capital_snapshot
from empire_os.qualification_worker_v2 import request_json


OUT = Path(
    os.getenv(
        "EMPIRE_PRIVATE_CAPITAL_LATEST",
        "/srv/empire_os/runtime/vertical_intelligence/private_capital_latest.json",
    )
)


def reader(path: str, params: dict[str, str]) -> Any:
    query = urllib.parse.urlencode(params)
    return request_json("GET", f"{path}?{query}")


def main() -> int:
    snapshot = fetch_private_capital_snapshot(reader)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(tmp, 0o644)
    tmp.replace(OUT)
    os.chmod(OUT, 0o644)

    print(json.dumps({
        **snapshot,
        "snapshot_path": str(OUT),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
