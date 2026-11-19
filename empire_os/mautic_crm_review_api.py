"""Opt-in authenticated Smart CRM inbox reader for verified Mautic reviews.

Uses the *existing* CRM tenant-authenticated dedicated Postgres reader and
its session_user / RLS boundary. No new login, public endpoint, workflow,
sender, or other CRM is created. This router is NOT mounted by default.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Mapping
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from empire_os.revenue_crm_api import AuthenticatedRevenueCrmRead
from empire_os.revenue_crm_transport import (
    PostgresRevenueCrmRepository, RevenueCrmTransportError,
)
from empire_os.mautic_crm_inbox import (
    ALLOWED_EVENTS, ALLOWED_SIGNALS, ALLOWED_STAGES,
    ALLOWED_TIMESTAMP_STATES, DIGEST, SOURCE,
)

INBOX_SELECT_SQL = (
    "SELECT tenant_id,source_id,event_evidence_hmac,prospect_id,"
    "source_event,review_signal,timestamp_state,journey_segment,"
    "review_state,received_at FROM public.empire_crm_mautic_event_inbox "
    "WHERE tenant_id=%s::uuid ORDER BY received_at DESC,"
    "event_evidence_hmac ASC LIMIT %s"
)
_COLUMNS = frozenset({
    "tenant_id", "source_id", "event_evidence_hmac", "prospect_id",
    "source_event", "review_signal", "timestamp_state", "journey_segment",
    "review_state", "received_at",
})


def create_mautic_crm_review_router(
    *,
    resolve_authenticated_read: Callable[
        [Request], AuthenticatedRevenueCrmRead | None
    ],
) -> APIRouter:
    """Attach only to the existing founder-approved, authenticated CRM app."""
    if not callable(resolve_authenticated_read):
        raise ValueError("authenticated canonical CRM resolver required")
    router = APIRouter(prefix="/v1/revenue-crm/integrations/mautic")

    @router.get("/inbox/reviews")
    def list_mautic_inbox_reviews(
        request: Request,
        limit: int = Query(default=25, ge=1, le=100),
    ) -> dict[str, Any]:
        try:
            access = resolve_authenticated_read(request)
        except Exception:
            raise HTTPException(
                status_code=503, detail="authenticated_crm_read_unavailable",
            ) from None
        if access is None:
            raise HTTPException(
                status_code=401, detail="authenticated_crm_scope_required",
            )
        if (
            not isinstance(access, AuthenticatedRevenueCrmRead)
            or not isinstance(access.repository, PostgresRevenueCrmRepository)
            or access.tenant_id != access.repository.tenant_id
        ):
            raise HTTPException(
                status_code=503, detail="authenticated_crm_read_unavailable",
            )

        try:
            tenant = str(UUID(access.tenant_id))
            # Reuse the existing canonical tenant-scoped read transport.
            # That transport executes SET TRANSACTION READ ONLY,
            # SET LOCAL ROLE empire_revenue_crm_reader, verifies the
            # database-bound tenant, then rejects mismatched rows.
            records = access.repository._fetch_all(
                INBOX_SELECT_SQL, (tenant, limit)
            )
            output: list[dict[str, Any]] = []
            for row in records:
                if not isinstance(row, Mapping) or set(row) != _COLUMNS:
                    raise ValueError("unexpected canonical inbox fields")
                if (
                    str(row["tenant_id"]) != tenant
                    or not isinstance(row["source_id"], str)
                    or not SOURCE.fullmatch(row["source_id"])
                    or not isinstance(row["event_evidence_hmac"], str)
                    or not DIGEST.fullmatch(row["event_evidence_hmac"])
                    or not isinstance(row["source_event"], str)
                    or row["source_event"] not in ALLOWED_EVENTS
                    or not isinstance(row["review_signal"], str)
                    or row["review_signal"] not in ALLOWED_SIGNALS
                    or not isinstance(row["timestamp_state"], str)
                    or row["timestamp_state"] not in ALLOWED_TIMESTAMP_STATES
                    or not isinstance(row["journey_segment"], str)
                    or row["journey_segment"] not in ALLOWED_STAGES
                    or row["review_state"] != "REVIEW_ONLY"
                    or not isinstance(row["received_at"], datetime)
                    or row["received_at"].tzinfo is None
                ):
                    raise ValueError("invalid or cross-tenant inbox result")
                prospect_id = str(UUID(str(row["prospect_id"])))
                output.append({
                    "source_id": row["source_id"],
                    "event_evidence_hmac": row["event_evidence_hmac"],
                    "prospect_id": prospect_id,
                    "source_event": row["source_event"],
                    "review_signal": row["review_signal"],
                    "timestamp_state": row["timestamp_state"],
                    "journey_segment_at_ingest": row["journey_segment"],
                    "review_state": "REVIEW_ONLY",
                    "received_at": row["received_at"].isoformat(),
                    "contact_details_disclosed": False,
                    "consent_verified": False,
                    "send_authorized": False,
                    "execution_authority": "none",
                })
        except (RevenueCrmTransportError, ValueError, TypeError, KeyError):
            raise HTTPException(
                status_code=503, detail="canonical_mautic_inbox_unavailable",
            ) from None
        except Exception:
            raise HTTPException(
                status_code=503, detail="canonical_mautic_inbox_unavailable",
            ) from None
        return {
            "schema_version": "empire.mautic_crm_inbox_review.v1",
            "tenant_id": tenant,
            "mode": "OBSERVE",
            "read_only": True,
            "inbox_events": output,
            "count": len(output),
            "limit": limit,
            "contact_details_disclosed": False,
            "execution_authority": "none",
            "send_authorized": False,
            "canonical_crm_written": False,
        }

    return router
