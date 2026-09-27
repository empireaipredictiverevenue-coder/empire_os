#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os

from empire_os.outbound_followup_worker import run_followup_worker
from empire_os.qualification_worker_v2 import request_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()
    result = run_followup_worker(
        request_json,
        limit=args.limit,
        start_hour_local=int(
            os.getenv("EMPIRE_OUTBOUND_LOCAL_START_HOUR", "8")
        ),
        end_hour_local=int(
            os.getenv("EMPIRE_OUTBOUND_LOCAL_END_HOUR", "18")
        ),
    )
    payload = result.as_dict()
    payload["ok"] = not payload["errors"]
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
