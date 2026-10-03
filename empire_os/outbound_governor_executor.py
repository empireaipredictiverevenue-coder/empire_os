"""Execution adapter for decisions emitted by the Phase 3E Outbound Governor."""
from __future__ import annotations

from typing import Any, Callable

from empire_os.outbound_email_transport import (
    OutboundEmailTransport,
    ResendEmailTransport,
)
from empire_os.outbound_provider import OutboundProviderError, build_resend_send


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
    email_transport: OutboundEmailTransport | None = None,
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
        if not sender or not reply_to:
            raise OutboundGovernorExecutionError("sender provider configuration required")

        transport = email_transport
        if transport is None:
            if not resend_api_key:
                raise OutboundGovernorExecutionError(
                    "sender provider configuration required"
                )
            transport = ResendEmailTransport(
                api_key=resend_api_key,
                resend_module=resend_module,
            )

        provider = str(getattr(transport, "provider", "") or "").strip().lower()
        if not provider or not callable(getattr(transport, "send", None)):
            raise OutboundGovernorExecutionError("valid email transport required")

        claim = sender_rpc("claim_outbound_send", {
            "p_intent_id": intent_id,
            "p_actor": actor,
        })
        payload = build_resend_send(claim, sender=sender, reply_to=reply_to)
        try:
            provider_message_id = transport.send(payload)
        except OutboundProviderError as exc:
            try:
                sender_rpc("record_outbound_delivery", {
                    "p_intent_id": intent_id,
                    "p_event_type": "reconciliation_required",
                    "p_actor": actor,
                    "p_provider_message_id": "",
                    "p_payload": {
                        "provider": provider,
                        "governor": True,
                        "provider_outcome": "unknown",
                        "error_type": type(exc).__name__,
                    },
                })
            except Exception as record_exc:
                raise OutboundGovernorExecutionError(
                    "provider outcome unknown and reconciliation record failed"
                ) from record_exc
            raise OutboundGovernorExecutionError(
                "provider outcome unknown; reconciliation required"
            ) from exc

        result = sender_rpc("record_outbound_delivery", {
            "p_intent_id": intent_id,
            "p_event_type": "sent",
            "p_actor": actor,
            "p_provider_message_id": provider_message_id,
            "p_payload": {"provider": provider, "governor": True},
        })
        return {
            "decision": "AUTO_SENT",
            "intent_id": intent_id,
            "provider_message_id": provider_message_id,
            "result": result,
            "actual_revenue": False,
        }

    raise OutboundGovernorExecutionError(f"non-executable governor action: {action}")
