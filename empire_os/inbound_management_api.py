"""Default-off, tenant-identity-derived read-only management API.

Never uses tenant IDs from the HTTP request; bearer claims are the sole tenant
selector. Uses private, pre-configured local evidence, directory and audit DBs.
This is a guarded development adapter, NOT deployed customer account auth.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Query, Response

from empire_os.inbound_access_audit import RecoveryAccessAudit
from empire_os.inbound_management_auth import (
    RecoveryAccessDenied, RecoveryActor, authenticate_recovery_reader,
)
from empire_os.inbound_opportunity_intelligence import (
    OpportunityPolicy, build_opportunity_queue,
)
from empire_os.inbound_recovery_patterns import PatternPolicy, analyse_inbound_patterns
from empire_os.inbound_recovery_scorecard import build_inbound_recovery_scorecard
from empire_os.inbound_recovery_store import OfflineRecoveryStore
from empire_os.inbound_tenant_directory import OfflineTenantDirectory, RecoveryTenant


def _enabled() -> bool:
    return os.getenv("EMPIRE_INBOUND_MANAGER_ENABLED", "").lower().strip() == "true"


def _fixed_path(setting: str, *, may_create: bool = False) -> Path:
    raw = os.getenv(setting, "").strip()
    if not raw:
        raise RuntimeError("management_storage_not_configured")
    p = Path(raw)
    if not p.is_absolute() or p.is_symlink() or not p.parent.is_dir():
        raise RuntimeError("management_storage_path_invalid")
    if not may_create and not p.is_file():
        raise RuntimeError("management_storage_unavailable")
    return p


def _tenant_actor(
    authorization: str | None, scope: str
) -> tuple[RecoveryActor, RecoveryTenant]:
    try:
        actor = authenticate_recovery_reader(
            authorization,
            signing_secret=os.getenv("EMPIRE_INBOUND_MANAGER_JWT_KEY", ""),
            required_scope=scope,
        )
    except RecoveryAccessDenied as exc:
        raise HTTPException(status_code=401, detail="management_access_denied") from exc
    try:
        with OfflineTenantDirectory(
            _fixed_path("EMPIRE_INBOUND_MANAGER_TENANT_DB"), read_only=True
        ) as directory:
            tenant = directory.get(actor.tenant_id)
    except (RuntimeError, OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="management_directory_not_ready") from exc
    if tenant is None or not tenant.may_review:
        raise HTTPException(status_code=403, detail="management_tenant_not_approved")
    return actor, tenant


def _read(
    authorization: str | None,
    scope: str,
    operation: str,
) -> tuple[RecoveryActor, RecoveryTenant, tuple]:
    actor, tenant = _tenant_actor(authorization, scope)
    try:
        with RecoveryAccessAudit(
            _fixed_path("EMPIRE_INBOUND_MANAGER_AUDIT_DB", may_create=True),
            audit_key=os.getenv("EMPIRE_INBOUND_MANAGER_AUDIT_KEY", ""),
        ) as audit:
            audit.append(actor, operation)
        with OfflineRecoveryStore(
            _fixed_path("EMPIRE_INBOUND_MANAGER_EVIDENCE_DB"), read_only=True
        ) as store:
            events = store.events_for_tenant(actor.tenant_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="management_evidence_or_audit_not_ready") from exc
    return actor, tenant, events


def _as_of(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise HTTPException(status_code=422, detail="as_of_timezone_required")
    return current


def create_inbound_management_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/inbound-recovery/management", tags=["inbound-recovery-management"]
    )

    @router.get("/profile")
    def profile(
        response: Response,
        authorization: str | None = Header(default=None),
    ):
        if not _enabled():
            raise HTTPException(status_code=404, detail="management_disabled")
        response.headers["Cache-Control"] = "no-store"
        actor, tenant, _events = _read(authorization, "recovery:read", "profile_read")
        return {
            "tenant_id": actor.tenant_id,
            "business_name": tenant.business_name,
            "vertical": tenant.vertical,
            "timezone": tenant.timezone_name,
            "reporting_authorized": tenant.may_review,
            "management_mode": "local_read_only_nonproduction",
            "live_telephony": "not_configured_by_this_api",
        }

    @router.get("/scorecard")
    def scorecard(
        response: Response,
        authorization: str | None = Header(default=None),
    ):
        if not _enabled():
            raise HTTPException(status_code=404, detail="management_disabled")
        response.headers["Cache-Control"] = "no-store"
        actor, _tenant, events = _read(authorization, "recovery:read", "scorecard_read")
        from empire_os.inbound_revenue_recovery import RecoveryLedger
        ledger = RecoveryLedger()
        for event in events:
            ledger.append(event)
        result = build_inbound_recovery_scorecard(ledger.report(actor.tenant_id))
        result["management_mode"] = "local_read_only_nonproduction"
        return result

    @router.get("/opportunities")
    def opportunities(
        response: Response,
        authorization: str | None = Header(default=None),
        as_of: datetime | None = Query(default=None),
    ):
        if not _enabled():
            raise HTTPException(status_code=404, detail="management_disabled")
        response.headers["Cache-Control"] = "no-store"
        actor, _tenant, events = _read(authorization, "recovery:queue", "queue_read")
        result = build_opportunity_queue(
            events, policy=OpportunityPolicy(actor.tenant_id), as_of=_as_of(as_of),
        )
        result["management_mode"] = "local_read_only_nonproduction"
        return result

    @router.get("/patterns")
    def patterns(
        response: Response,
        authorization: str | None = Header(default=None),
        as_of: datetime | None = Query(default=None),
    ):
        if not _enabled():
            raise HTTPException(status_code=404, detail="management_disabled")
        response.headers["Cache-Control"] = "no-store"
        actor, tenant, events = _read(authorization, "recovery:patterns", "patterns_read")
        result = analyse_inbound_patterns(
            events, as_of=_as_of(as_of),
            policy=PatternPolicy(actor.tenant_id, tenant.timezone_name),
        )
        result["management_mode"] = "local_read_only_nonproduction"
        return result

    return router
