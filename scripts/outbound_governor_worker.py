#!/usr/bin/env python3
"""Bounded Phase 3E Outbound Governor worker.

OBSERVE is the default. Mutations require GUARDED_EXECUTE plus explicit
auto-approval/auto-send flags and the matching dedicated role credentials.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from empire_os.outbound_governor import OutboundGovernorPolicy, evaluate_outbound
from empire_os.outbound_governor_executor import (
    OutboundGovernorExecutionError,
    execute_governor_decision,
)
from empire_os.outbound_provider import OutboundProviderError
from empire_os.outbound_role_transport import (
    PostgresOutboundRpc,
    SupabaseOutboundRpc,
    SupabaseStandingAuthorityApproverRpc,
)


def _bool_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Empire outbound governor worker")
    p.add_argument("--limit", type=int, default=25)
    p.add_argument(
        "--mode",
        choices=("OBSERVE", "ASSIST", "GUARDED_EXECUTE"),
        default=os.getenv("EMPIRE_OUTBOUND_GOVERNOR_MODE", "OBSERVE"),
    )
    p.add_argument("--execute", action="store_true")
    return p


def _provider_ready() -> bool:
    return all([
        os.getenv("RESEND_API_KEY", "").strip(),
        os.getenv("EMPIRE_OUTBOUND_FROM", "").strip(),
        os.getenv("EMPIRE_REPLY_TO", "").strip(),
    ])


def _sender_rpc():
    dsn = os.getenv("EMPIRE_OUTBOUND_SENDER_DSN", "").strip()
    if dsn:
        try:
            return PostgresOutboundRpc(
                dsn,
                "empire_outbound_sender",
            )
        except OutboundProviderError as exc:
            # Dedicated role transport is preferred, but a missing local
            # psycopg driver must not take the governed sender offline. The
            # Supabase bridge exposes the same narrow RPC allowlist and keeps
            # database policy as the authority boundary.
            if "psycopg is required" not in str(exc):
                raise
    return SupabaseOutboundRpc("empire_outbound_sender")


def _approver_rpc():
    dsn = os.getenv("EMPIRE_OUTBOUND_APPROVER_DSN", "").strip()
    if dsn:
        try:
            return PostgresOutboundRpc(dsn, "empire_outbound_approver")
        except OutboundProviderError as exc:
            if "psycopg is required" not in str(exc):
                raise
    cap = int(os.getenv("EMPIRE_GTM_DAILY_EXTERNAL_CAP", "10"))
    return SupabaseStandingAuthorityApproverRpc(daily_cap=cap)


def _evaluate(
    sender_rpc: PostgresOutboundRpc,
    intent_id: str,
    policy: OutboundGovernorPolicy,
) -> dict:
    review = sender_rpc("get_outbound_intent_review", {"p_intent_id": intent_id})
    context = sender_rpc(
        "get_outbound_governor_context", {"p_intent_id": intent_id}
    )
    context = {**dict(context or {}), "provider_ready": _provider_ready()}
    return evaluate_outbound(review, context, policy=policy)


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    auto_approve = _bool_env("EMPIRE_OUTBOUND_AUTO_APPROVE")
    auto_send = _bool_env("EMPIRE_OUTBOUND_AUTO_SEND")
    policy = OutboundGovernorPolicy(
        mode=args.mode,
        allow_auto_approval=auto_approve,
        allow_auto_send=auto_send,
    )
    sender_rpc = _sender_rpc()
    work = sender_rpc("list_outbound_governor_work", {"p_limit": args.limit})
    results = []

    approver_rpc = None
    if args.execute and auto_approve and args.mode == "GUARDED_EXECUTE":
        approver_rpc = _approver_rpc()

    # Already-approved sends are the most actionable work. Process them before
    # pending approvals so a policy-rejected approval can never starve the send
    # queue.
    work = sorted(
        work,
        key=lambda item: (
            0 if str(item.get("status") or "") == "approved" else 1,
            str(item.get("updated_at") or ""),
            str(item.get("intent_id") or ""),
        ),
    )

    fatal_errors = 0
    for item in work:
        intent_id = str(item["intent_id"])
        record = {"intent_id": intent_id}
        try:
            decision = _evaluate(sender_rpc, intent_id, policy)
            record["evaluation"] = decision

            executable_actions = {"AUTO_APPROVE_ELIGIBLE", "AUTO_SEND_ELIGIBLE"}
            if (
                args.execute
                and decision.get("mutation_authorized") is True
                and decision.get("decision") in executable_actions
            ):
                try:
                    execution = execute_governor_decision(
                        decision,
                        approver_rpc=approver_rpc,
                        sender_rpc=sender_rpc,
                        actor=os.getenv("EMPIRE_OPERATOR_ID", "outbound_governor"),
                        sender=os.getenv("EMPIRE_OUTBOUND_FROM", "").strip() or None,
                        reply_to=os.getenv("EMPIRE_REPLY_TO", "").strip() or None,
                        resend_api_key=os.getenv("RESEND_API_KEY", "").strip() or None,
                    )
                    record["execution"] = execution
                except RuntimeError as exc:
                    message = str(exc)
                    if (
                        decision.get("decision") == "AUTO_APPROVE_ELIGIBLE"
                        and "existing outbound history requires explicit review"
                        in message
                    ):
                        record["execution_blocked"] = {
                            "reason": "existing_outbound_history_requires_explicit_review",
                            "nonfatal": True,
                        }
                        results.append(record)
                        continue
                    raise

                if execution["decision"] == "AUTO_APPROVED" and auto_send:
                    after = _evaluate(sender_rpc, intent_id, policy)
                    record["post_approval_evaluation"] = after
                    if after.get("decision") == "AUTO_SEND_ELIGIBLE":
                        record["send_execution"] = execute_governor_decision(
                            after,
                            sender_rpc=sender_rpc,
                            actor=os.getenv(
                                "EMPIRE_OPERATOR_ID", "outbound_governor"
                            ),
                            sender=os.getenv("EMPIRE_OUTBOUND_FROM", "").strip(),
                            reply_to=os.getenv("EMPIRE_REPLY_TO", "").strip(),
                            resend_api_key=os.getenv("RESEND_API_KEY", "").strip(),
                        )
            elif args.execute and decision.get("decision") == "AUTO_REPAIR":
                record["execution_deferred"] = (
                    "deterministic repair adapter not yet enabled"
                )
        except Exception as exc:
            fatal_errors += 1
            record["execution_error"] = {
                "type": type(exc).__name__,
                "message": str(exc)[:500],
            }
        results.append(record)

    print(json.dumps({
        "decision": "WORKER_CYCLE",
        "mode": policy.mode,
        "execute": bool(args.execute),
        "count": len(results),
        "fatal_error_count": fatal_errors,
        "results": results,
    }, indent=2, sort_keys=True, default=str))
    return 2 if fatal_errors else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OutboundProviderError, OutboundGovernorExecutionError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        raise SystemExit(2)
