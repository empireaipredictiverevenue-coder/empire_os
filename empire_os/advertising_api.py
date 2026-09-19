"""Read-only Advertising Brain provider API."""
from __future__ import annotations

from typing import Any, Mapping, Protocol

from fastapi import APIRouter, HTTPException, Query


class AdvertisingReadAdapter(Protocol):
    def status(self) -> Any:
        ...

    def observations(
        self,
        *,
        start_date: str,
        end_date: str,
    ) -> Any:
        ...


def create_advertising_router(
    adapters: Mapping[str, AdvertisingReadAdapter] | None = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/advertising",
        tags=["advertising-brain"],
    )
    bound = {
        str(name).strip().lower(): adapter
        for name, adapter in dict(adapters or {}).items()
    }

    @router.get("/health")
    def health():
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "campaign_creation": False,
            "budget_mutation": False,
            "pause_mutation": False,
            "retarget_execution": False,
            "providers": sorted(bound),
        }

    @router.get("/{provider}/status")
    def provider_status(provider: str):
        name = provider.strip().lower()
        adapter = bound.get(name)
        if adapter is None:
            raise HTTPException(
                status_code=503,
                detail="advertising_read_adapter_not_activated",
            )
        status = adapter.status()
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "provider": name,
            "status": (
                status.__dict__
                if hasattr(status, "__dict__")
                else status
            ),
        }

    @router.get("/{provider}/observations")
    def observations(
        provider: str,
        start_date: str,
        end_date: str,
        limit: int = Query(default=500, ge=1, le=5000),
    ):
        name = provider.strip().lower()
        adapter = bound.get(name)
        if adapter is None:
            raise HTTPException(
                status_code=503,
                detail="advertising_read_adapter_not_activated",
            )
        try:
            rows = list(
                adapter.observations(
                    start_date=start_date,
                    end_date=end_date,
                )
            )[:limit]
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="advertising_read_unavailable",
            ) from exc

        items = [
            row.as_dict() if hasattr(row, "as_dict") else dict(row)
            for row in rows
        ]
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "campaign_creation": False,
            "budget_mutation": False,
            "pause_mutation": False,
            "retarget_execution": False,
            "provider": name,
            "count": len(items),
            "limit": limit,
            "items": items,
        }

    return router
