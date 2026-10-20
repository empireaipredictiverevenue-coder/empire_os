"""Idempotent, supervised OFFLINE calendar evidence projection.

Calendar read-backs are persisted in the owner-bound registry first, then
replayed to independent local recovery and workflow stores. A crash between
target writes is safe to retry: both stores reject changed duplicate event IDs.
This is at-least-once delivery, NOT a distributed atomic transaction.

No Google API, payment, messaging, phone or booking operations happen here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from empire_os.inbound_booking_store import OfflineBookingWorkflowStore
from empire_os.inbound_calendar_registry import OfflineCalendarRegistry
from empire_os.inbound_google_calendar_adapter import (
    calendar_proof_to_recovery_event,
    calendar_proof_to_workflow_event,
)
from empire_os.inbound_recovery_store import OfflineRecoveryStore


@dataclass(frozen=True)
class CalendarProjectionResult:
    tenant_id: str
    examined: int
    acknowledged: int
    recovery_events_added: int
    workflow_events_added: int
    remaining_pending: int
    mode: str = "supervised_local_evidence_projection_only"
    live_calendar_writes: bool = False
    messages_sent: bool = False
    revenue_inferred: bool = False


def project_calendar_evidence_offline(
    *,
    registry: OfflineCalendarRegistry,
    recovery: OfflineRecoveryStore,
    workflow: OfflineBookingWorkflowStore,
    tenant_id: str,
    as_of: datetime,
    limit: int = 100,
) -> CalendarProjectionResult:
    """Requires explicit operator invocation and writable *local* stores.

    Projection acknowledgement happens only after *both* target stores
    accept the same immutable proof. No new provider claims are minted.
    """
    if (registry.read_only or recovery.read_only or workflow.read_only):
        raise ValueError("projection_requires_explicit_writable_offline_stores")
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ValueError("tenant_id_required")
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("projection_time_must_be_aware")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ValueError("invalid_projection_batch_limit")

    proofs = registry.pending_projection_proofs(tenant_id, limit=limit)
    acknowledged = recovery_added = workflow_added = 0
    for proof in proofs:
        if datetime.fromisoformat(proof.observed_at.replace("Z", "+00:00")) > as_of:
            # Do not claim future calendar observations were processed.
            continue
        link = registry.get_link(
            calendar_id=proof.calendar_id, event_id=proof.appointment_id,
        )
        if (link is None or link.tenant_id != tenant_id
            or link.call_id != proof.call_id):
            raise ValueError("calendar_projection_link_not_trusted")
        canonical_recovery = calendar_proof_to_recovery_event(proof)
        canonical_workflow = calendar_proof_to_workflow_event(
            proof, contact_key=link.contact_key,
        )
        if canonical_recovery.tenant_id != tenant_id or canonical_workflow.tenant_id != tenant_id:
            raise ValueError("calendar_projection_cross_tenant")
        added_recovery = recovery.append_offline(canonical_recovery)
        # Failure here leaves the earlier recovery evidence in place;
        # the registry remains pending and a replay safely resumes.
        added_workflow = workflow.append_offline(canonical_workflow)
        registry.acknowledge_projection_offline(proof, projected_at=as_of)
        recovery_added += int(added_recovery)
        workflow_added += int(added_workflow)
        acknowledged += 1

    return CalendarProjectionResult(
        tenant_id=tenant_id, examined=len(proofs), acknowledged=acknowledged,
        recovery_events_added=recovery_added,
        workflow_events_added=workflow_added,
        remaining_pending=registry.projection_counts(tenant_id)["pending"],
    )
