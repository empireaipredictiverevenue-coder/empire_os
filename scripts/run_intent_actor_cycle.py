#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.revenue_actor_queue import (
    actor_queue_snapshot,
    process_actor_queue,
)
from empire_os.signal_intent_actor_router import (
    route_signal_inbox,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--signal-inbox",
        required=True,
    )
    parser.add_argument(
        "--queue",
        required=True,
    )
    parser.add_argument(
        "--lock",
        required=True,
    )
    parser.add_argument(
        "--route-limit",
        type=int,
        default=25,
    )
    parser.add_argument(
        "--process-limit",
        type=int,
        default=25,
    )
    args = parser.parse_args()

    signal_path = Path(args.signal_inbox)
    queue = Path(args.queue)
    lock = Path(args.lock)

    signals = json.loads(
        signal_path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(signals, dict):
        raise ValueError(
            "signal inbox must be an object"
        )

    routed = route_signal_inbox(
        signals,
        queue=queue,
        lock=lock,
        limit=args.route_limit,
    )

    processed = process_actor_queue(
        limit=args.process_limit,
        queue=queue,
        lock=lock,
    )

    snapshot = actor_queue_snapshot(queue)

    print(json.dumps({
        "schema_version":
            "empire.intent_actor_cycle.v1",
        "mode": "OBSERVE",
        "routing": routed,
        "processing": processed,
        "queue": snapshot,
        "outbound_sent": False,
        "canonical_promotion_performed":
            False,
        "payment_mutation": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }, indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
