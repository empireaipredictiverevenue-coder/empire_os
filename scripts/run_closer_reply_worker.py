#!/usr/bin/env python3
"""Run the bounded reply-to-closer handoff using the service-role RPC bridge."""
from __future__ import annotations

import argparse
import json

from empire_os.closer_reply_worker import run_closer_reply_worker
from empire_os.closer_role_transport import SupabaseCloserRpc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    rpc = SupabaseCloserRpc("empire_closer_planner")
    result = run_closer_reply_worker(rpc, limit=args.limit)
    payload = result.as_dict()
    payload["ok"] = not payload["errors"]
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
