#!/usr/bin/env python3
"""One-shot operator path for an approved individual EmpireDB email intent.

Never a campaign worker. Read-only review by default; explicit double consent
and current canonical DB evidence are needed for any future send. No sending
is performed when inspecting this script or running the default invocation.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from typing import Any

from empire_os.outbound_governor import OutboundGovernorPolicy, evaluate_outbound
from empire_os.outbound_governor_executor import execute_governor_decision, OutboundGovernorExecutionError
from empire_os.outbound_role_transport import PostgresOutboundRpc
from empire_os.outbound_email_transport import GovernedGmailEmailTransport

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$")
SENDER = "Phil - Founder - Empire AI <phil@mail.empire-ai.co.uk>"
REPLY_TO = "reply@mail.empire-ai.co.uk"
TOKEN_FILE = "/srv/empire_os/runtime/secrets/google-workspace-internal-token.json"


def policy_review(review: dict[str, Any], context: dict[str, Any],
                  *, recipient: str, execution_requested: bool = False) -> dict[str, Any]:
    """Pure gate: no automated approval, no campaigns, no inferred buyer route."""
    if not isinstance(review, dict) or not isinstance(context, dict):
        raise ValueError("CANONICAL_REVIEW_AND_CONTEXT_REQUIRED")
    if (str(review.get("recipient") or "").strip().casefold()
            != str(recipient or "").strip().casefold()):
        raise ValueError("EXACT_RECIPIENT_NOT_MATCHED_TO_CANONICAL_INTENT")
    if review.get("status") != "approved" or review.get("actual_revenue") is not False:
        raise ValueError("CANONICAL_APPROVED_ONE_TO_ONE_INTENT_REQUIRED")
    if context.get("suppressed") is not False:
        raise ValueError("EXACT_RECIPIENT_SUPPRESSION_UNVERIFIED")
    required = ("review_ready", "outreach_ready", "bound_to_decision_maker")
    if any(context.get(flag) is not True for flag in required):
        raise ValueError("VERIFIED_PERSON_BOUND_OUTREACH_REQUIRED")
    if execution_requested and context.get("provider_ready") is not True:
        raise ValueError("PROFESSIONAL_GMAIL_TRANSPORT_NOT_VERIFIED")
    return evaluate_outbound(
        review, context,
        policy=OutboundGovernorPolicy(
            mode="GUARDED_EXECUTE" if execution_requested else "OBSERVE",
            allow_auto_approval=False,
            allow_auto_send=execution_requested,
        ),
    )


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Founder one-recipient Gmail; no send by default")
    p.add_argument("--intent-id", required=True)
    p.add_argument("--recipient", required=True)
    p.add_argument("--send", action="store_true")
    p.add_argument("--confirm-approved-intent-id")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    sent = False
    result: dict[str, Any] = {
        "schema_version": "empire.founder.one_to_one_gmail.v1",
        "mode": "HELD", "message_sent": False,
        "new_approvals_created": False,
        "automatic_campaigns_enabled": False,
    }
    try:
        if not UUID_RE.fullmatch(args.intent_id):
            raise ValueError("INVALID_CANONICAL_INTENT_ID")
        if not isinstance(args.recipient, str) or args.recipient.count("@") != 1:
            raise ValueError("INVALID_EXACT_RECIPIENT")
        if args.send and (
            args.confirm_approved_intent_id != args.intent_id
            or os.getenv("EMPIRE_FOUNDER_MANUAL_GMAIL_RELEASE") != "APPROVED_ONE_TO_ONE_ONLY"
        ):
            raise ValueError("EXPLICIT_FOUNDER_SINGLE_INTENT_RELEASE_REQUIRED")
        dsn = os.getenv("EMPIRE_OUTBOUND_SENDER_DSN", "").strip()
        if not dsn:
            raise ValueError("DEDICATED_CANONICAL_OUTBOUND_SENDER_UNAVAILABLE")
        rpc = PostgresOutboundRpc(dsn, "empire_outbound_sender")
        review = rpc("get_outbound_intent_review", {"p_intent_id": args.intent_id})
        context = rpc("get_outbound_governor_context", {"p_intent_id": args.intent_id})
        if not isinstance(context, dict):
            raise ValueError("CANONICAL_OUTBOUND_CONTEXT_UNAVAILABLE")
        # Read-only review never assumes a provider is live or permits writes.
        # Real execution must separately check the dedicated durable Gmail token.
        provider_ok = False
        if args.send:
            from empire_os.gmail_api_transport import load_gmail_credentials
            credentials = load_gmail_credentials(TOKEN_FILE)
            provider_ok = bool(credentials.valid)
        context = {**context, "provider_ready": provider_ok}
        decision = policy_review(review, context, recipient=args.recipient,
                                 execution_requested=args.send)
        result["mode"] = "REVIEW_ONLY" if not args.send else "HELD"
        result["governor_decision"] = decision["decision"]
        if not args.send:
            return _print(result, 0)
        if (decision.get("decision") != "AUTO_SEND_ELIGIBLE"
                or decision.get("mutation_authorized") is not True):
            raise ValueError("CURRENT_CANONICAL_SEND_GATES_DENIED")
        transport = GovernedGmailEmailTransport(token_file=TOKEN_FILE)
        outcome = execute_governor_decision(
            decision, sender_rpc=rpc, actor="founder_manual_one_to_one",
            sender=SENDER, reply_to=REPLY_TO,
            email_transport=transport,
        )
        sent = outcome.get("decision") == "AUTO_SENT"
        result["message_sent"] = sent
        result["mode"] = "PROVIDER_ACCEPTED" if sent else "RECONCILIATION_REQUIRED"
        return _print(result, 0 if sent else 2)
    except Exception as exc:
        if isinstance(exc, OutboundGovernorExecutionError) and "reconciliation required" in str(exc).lower():
            # Provider may have accepted an attempt; a retry is not safe.
            result["mode"] = "RECONCILIATION_REQUIRED"
        # Sanitize: never echo database credentials, email text, person or DSN.
        result["reason_code"] = (
            str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        )[:90]
        return _print(result, 2)


def _print(value: dict[str, Any], exit_code: int) -> int:
    print(json.dumps(value, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
