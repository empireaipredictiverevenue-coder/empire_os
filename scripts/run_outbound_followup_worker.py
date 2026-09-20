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
        start_hour_utc=int(
            os.getenv("EMPIRE_OUTBOUND_WINDOW_START_UTC", "14")
        ),
        end_hour_utc=int(
            os.getenv("EMPIRE_OUTBOUND_WINDOW_END_UTC", "21")
        ),
    )
    payload = result.as_dict()
    payload["ok"] = not payload["errors"]
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
