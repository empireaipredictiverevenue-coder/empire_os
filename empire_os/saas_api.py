"""Tenant-scoped read-only SaaS usage/subscription API."""
from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence

from fastapi import APIRouter, HTTPException, Query


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

    return router
