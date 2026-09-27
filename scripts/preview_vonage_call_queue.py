#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.vonage_call_transport import (
    VonageCallConfig,
    VonageCallTransport,
)

CALL_PLANS = Path(
    "/srv/empire_os/runtime/closer/call_plans_latest.json"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    try:
        payload = json.loads(CALL_PLANS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    plans = payload.get("plans") if isinstance(payload, dict) else []
    if not isinstance(plans, list):
        plans = []

    config = VonageCallConfig.from_env()
    transport = VonageCallTransport(config)
    previews = [
        transport.preview(plan)
        for plan in plans[: max(1, min(int(args.limit), 25))]
        if isinstance(plan, dict)
    ]
    print(json.dumps({
        "provider": "vonage",
        "queue_count": len(plans),
        "readiness": config.readiness(),
        "previews": previews,
        "live_calls_placed": 0,
        "execution_allowed": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
