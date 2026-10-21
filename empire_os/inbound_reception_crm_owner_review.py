"""Opt-in tenant-scoped AI receptionist enquiry view under EXISTING Revenue CRM auth.

No new user directory, CRM writers, tenant-header auth, database schema,
callback execution, prospect admission, or payment/booking claims. The source
queue is the SAME running signed voice engine. Still in-process only and
therefore unsuitable for multiworker/restart production without durable state.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from threading import Lock
from fastapi import APIRouter, HTTPException, Request, Response

from empire_os.inbound_reception_call_flow import InboundReceptionCallEngine
from empire_os.inbound_reception_recovery_bridge import (
    project_reception_recovery_review,
)
from empire_os.revenue_crm_api import AuthenticatedRevenueCrmRead
from empire_os.revenue_crm_transport import (
    PostgresRevenueCrmRepository, RevenueCrmTransportError,
)


def create_inbound_reception_crm_owner_review_router(
    *,
    engine: InboundReceptionCallEngine,
    resolve_authenticated_read: Callable[[Request], AuthenticatedRevenueCrmRead | None],
    enabled: bool = False,
    review_lock: object | None = None,
) -> APIRouter:
    """Reuse the canonical CRM resolver and dedicated LOGIN/session_user read.

    This is *not* an admission writer. Production needs an approved durable
    queue, owner receipt, retention/suppression and authenticated source
    binding before an actual CRM handoff or follow-up can be claimed.
    """
    if not isinstance(engine, InboundReceptionCallEngine):
        raise ValueError("existing_reception_engine_required")
    if not callable(resolve_authenticated_read):
        raise ValueError("existing_crm_tenant_resolver_required")
    owner_lock = review_lock if review_lock is not None else Lock()
    if not hasattr(owner_lock, "__enter__") or not hasattr(owner_lock, "__exit__"):
        raise ValueError("shared_reception_lock_required")
    router = APIRouter(
        prefix="/v1/inbound-reception/crm-review",
        tags=["inbound-reception-crm-review"],
    )

    @router.get("/enquiries")
    def list_enquiries(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["Referrer-Policy"] = "no-referrer"
        if enabled is not True:
            raise HTTPException(status_code=404, detail="reception_crm_review_disabled")
        # Refuse caller-supplied tenant scope in query parameters. Every item
        # comes from the authenticated server-side CRM principal, not headers.
        if request.query_params:
            raise HTTPException(status_code=422, detail="reception_crm_review_query_disallowed")
        try:
            access = resolve_authenticated_read(request)
        except Exception:
            raise HTTPException(
                status_code=503, detail="reception_crm_authentication_unavailable"
            ) from None
        if access is None:
            raise HTTPException(status_code=401, detail="reception_crm_identity_required")
        if (not isinstance(access, AuthenticatedRevenueCrmRead)
            or not isinstance(access.repository, PostgresRevenueCrmRepository)
            or access.tenant_id != access.repository.tenant_id):
            raise HTTPException(status_code=503, detail="reception_crm_tenant_unverified")

        # Existing CRM repository's prospects() issues SET TRANSACTION READ ONLY,
        # SET LOCAL ROLE and verifies public.empire_current_tenant_id() equals
        # the independently authenticated tenant. Do not use its data to
        # create/admit an inbound customer prospect.
        try:
            probe = access.repository.prospects(limit=1)
        except Exception:
            raise HTTPException(status_code=503, detail="reception_crm_tenant_unverified") from None
        if (not isinstance(probe, (list, tuple))
            or any(
                not isinstance(row, Mapping)
                or str(row.get("tenant_id") or "") != access.tenant_id
                for row in probe
            )):
            raise HTTPException(status_code=503, detail="reception_crm_tenant_unverified")
        if access.tenant_id not in engine.profiles:
            # A real CRM account can exist with no registered receptionist
            # product; don't leak which other tenants have pending requests.
            return {
                "schema": "empire.inbound.reception_crm_owner_preview.v1",
                "status": "NO_RECEPTIONIST_TENANT_CONFIGURED",
                "mode": "AUTHENTICATED_READ_ONLY_PRIVATE_PREVIEW",
                "enquiry_drafts_count": 0, "review_items": [],
                "crm_writes": False, "canonical_crm_receipts": 0,
                "customer_followups_executed": False,
                "verified_recovered_calls": 0,
                "recovered_revenue_claimed": False,
            }

        # Never claim missing provider evidence. Only read the exact current
        # tenant's consented in-memory drafts and original RecoveryLedger.
        try:
            # Shared lock with the signed Voice API prevents concurrent
            # webhook writes from changing the snapshot mid-review.
            with owner_lock:
                drafts = engine.review_handoffs_for_tenant(access.tenant_id)
                # A distinct no-PII recent queue cap; do not auto-evict or
                # falsely claim complete CRM visibility if over capacity.
                if len(drafts) > 500:
                    raise HTTPException(status_code=503, detail="reception_crm_review_capacity_held")
                projection = project_reception_recovery_review(
                    access.tenant_id, drafts,
                )
        except HTTPException:
            raise
        except (TypeError, ValueError):
            raise HTTPException(status_code=503, detail="reception_crm_review_unavailable") from None
        return {
            "schema": "empire.inbound.reception_crm_owner_preview.v1",
            "status": "CONSENTED_ENQUIRIES_FOR_OWNER_REVIEW_ONLY",
            "mode": "AUTHENTICATED_READ_ONLY_PRIVATE_PREVIEW",
            "enquiry_drafts_count": projection["enquiry_drafts_count"],
            "review_items": projection["review_items"],
            "crm_writes": False, "canonical_crm_receipts": 0,
            "customer_followups_executed": False,
            "verified_recovered_calls": 0,
            "recovered_revenue_claimed": False,
            "appointment_confirmed": False,
            "durable_queue_verified": False,
        }

    return router
