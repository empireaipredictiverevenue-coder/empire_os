#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os

from empire_os.gtm_pipeline_worker import run_gtm_pipeline
from empire_os.qualification_worker_v2 import request_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()
    cap = int(os.getenv("EMPIRE_GTM_DAILY_EXTERNAL_CAP", "25"))
    result = run_gtm_pipeline(
        request_json,
        limit=args.limit,
        daily_cap=cap,
    )
    payload = result.as_dict()
    payload["ok"] = not payload["proposal_errors"]
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
