#!/usr/bin/env python3
"""Manual governed email sender for Phase 3E. Defaults to review-only."""
from __future__ import annotations

import argparse
import json
import os
import sys

from empire_os.outbound_provider import (
    OutboundProviderError,
    build_resend_send,
    send_with_resend,
)
from empire_os.outbound_role_transport import PostgresOutboundRpc


def parser():
    p = argparse.ArgumentParser(description="Empire governed outbound email tool")
    p.add_argument("intent_id")
    p.add_argument("--actor", default=os.getenv("EMPIRE_OPERATOR_ID", ""))
    p.add_argument("--sender", default=os.getenv("EMPIRE_OUTBOUND_FROM", ""))
    p.add_argument("--reply-to", default=os.getenv("EMPIRE_REPLY_TO", ""))
    p.add_argument("--send", action="store_true", help="actually send after DB authorization")
    return p


def emit(value):
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def main(argv=None):
    args = parser().parse_args(argv)
    dsn = os.getenv("EMPIRE_OUTBOUND_SENDER_DSN", "").strip()
    if not dsn:
        raise OutboundProviderError("EMPIRE_OUTBOUND_SENDER_DSN is required")
    rpc = PostgresOutboundRpc(dsn, "empire_outbound_sender")
    review = rpc("get_outbound_intent_review", {"p_intent_id": args.intent_id})
    if not args.send:
        emit({"decision":"review_only","review":review,
              "next_gate":"rerun with --send after operator review"})
        return 0
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    claim = rpc("claim_outbound_send", {
        "p_intent_id": args.intent_id, "p_actor": args.actor,
    })
    payload = build_resend_send(claim, sender=args.sender, reply_to=args.reply_to)
    provider_message_id = send_with_resend(payload, api_key=api_key)
    result = rpc("record_outbound_delivery", {
        "p_intent_id": args.intent_id, "p_event_type":"sent",
        "p_actor":args.actor, "p_provider_message_id":provider_message_id,
        "p_payload":{"provider":"resend"},
    })
    emit({"review":review,"provider_message_id":provider_message_id,"result":result})
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except OutboundProviderError as exc:
        print(json.dumps({"ok":False,"error":str(exc)}), file=sys.stderr)
        raise SystemExit(2)
