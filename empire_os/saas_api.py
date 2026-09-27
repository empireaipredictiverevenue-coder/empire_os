"""Tenant-scoped read-only SaaS usage/subscription API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Protocol, Sequence

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from empire_os.saas_api_access import (
    ApiAccessEvidence,
    assess_api_access_readiness,
)
from empire_os.saas_api_access_freshness import assess_api_access_freshness
from empire_os.saas_api_access_registry import ApiAccessReviewRecord
from empire_os.saas_freshness import review_saas_quota_readiness
from empire_os.saas_usage_billing import (
    SaasUsageBillingTerms,
    review_saas_usage_billing,
)
from empire_os.saas_registry import SaasReadinessRecord
from empire_os.saas_readiness import (
    SaasScaleSnapshot,
    assess_saas_scale_readiness,
)
from empire_os.saas_scale import TenantMembership






class ApiAccessReadinessRequest(BaseModel):
    tenant_id: str
    user_id: str
    role: str
    membership_status: str = "active"
    active_subscription: bool
    tenant_isolation_verified: bool
    requested_scopes: list[str] = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)


class ApiAccessFreshnessRequest(ApiAccessReadinessRequest):
    membership_observed_at: str
    subscription_observed_at: str
    isolation_observed_at: str
    now_utc: str
    max_age_seconds: int = Field(default=21600, gt=0)


class ApiAccessReviewRegisterRequest(ApiAccessFreshnessRequest):
    review_key: str
    evidence: dict = Field(default_factory=dict)


class SaasQuotaReadinessRequest(BaseModel):
    tenant_id: str
    observed_monthly_usage: int = Field(ge=0)
    observed_usage_limit: int | None = Field(default=None, ge=0)
    active_subscription: bool
    tenant_isolation_verified: bool
    usage_observed_at: str
    subscription_observed_at: str
    isolation_observed_at: str
    now_utc: str
    max_age_seconds: int = Field(default=21600, gt=0)


class SaasUsageBillingRequest(SaasQuotaReadinessRequest):
    commercial_terms_verified: bool = False
    commercial_terms_ref: str | None = None
    overage_price_usdt_micros_per_unit: int | None = Field(default=None, ge=0)
    pricing_evidence_ref: str | None = None


class SaasReadinessRegisterRequest(BaseModel):
    readiness_key: str
    tenant_id: str
    active_members: int = Field(ge=0)
    observed_monthly_usage: int = Field(ge=0)
    observed_usage_limit: int | None = Field(default=None, ge=0)
    active_subscription: bool
    tenant_isolation_verified: bool
    white_label_requested: bool = False
    white_label_configured: bool = False
    evidence_refs: list[str] = Field(min_length=1)
    evidence: dict = Field(default_factory=dict)

class SaasScaleReadinessRequest(BaseModel):
    tenant_id: str
    active_members: int = Field(ge=0)
    observed_monthly_usage: int = Field(ge=0)
    observed_usage_limit: int | None = Field(default=None, ge=0)
    active_subscription: bool
    tenant_isolation_verified: bool
    white_label_requested: bool = False
    white_label_configured: bool = False
    evidence_refs: list[str] = Field(min_length=1)

class TenantScopedSaasRepository(Protocol):
    @property
    def tenant_id(self) -> str:
        ...

    def memberships(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        ...

    def usage(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        ...

    def subscriptions(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        ...


def create_saas_router(
    repository: TenantScopedSaasRepository | None = None,
    registry=None,
    api_access_registry=None,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/saas",
        tags=["saas"],
    )

    @router.get("/health")
    def health():
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "tenant_scoped": True,
            "repository_available": repository is not None,
            "registry_available": registry is not None,
            "api_access_registry_available": api_access_registry is not None,
            "tenant_id": (
                repository.tenant_id
                if repository is not None
                else None
            ),
        }

    def require_repository() -> TenantScopedSaasRepository:
        if repository is None:
            raise HTTPException(
                status_code=503,
                detail="saas_tenant_repository_not_activated",
            )
        if not str(repository.tenant_id or "").strip():
            raise HTTPException(
                status_code=503,
                detail="saas_tenant_scope_missing",
            )
        return repository


    @router.post("/quota-readiness/preview")
    def quota_readiness(req: SaasQuotaReadinessRequest):
        try:
            normalized = (
                req.now_utc[:-1] + "+00:00"
                if req.now_utc.endswith("Z")
                else req.now_utc
            )
            now = datetime.fromisoformat(normalized)
            if now.tzinfo is None:
                raise ValueError("now_utc must include timezone")
            result = review_saas_quota_readiness(
                tenant_id=req.tenant_id,
                observed_monthly_usage=req.observed_monthly_usage,
                observed_usage_limit=req.observed_usage_limit,
                active_subscription=req.active_subscription,
                tenant_isolation_verified=req.tenant_isolation_verified,
                usage_observed_at=req.usage_observed_at,
                subscription_observed_at=req.subscription_observed_at,
                isolation_observed_at=req.isolation_observed_at,
                now=now,
                max_age_seconds=req.max_age_seconds,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "recommendation_only": True,
            "execution_authority": "none",
            "provisioning_execution": False,
            "billing_execution": False,
            "subscription_mutation": False,
            "api_key_issuance": False,
            "review": result.as_dict(),
        }

    @router.post("/usage-billing/preview")
    def usage_billing_preview(req: SaasUsageBillingRequest):
        try:
            normalized = (
                req.now_utc[:-1] + "+00:00"
                if req.now_utc.endswith("Z")
                else req.now_utc
            )
            now = datetime.fromisoformat(normalized)
            if now.tzinfo is None:
                raise ValueError("now_utc must include timezone")
            quota_review = review_saas_quota_readiness(
                tenant_id=req.tenant_id,
                observed_monthly_usage=req.observed_monthly_usage,
                observed_usage_limit=req.observed_usage_limit,
                active_subscription=req.active_subscription,
                tenant_isolation_verified=req.tenant_isolation_verified,
                usage_observed_at=req.usage_observed_at,
                subscription_observed_at=req.subscription_observed_at,
                isolation_observed_at=req.isolation_observed_at,
                now=now,
                max_age_seconds=req.max_age_seconds,
            )
            review = review_saas_usage_billing(
                quota_review=quota_review,
                terms=SaasUsageBillingTerms(
                    tenant_id=req.tenant_id,
                    commercial_terms_verified=req.commercial_terms_verified,
                    commercial_terms_ref=req.commercial_terms_ref,
                    overage_price_usdt_micros_per_unit=(
                        req.overage_price_usdt_micros_per_unit
                    ),
                    pricing_evidence_ref=req.pricing_evidence_ref,
                ),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "invoice_creation": False,
            "payment_request_creation": False,
            "funds_movement": False,
            "billing_execution": False,
            "subscription_mutation": False,
            "recognized_revenue": False,
            "review": review.as_dict(),
        }

    @router.post("/api-access/readiness/preview")
    def api_access_readiness(req: ApiAccessReadinessRequest):
        try:
            membership = TenantMembership(
                tenant_id=req.tenant_id,
                user_id=req.user_id,
                role=req.role,
                status=req.membership_status,
            )
            result = assess_api_access_readiness(
                ApiAccessEvidence(
                    membership=membership,
                    active_subscription=req.active_subscription,
                    tenant_isolation_verified=(
                        req.tenant_isolation_verified
                    ),
                    requested_scopes=tuple(req.requested_scopes),
                    evidence_refs=tuple(req.evidence_refs),
                )
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "recommendation_only": True,
            "execution_authority": "none",
            "api_key_issuance": False,
            "api_key_revocation": False,
            "secret_material_generated": False,
            "readiness": result.as_dict(),
        }

    @router.post("/api-access/freshness/preview")
    def api_access_freshness(req: ApiAccessFreshnessRequest):
        try:
            membership = TenantMembership(
                tenant_id=req.tenant_id,
                user_id=req.user_id,
                role=req.role,
                status=req.membership_status,
            )
            readiness = assess_api_access_readiness(
                ApiAccessEvidence(
                    membership=membership,
                    active_subscription=req.active_subscription,
                    tenant_isolation_verified=req.tenant_isolation_verified,
                    requested_scopes=tuple(req.requested_scopes),
                    evidence_refs=tuple(req.evidence_refs),
                )
            )
            normalized = (
                req.now_utc[:-1] + "+00:00"
                if req.now_utc.endswith("Z")
                else req.now_utc
            )
            now = datetime.fromisoformat(normalized)
            if now.tzinfo is None:
                raise ValueError("now_utc must include timezone")
            freshness = assess_api_access_freshness(
                readiness=readiness,
                membership_observed_at=req.membership_observed_at,
                subscription_observed_at=req.subscription_observed_at,
                isolation_observed_at=req.isolation_observed_at,
                now=now,
                max_age_seconds=req.max_age_seconds,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "recommendation_only": True,
            "execution_authority": "none",
            "api_key_issuance": False,
            "api_key_revocation": False,
            "secret_material_generated": False,
            "subscription_mutation": False,
            "freshness": freshness.as_dict(),
        }

    @router.post("/api-access/reviews/register")
    def register_api_access_review(req: ApiAccessReviewRegisterRequest):
        if api_access_registry is None or not hasattr(
            api_access_registry,
            "record_api_access_review",
        ):
            raise HTTPException(
                status_code=503,
                detail="saas_api_access_registry_not_activated",
            )
        try:
            membership = TenantMembership(
                tenant_id=req.tenant_id,
                user_id=req.user_id,
                role=req.role,
                status=req.membership_status,
            )
            readiness = assess_api_access_readiness(
                ApiAccessEvidence(
                    membership=membership,
                    active_subscription=req.active_subscription,
                    tenant_isolation_verified=req.tenant_isolation_verified,
                    requested_scopes=tuple(req.requested_scopes),
                    evidence_refs=tuple(req.evidence_refs),
                )
            )
            normalized = (
                req.now_utc[:-1] + "+00:00"
                if req.now_utc.endswith("Z")
                else req.now_utc
            )
            now = datetime.fromisoformat(normalized)
            if now.tzinfo is None:
                raise ValueError("now_utc must include timezone")
            freshness = assess_api_access_freshness(
                readiness=readiness,
                membership_observed_at=req.membership_observed_at,
                subscription_observed_at=req.subscription_observed_at,
                isolation_observed_at=req.isolation_observed_at,
                now=now,
                max_age_seconds=req.max_age_seconds,
            )
            item = ApiAccessReviewRecord(
                review_key=req.review_key,
                freshness=freshness,
                evidence=dict(req.evidence),
            )
            item.validate()
            row = api_access_registry.record_api_access_review(item)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "recommendation_only": True,
            "approval_required": True,
            "execution_authority": "none",
            "api_key_issuance": False,
            "api_key_revocation": False,
            "secret_material_generated": False,
            "subscription_mutation": False,
            "provisioning_execution": False,
            "status": str(row.get("status") or "recorded"),
            "review_record": item.as_dict(),
            "result": dict(row),
        }

    @router.get("/api-access/reviews")
    def list_api_access_reviews(
        limit: int = Query(default=100, ge=1, le=500),
    ):
        if api_access_registry is None or not hasattr(
            api_access_registry,
            "list_api_access_reviews",
        ):
            raise HTTPException(
                status_code=503,
                detail="saas_api_access_registry_not_activated",
            )
        rows = list(api_access_registry.list_api_access_reviews(limit=limit))
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "recommendation_only": True,
            "approval_required": True,
            "execution_authority": "none",
            "api_key_issuance": False,
            "api_key_revocation": False,
            "secret_material_generated": False,
            "subscription_mutation": False,
            "provisioning_execution": False,
            "count": len(rows),
            "items": [dict(row) for row in rows],
        }

    @router.post("/scale-readiness/preview")
    def scale_readiness(req: SaasScaleReadinessRequest):
        snapshot = SaasScaleSnapshot(
            tenant_id=req.tenant_id,
            active_members=req.active_members,
            observed_monthly_usage=req.observed_monthly_usage,
            observed_usage_limit=req.observed_usage_limit,
            active_subscription=req.active_subscription,
            tenant_isolation_verified=req.tenant_isolation_verified,
            white_label_requested=req.white_label_requested,
            white_label_configured=req.white_label_configured,
            evidence_refs=tuple(req.evidence_refs),
        )
        try:
            result = assess_saas_scale_readiness(snapshot)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "recommendation_only": True,
            "execution_authority": "none",
            "provisioning_execution": False,
            "billing_execution": False,
            "readiness": result.as_dict(),
        }

    @router.get("/memberships")
    def memberships(limit: int = Query(default=100, ge=1, le=500)):
        repo = require_repository()
        rows = [dict(row) for row in repo.memberships(limit=limit)]
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "tenant_id": repo.tenant_id,
            "count": len(rows),
            "limit": limit,
            "items": rows,
        }

    @router.get("/usage")
    def usage(limit: int = Query(default=100, ge=1, le=500)):
        repo = require_repository()
        rows = [dict(row) for row in repo.usage(limit=limit)]
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "tenant_id": repo.tenant_id,
            "count": len(rows),
            "limit": limit,
            "items": rows,
        }

    @router.get("/subscriptions")
    def subscriptions(limit: int = Query(default=100, ge=1, le=500)):
        repo = require_repository()
        rows = [dict(row) for row in repo.subscriptions(limit=limit)]
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "billing_execution": False,
            "tenant_id": repo.tenant_id,
            "count": len(rows),
            "limit": limit,
            "items": rows,
        }


    @router.post("/scale-readiness/register")
    def register_scale_readiness(req: SaasReadinessRegisterRequest):
        if registry is None:
            raise HTTPException(
                status_code=503,
                detail="saas_readiness_registry_not_activated",
            )
        snapshot = SaasScaleSnapshot(
            tenant_id=req.tenant_id,
            active_members=req.active_members,
            observed_monthly_usage=req.observed_monthly_usage,
            observed_usage_limit=req.observed_usage_limit,
            active_subscription=req.active_subscription,
            tenant_isolation_verified=req.tenant_isolation_verified,
            white_label_requested=req.white_label_requested,
            white_label_configured=req.white_label_configured,
            evidence_refs=tuple(req.evidence_refs),
        )
        try:
            readiness = assess_saas_scale_readiness(snapshot)
            item = SaasReadinessRecord(
                readiness_key=req.readiness_key,
                snapshot=snapshot,
                readiness=readiness,
                evidence=dict(req.evidence),
            )
            item.validate()
            row = registry.record(item)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "provisioning_execution": False,
            "billing_execution": False,
            "api_key_issuance": False,
            "subscription_mutation": False,
            "status": str(row.get("status") or "recorded"),
            "readiness_record": item.as_dict(),
            "result": dict(row),
        }

    @router.get("/scale-readiness")
    def list_scale_readiness(limit: int = Query(default=100, ge=1, le=500)):
        if registry is None or not hasattr(registry, "list_readiness"):
            raise HTTPException(
                status_code=503,
                detail="saas_readiness_registry_not_activated",
            )
        rows = list(registry.list_readiness(limit=limit))
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "execution_authority": "none",
            "provisioning_execution": False,
            "billing_execution": False,
            "api_key_issuance": False,
            "subscription_mutation": False,
            "count": len(rows),
            "limit": limit,
            "items": [dict(row) for row in rows],
        }

    return router
