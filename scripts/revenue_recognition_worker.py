#!/usr/bin/env python3
"""Phase 3F evidence-backed revenue recognition worker."""
from __future__ import annotations

import argparse
import json
import os
import sys

from empire_os.outcome_role_transport import (
    OutcomeTransportError,
    PostgresOutcomeRpc,
)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Empire Phase 3F revenue worker")
    p.add_argument("--limit", type=int, default=25)
    p.add_argument(
        "--mode",
        choices=("OBSERVE", "GUARDED_EXECUTE"),
        default=os.getenv("EMPIRE_REVENUE_RECOGNITION_MODE", "OBSERVE"),
    )
    p.add_argument("--execute", action="store_true")
    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    dsn = os.getenv("EMPIRE_REVENUE_RECOGNIZER_DSN", "").strip()
    if not dsn:
        raise OutcomeTransportError(
            "EMPIRE_REVENUE_RECOGNIZER_DSN is required"
        )

    rpc = PostgresOutcomeRpc(dsn, "empire_revenue_recognizer")
    work = rpc("list_revenue_recognition_work", {"p_limit": args.limit})
    actor = os.getenv(
        "EMPIRE_REVENUE_RECOGNITION_ACTOR", "revenue_recognition_worker"
    ).strip() or "revenue_recognition_worker"

    results = []
    for item in work:
        order_id = str(item.get("fulfilment_order_id") or "")
        record = {
            "fulfilment_order_id": order_id,
            "amount_matches": bool(item.get("amount_matches")),
            "decision": "READY" if item.get("amount_matches") else "HOLD_AMOUNT_MISMATCH",
        }

        if (
            args.execute
            and args.mode == "GUARDED_EXECUTE"
            and item.get("amount_matches") is True
        ):
            try:
                record["execution"] = rpc(
                    "recognize_bsc_revenue",
                    {
                        "p_fulfilment_order_id": order_id,
                        "p_actor": actor,
                    },
                )
            except OutcomeTransportError as exc:
                record["decision"] = "EXECUTION_ERROR"
                record["error"] = str(exc)
        results.append(record)

    print(json.dumps({
        "decision": "REVENUE_RECOGNITION_CYCLE",
        "mode": args.mode,
        "execute": bool(args.execute),
        "count": len(results),
        "results": results,
    }, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OutcomeTransportError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        raise SystemExit(2)
