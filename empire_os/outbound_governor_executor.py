"""Execution adapter for decisions emitted by the Phase 3E Outbound Governor."""
from __future__ import annotations

from typing import Any, Callable

from empire_os.outbound_provider import build_resend_send, send_with_resend


class OutboundGovernorExecutionError(RuntimeError):
    pass


def execute_governor_decision(
    decision: dict[str, Any],
    *,
    approver_rpc: Callable[[str, dict[str, Any]], Any] | None = None,
    sender_rpc: Callable[[str, dict[str, Any]], Any] | None = None,
    actor: str,
    sender: str | None = None,
    reply_to: str | None = None,
    resend_api_key: str | None = None,
    resend_module: Any | None = None,
) -> dict[str, Any]:
    """Execute one already-evaluated governor decision, fail-closed."""
    action = str(decision.get("decision") or "")
    intent_id = str(decision.get("intent_id") or "")
    mode = str(decision.get("mode") or "")
    if mode != "GUARDED_EXECUTE":
        raise OutboundGovernorExecutionError("GUARDED_EXECUTE decision required")
    if decision.get("mutation_authorized") is not True:
        raise OutboundGovernorExecutionError("mutation authorization required")
    if not intent_id or not actor:
        raise OutboundGovernorExecutionError("intent id and actor required")


    if action == "AUTO_APPROVE_ELIGIBLE":
        if approver_rpc is None:
            raise OutboundGovernorExecutionError("approver transport required")
        result = approver_rpc("approve_outbound_intent", {
            "p_intent_id": intent_id,
            "p_approved_by": actor,
            "p_note": "Approved automatically by Outbound Governor policy.",
        })
        return {
            "decision": "AUTO_APPROVED",
            "intent_id": intent_id,
            "result": result,
            "actual_revenue": False,
        }

    if action == "AUTO_SEND_ELIGIBLE":
        if sender_rpc is None:
            raise OutboundGovernorExecutionError("sender transport required")
        if not sender or not reply_to or not resend_api_key:
            raise OutboundGovernorExecutionError("sender provider configuration required")
        claim = sender_rpc("claim_outbound_send", {
            "p_intent_id": intent_id,
            "p_actor": actor,
        })
        payload = build_resend_send(claim, sender=sender, reply_to=reply_to)
        provider_message_id = send_with_resend(
            payload, api_key=resend_api_key, resend_module=resend_module
        )
        result = sender_rpc("record_outbound_delivery", {
            "p_intent_id": intent_id,
            "p_event_type": "sent",
            "p_actor": actor,
            "p_provider_message_id": provider_message_id,
            "p_payload": {"provider": "resend", "governor": True},
        })
        return {
            "decision": "AUTO_SENT",
            "intent_id": intent_id,
            "provider_message_id": provider_message_id,
            "result": result,
            "actual_revenue": False,
        }

    raise OutboundGovernorExecutionError(f"non-executable governor action: {action}")
