#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from empire_os.commercial_evidence_auto_verifier import (
    run_commercial_evidence_auto_verifier,
)
from empire_os.qualification_worker_v2 import request_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 100:
        parser.error("--limit must be between 1 and 100")

    result = run_commercial_evidence_auto_verifier(
        request_json,
        limit=args.limit,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
