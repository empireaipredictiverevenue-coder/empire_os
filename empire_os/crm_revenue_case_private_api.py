"""Optional original-CRM authenticated V11 order detail extension.

Attached ONLY to the existing first-party CRM read router by its original
pilot owner. Default OFF. No global query, separate API/service, unscoped
tenant header, source writes, payment execution or public founder overview.
"""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Callable, Literal, Mapping
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from empire_os.crm_revenue_case_bridge import review_signed_crm_revenue_case
from empire_os.revenue_crm_api import AuthenticatedRevenueCrmRead
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier
from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository
from empire_os.saas_scale import TenantMembership

STAGES = ("BUYER_ACCEPTANCE", "FULFILMENT", "SETTLEMENT_LEDGER",
          "RECOGNIZER_EVENT", "ECONOMIC_MEMORY_SHADOW")


class PrivateStage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage: str
    status: Literal["NOT_OBSERVED", "SOURCE_REPORTED_COHERENCE_ONLY"]


class PrivateFounderCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["empire.crm.founder_revenue_case_view.v1"]
    status: Literal["SIGNED_ORDER_OBSERVED_FINANCIAL_PROOF_UNATTESTED"]
    mode: Literal["OBSERVE"]
    case_ref: str = Field(pattern=r"^revenue_case:[0-9a-f]{24}$")
    reported_order_state: str | None
    next_missing_stage: str
    next_original_owner: str
    next_original_action: str
    stages: list[PrivateStage] = Field(min_length=5, max_length=5)
    independent_evidence_attested_here: Literal[False]
    recognized_revenue_verified_here: Literal[False]
    economic_memory_training_authorized: Literal[False]
    database_writes: Literal[False]
    outbound_sent: Literal[False]
    execution_authority: Literal["NONE"]


def create_private_revenue_case_router(
    *, resolve_authenticated_read: Callable[[Request], AuthenticatedRevenueCrmRead | None],
    signed_crm_verifier: SignedCrmTenantVerifier,
    dedicated_tenant_dsns: Mapping[str, str],
    load_original_membership: Callable[[str, str], TenantMembership | None],
) -> APIRouter:
    """Existing signed CRM and dedicated login only; no route without opt-in."""
    if not callable(resolve_authenticated_read):
        raise ValueError("original signed CRM tenant resolver required")
    if type(signed_crm_verifier) is not SignedCrmTenantVerifier:
        raise ValueError("original pinned signed CRM verifier required")
    if not callable(load_original_membership):
        raise ValueError("original CRM owner membership lookup required")
    if not isinstance(dedicated_tenant_dsns, Mapping) or not dedicated_tenant_dsns:
        raise ValueError("original dedicated CRM tenant login inventory required")
    known = dict(dedicated_tenant_dsns)
    if any(not isinstance(k, str) or str(UUID(k)) != k or
           not isinstance(v, str) or not v.strip() for k, v in known.items()):
        raise ValueError("canonical original CRM connection inventory required")

    router = APIRouter()  # Mounted INSIDE the existing /v1/revenue-crm router.

    @router.get(
        "/prospects/{prospect_id}/opportunities/{opportunity_id}/orders/{order_id}/revenue-case"
    )
    def private_order_case(
        prospect_id: str, opportunity_id: str, order_id: str,
        request: Request, response: Response,
    ) -> dict:
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        headers = request.headers.getlist("authorization")
        if len(headers) != 1 or not headers[0].startswith("Bearer "):
            raise HTTPException(401, detail="authenticated_crm_scope_required")
        bearer = headers[0][len("Bearer "):]
        if not bearer or bearer != bearer.strip() or " " in bearer or len(bearer) > 4096:
            raise HTTPException(401, detail="authenticated_crm_scope_required")
        try:
            access = resolve_authenticated_read(request)
        except Exception:
            raise HTTPException(503, detail="authenticated_crm_read_unavailable") from None
        if access is None:
            raise HTTPException(401, detail="authenticated_crm_scope_required")
        if (not isinstance(access, AuthenticatedRevenueCrmRead)
                or not isinstance(access.repository, PostgresRevenueCrmRepository)
                or access.repository.tenant_id != access.tenant_id
                or access.repository.dsn != known.get(access.tenant_id)):
            raise HTTPException(503, detail="authenticated_crm_read_unavailable")
        # The ordinary CRM read permission includes viewers and analysts.
        # A V11 *founder* order case instead requires a fresh original OWNER
        # membership; never elevate based on caller-provided role headers.
        try:
            if signed_crm_verifier.authenticate(bearer) != access.tenant_id:
                raise ValueError("signed CRM tenant mismatch")
            segment = bearer.split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(
                segment + "=" * (-len(segment) % 4)))
            subject = claims["sub"]
            membership = load_original_membership(subject, access.tenant_id)
            if (not isinstance(membership, TenantMembership)
                    or membership.user_id != subject
                    or membership.tenant_id != access.tenant_id
                    or membership.role != "owner"
                    or not membership.can("admin")):
                raise PermissionError("original founder owner membership required")
        except Exception:
            raise HTTPException(403, detail="crm_owner_membership_required") from None
        # Re-authenticate through the ORIGINAL pinned verifier and per-tenant
        # session_user reader. Neither identity nor DSN comes from path/header.
        try:
            report = review_signed_crm_revenue_case(
                signed_crm_bearer=bearer,
                crm_verifier=signed_crm_verifier,
                dedicated_crm_dsn=known[access.tenant_id],
                prospect_id=prospect_id,
                opportunity_id=opportunity_id,
                fulfilment_order_id=order_id,
                as_of=datetime.now(timezone.utc),
            )
            if (report.get("tenant_id") != access.tenant_id
                    or report.get("fulfilment_order_id") != order_id):
                raise ValueError("signed order mismatch")
            redacted = PrivateFounderCase.model_validate(report["founder_case_view"])
            if tuple(stage.stage for stage in redacted.stages) != STAGES:
                raise ValueError("untrusted source stages")
        except Exception:
            # Do not leak bearer, customer identifiers, SQL or internal state.
            raise HTTPException(503, detail="authenticated_order_case_unavailable") from None
        return redacted.model_dump()

    return router
