"""Omnichannel-style lifecycle graph over EXISTING tenant-scoped Revenue CRM reads.

This module never subscribes contacts, sends messages, schedules automation,
reads mail bodies, writes a database, or treats price/forecast as actual revenue.
It only projects canonical CRM view fields into review-only segments and journeys.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from uuid import UUID

SCHEMA = "empire.revenue_crm_omnichannel_journey_preview.v1"
STAGES = (
    "source_observed", "segment_review", "consent_suppression_gate",
    "conversation_review", "commercial_readiness_gate", "outcome_review",
    "recognized_revenue_proof",
)
CHANNELS = ("email", "sms", "web_push")
MAX_ROWS = 500
STATUS_EXCLUDE = {"suppressed", "unsubscribed", "opted_out", "do_not_contact", "bounced"}


def journey_blueprint() -> dict[str, Any]:
    """JSON graph suitable for a visual canvas; not a live workflow definition."""
    nodes = [
        {"id": "source_observed", "type": "source", "label": "Canonical CRM record"},
        {"id": "segment_review", "type": "segment", "label": "Observed lifecycle segment"},
        {"id": "consent_suppression_gate", "type": "decision", "label": "Consent + suppression + identity"},
        {"id": "conversation_review", "type": "review", "label": "Operator: next conversation step"},
        {"id": "commercial_readiness_gate", "type": "decision", "label": "Buyer + terms + routing authority"},
        {"id": "outcome_review", "type": "review", "label": "Fulfilment and outcome evidence"},
        {"id": "recognized_revenue_proof", "type": "evidence", "label": "Canonical recognized revenue proof"},
    ]
    return {
        "schema_version": "empire.revenue_crm_omnichannel_graph.v1",
        "mode": "OBSERVE",
        "design_editable": False,
        "execution_authority": "none",
        "visual_graph_ready": True,
        "actual_drag_drop_editor_built": True,
        "visual_editor_route": "/v1/revenue-crm/journeys/designer",
        "visual_editor_mode": "LOCAL_DESIGN_ONLY",
        "workflow_server_persistence": False,
        "nodes": nodes,
        "edges": [
            {"from": STAGES[i], "to": STAGES[i + 1], "condition": "evidence_review_only"}
            for i in range(len(STAGES) - 1)
        ],
        "supported_channels": [
            {"channel": channel, "send_enabled": False, "consent_verified": False,
             "suppression_checked": False}
            for channel in CHANNELS
        ],
        "triggers": ["canonical_conversation_state", "closer_case_state",
                     "fulfilment_state", "buyer_capacity_review"],
        "splits": ["evidence_missing", "observed_stage", "contact_suppressed",
                   "external_authority_pending"],
        "recovery_templates": ["engaged_conversation_review", "proposal_review",
                               "awaiting_payment_review", "fulfilment_review",
                               "stalled_conversation_review"],
        "outcome_source": "canonical_commercial_events_not_read_by_this_view",
        "outbound_enabled": False,
        "payment_enabled": False,
        "recognized_revenue_enabled": False,
    }


def _identifier(row: Mapping[str, Any], field: str) -> str:
    value = row.get(field)
    if isinstance(value, UUID):
        return str(value)
    if not isinstance(value, str) or len(value) > 256:
        return ""
    return value.strip()


def _timestamp(value: Any) -> datetime | None:
    # psycopg returns native datetimes; JSON/test readers may provide ISO.
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and len(value) <= 64:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else None


def _stage(row: Mapping[str, Any]) -> tuple[str, str, str | None]:
    """Always require a matching canonical object ID for state transitions."""
    fulfilment = _identifier(row, "fulfilment_state").lower()
    closer = _identifier(row, "closer_state").lower()
    conversation = _identifier(row, "conversation_state").lower()
    prospect_status = _identifier(row, "prospect_status").lower()
    if any(s in STATUS_EXCLUDE for s in (fulfilment, closer, conversation, prospect_status)):
        return "contact_hold", "OBSERVED_CONTACT_HOLD", None
    if _identifier(row, "fulfilment_order_id") and fulfilment in (
        "accepted", "invoiced", "delivered", "confirmed",
    ):
        return "fulfilment_review", "CANONICAL_FULFILMENT_OBSERVED", "fulfilment_order_id"
    if _identifier(row, "closer_case_id") and closer == "awaiting_payment":
        return "awaiting_payment_review", "CLOSER_PAYMENT_REVIEW", "closer_case_id"
    if _identifier(row, "closer_case_id") and closer == "proposal_ready":
        return "proposal_review", "CLOSER_PROPOSAL_REVIEW", "closer_case_id"
    if _identifier(row, "conversation_id") and conversation == "engaged":
        return "engaged_conversation_review", "ENGAGED_CONVERSATION", "conversation_id"
    return "unqualified_evidence_review", "NO_VERIFIED_LIFECYCLE_EVENT", None


def preview_crm_journey(
    row: Mapping[str, Any], *, now: datetime, next_action: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if now.tzinfo is None:
        raise ValueError("timezone-aware preview clock required")
    if not isinstance(row, Mapping):
        raise ValueError("canonical CRM row required")
    prospect = _identifier(row, "prospect_id")
    tenant = _identifier(row, "tenant_id")
    if not prospect or not tenant:
        raise ValueError("canonical tenant-scoped CRM identity required")
    segment, reason, supporting_id_key = _stage(row)
    refs = []
    if supporting_id_key:
        ref = _identifier(row, supporting_id_key)
        if not ref:
            raise ValueError("orphan stage identity")
        refs.append({"source": "canonical_revenue_crm_prospects",
                     "kind": supporting_id_key, "record_id": ref})
    stale_review = False
    latest = None
    for key in ("conversation_updated_at", "closer_updated_at", "fulfilment_updated_at"):
        dt = _timestamp(row.get(key))
        if dt is not None and (latest is None or dt > latest):
            latest = dt
    if segment == "engaged_conversation_review" and latest is not None:
        seconds = (now.astimezone(timezone.utc) - latest).total_seconds()
        stale_review = seconds >= 72 * 3600
    blockers = [
        "CHANNEL_CONSENT_NOT_PRESENT_IN_CRM_VIEW",
        "CANONICAL_SUPPRESSION_NOT_JOINED",
        "CHANNEL_DELIVERY_IDENTITY_NOT_VERIFIED",
        "SENDER_PROVIDER_NOT_VERIFIED",
        "FOUNDER_OUTBOUND_AUTHORITY_REQUIRED",
        "CANONICAL_REVENUE_LEDGER_NOT_JOINED",
    ]
    if segment == "contact_hold":
        blockers.append("OBSERVED_CONTACT_HOLD")
    if supporting_id_key is None and segment != "contact_hold":
        blockers.append("LIFECYCLE_EVIDENCE_NOT_BOUND")
    if stale_review:
        blockers.append("ENGAGED_CONVERSATION_OVER_72H_REVIEW_ONLY")
    candidate = (next_action or {}).get("action")
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE", "status": "REVIEW_ONLY",
        "tenant_id": tenant, "prospect_id": prospect,
        "segment": segment, "segment_reason": reason,
        "engaged_conversation_stale_candidate": stale_review,
        "evidence_refs": refs,
        "existing_crm_next_action": candidate if isinstance(candidate, str) else None,
        "operator_review_recommended": (
            segment not in ("contact_hold", "unqualified_evidence_review")
        ),
        "graph_stage_ids": list(STAGES),
        "blockers": sorted(set(blockers)),
        "channel_actions": {key: "BLOCKED_NO_SEND" for key in CHANNELS},
        "send_authorized": False, "followup_authorized": False,
        "payment_authorized": False, "crm_mutation": False,
        "observed_attribution_revenue_cents": None,
        "forecast_revenue_cents": None,
        "potential_price_cents_is_revenue": False,
        "revenue_attribution_state": "UNKNOWN_CANONICAL_LEDGER_NOT_READ",
        "execution_authority": "none",
    }


def preview_segment_distribution(
    rows: Sequence[Mapping[str, Any]], *, tenant_id: str, requested_limit: int = 100,
) -> dict[str, Any]:
    if (type(requested_limit) is not int or not 1 <= requested_limit <= MAX_ROWS
            or not isinstance(rows, (list, tuple))
            or not 0 <= len(rows) <= requested_limit):
        raise ValueError("bounded CRM prospect rows required")
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ValueError("authenticated CRM tenant required")
    counts: dict[str, int] = {}
    unique: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("canonical CRM prospect required")
        pid = _identifier(row, "prospect_id")
        bound = _identifier(row, "tenant_id")
        if not pid or not bound or bound != tenant_id or pid in unique:
            raise ValueError("duplicate, unbound or cross-tenant CRM prospect")
        unique.add(pid)
        label = _stage(row)[0]
        counts[label] = counts.get(label, 0) + 1
    return {
        "schema_version": "empire.revenue_crm_segment_distribution.v1",
        "mode": "OBSERVE", "read_only": True,
        "tenant_id": tenant_id, "observed_prospect_count": len(rows),
        "segments": [{"name": key, "count": counts[key]} for key in sorted(counts)],
        "page_may_be_partial": len(rows) == requested_limit,
        "complete_tenant_audience_verified": False,
        "subscribers_verified": False, "revenue_cents": None,
        "channel_consent_verified": False, "execution_authority": "none",
        "send_authorized": False,
    }
