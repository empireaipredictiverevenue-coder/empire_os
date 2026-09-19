#!/usr/bin/env python3
"""Review a governed outbound intent and emit the next safe EmpireOS action."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from empire_os.outbound_governor import OutboundGovernorPolicy, evaluate_outbound
from empire_os.outbound_provider import OutboundProviderError
from empire_os.outbound_role_transport import PostgresOutboundRpc


def _context(path: str | None) -> dict:
    if not path:
        return {}
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict):
        raise ValueError("context JSON object required")
    return value


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Empire Phase 3E outbound governor")
    p.add_argument("intent_id", nargs="?")
    p.add_argument("--context-json")
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--mode", choices=("OBSERVE", "ASSIST", "GUARDED_EXECUTE"),
                   default=os.getenv("EMPIRE_OUTBOUND_GOVERNOR_MODE", "OBSERVE"))
    p.add_argument("--auto-approve", action="store_true")
    p.add_argument("--auto-send", action="store_true")
    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    dsn = os.getenv("EMPIRE_OUTBOUND_SENDER_DSN", "").strip()
    if not dsn:
        raise OutboundProviderError("EMPIRE_OUTBOUND_SENDER_DSN is required")

    rpc = PostgresOutboundRpc(dsn, "empire_outbound_sender")
    policy = OutboundGovernorPolicy(
        mode=args.mode,
        allow_auto_approval=args.auto_approve,
        allow_auto_send=args.auto_send,
    )

    intent_ids = [args.intent_id] if args.intent_id else [
        item["intent_id"] for item in rpc(
            "list_outbound_governor_work", {"p_limit": args.limit}
        )
    ]
    results = []
    override_context = _context(args.context_json) if args.context_json else None
    for intent_id in intent_ids:
        review = rpc("get_outbound_intent_review", {"p_intent_id": intent_id})
        context = (
            override_context
            if override_context is not None
            else rpc("get_outbound_governor_context", {"p_intent_id": intent_id})
        )
        results.append(evaluate_outbound(review, context, policy=policy))

    output = results[0] if args.intent_id and results else {
        "decision": "BATCH_REVIEW",
        "mode": policy.mode,
        "count": len(results),
        "results": results,
    }
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OutboundProviderError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        raise SystemExit(2)
