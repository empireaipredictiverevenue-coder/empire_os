#!/usr/bin/env python3
"""Phase 3F evidence-backed revenue recognition worker."""
from __future__ import annotations

import argparse
import json
import os
import sys
from uuid import UUID

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


def _verified_cost_ready(
    order_id: str, price_cents: object, document: object
) -> bool:
    """Mirror the existing DB actual-cost and positive-margin prerequisites.

    The authoritative database still rechecks all evidence atomically.
    Missing/malformed cost evidence MUST NOT be called READY, even when a
    blockchain payment amount matches the order's estimated sales price.
    """
    try:
        if str(UUID(order_id)) != order_id:
            return False
    except (TypeError, ValueError, AttributeError):
        return False
    if type(price_cents) is not int or price_cents <= 0:
        return False
    if (not isinstance(document, dict)
            or document.get("fulfilment_order_id") != order_id
            or document.get("actual_cost_ready") is not True):
        return False
    total = 0
    for name in ("acquisition_cost", "fulfilment_cost"):
        cost = document.get(name)
        if not isinstance(cost, dict):
            return False
        amount = cost.get("amount_cents")
        if (type(amount) is not int or amount < 0
                or cost.get("source_type") not in ("provider_invoice", "internal_actual")
                or not isinstance(cost.get("source_reference"), str)
                or not cost["source_reference"].strip()
                or not cost.get("evidence_id")):
            return False
        total += amount
    return total < price_cents


def _classify_work(item: object, rpc) -> dict:
    """A read-only gate for the existing revenue worker, not a new authority."""
    if not isinstance(item, dict):
        raise OutcomeTransportError("invalid revenue work row")
    order_id = str(item.get("fulfilment_order_id") or "")
    try:
        if str(UUID(order_id)) != order_id:
            raise ValueError("invalid")
    except (TypeError, ValueError, AttributeError):
        raise OutcomeTransportError("invalid revenue work identity") from None
    evidence_present = (
        item.get("direct_evidence") is True or
        item.get("escrow_release") is True
    )
    amount_matches = item.get("amount_matches") is True
    result = {
        "fulfilment_order_id": order_id,
        "amount_matches": amount_matches,
        "actual_cost_evidence_ready": False,
        "decision": "HOLD_AMOUNT_MISMATCH",
    }
    if not evidence_present or not amount_matches:
        return result
    try:
        costs = rpc("get_verified_actual_cost_evidence", {
            "p_fulfilment_order_id": order_id,
        })
    except OutcomeTransportError:
        result["decision"] = "HOLD_ACTUAL_COST_LOOKUP_UNAVAILABLE"
        return result
    ready = _verified_cost_ready(order_id, item.get("price_cents"), costs)
    result["actual_cost_evidence_ready"] = ready
    result["decision"] = "READY" if ready else "HOLD_ACTUAL_COST_EVIDENCE"
    return result


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

    if not isinstance(work, list):
        raise OutcomeTransportError("invalid revenue work queue")
    results = []
    for item in work:
        record = _classify_work(item, rpc)
        # An explicit execution flag NEVER overrides missing actual-cost
        # evidence. The canonical SQL independently repeats this guard.
        if (
            args.execute
            and args.mode == "GUARDED_EXECUTE"
            and record["decision"] == "READY"
        ):
            try:
                record["execution"] = rpc(
                    "recognize_bsc_revenue",
                    {
                        "p_fulfilment_order_id": record["fulfilment_order_id"],
                        "p_actor": actor,
                    },
                )
            except OutcomeTransportError:
                record["decision"] = "EXECUTION_ERROR"
                record["error"] = "dedicated_outcome_rpc_failed"
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
