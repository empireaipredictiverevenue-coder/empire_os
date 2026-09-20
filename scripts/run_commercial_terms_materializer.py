#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.commercial_terms_materializer import (
    run_commercial_terms_materializer,
)

LATEST = Path("/srv/empire_os/runtime/commercial_terms_materializer/latest.json")


def _write(payload: dict) -> None:
    LATEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = LATEST.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(LATEST)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan-limit", type=int, default=25)
    parser.add_argument("--proposal-limit", type=int, default=5)
    args = parser.parse_args()

    result = run_commercial_terms_materializer(
        scan_limit=args.scan_limit,
        proposal_limit=args.proposal_limit,
    )
    payload = result.as_dict()
    payload["mode"] = "INTERNAL_MATERIALIZE"
    payload["owner"] = "astra"
    payload["ok"] = not payload["errors"]
    _write(payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
