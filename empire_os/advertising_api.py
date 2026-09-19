"""Read-only Advertising Brain provider API plus governed observation ingest."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Protocol

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from empire_os.advertising_brain import normalise_ad_observation
from empire_os.advertising_freshness import review_advertising_evidence
from empire_os.advertising_ingest import build_canonical_ad_observation
from empire_os.advertising_review import review_campaign_economics


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


class AdvertisingObservationRepository(Protocol):
    def append(self, item):
        ...


class AdvertisingCampaignReviewRequest(BaseModel):
    campaign_id: str
    observations: list[dict[str, Any]] = Field(default_factory=list)


class AdvertisingEvidenceReviewRequest(BaseModel):
    campaign_id: str
    now_utc: str
    max_age_seconds: int = Field(default=21600, gt=0)
    observations: list[dict[str, Any]] = Field(default_factory=list)


class AdvertisingObservationIngestRequest(BaseModel):
    canonical_campaign_id: str
    provider_observation_id: str
    canonical_creative_id: str | None = None
    row: dict[str, Any]
    evidence: dict[str, Any] = Field(default_factory=dict)


def create_advertising_router(
    adapters: Mapping[str, AdvertisingReadAdapter] | None = None,
    observation_repository: AdvertisingObservationRepository | None = None,
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
            "observation_ingest_configured": (
                observation_repository is not None
            ),
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

    @router.post("/campaigns/review/preview")
    def campaign_review(req: AdvertisingCampaignReviewRequest):
        try:
            observations = tuple(
                normalise_ad_observation(row)
                for row in req.observations
            )
            result = review_campaign_economics(
                observations,
                campaign_id=req.campaign_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "campaign_creation": False,
            "budget_mutation": False,
            "pause_mutation": False,
            "retarget_execution": False,
            "review": result.as_dict(),
        }

    @router.post("/campaigns/evidence/preview")
    def campaign_evidence_preview(req: AdvertisingEvidenceReviewRequest):
        try:
            normalized = (
                req.now_utc[:-1] + "+00:00"
                if req.now_utc.endswith("Z")
                else req.now_utc
            )
            now = datetime.fromisoformat(normalized)
            if now.tzinfo is None:
                raise ValueError("now_utc must include timezone")
            observations = tuple(
                normalise_ad_observation(row)
                for row in req.observations
            )
            result = review_advertising_evidence(
                observations,
                campaign_id=req.campaign_id,
                now=now,
                max_age_seconds=req.max_age_seconds,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "campaign_creation": False,
            "budget_mutation": False,
            "pause_mutation": False,
            "retarget_execution": False,
            "review": result.as_dict(),
        }

    @router.post("/observations/ingest")
    def ingest_observation(req: AdvertisingObservationIngestRequest):
        if observation_repository is None:
            raise HTTPException(
                status_code=503,
                detail="advertising_observation_ingest_not_activated",
            )
        try:
            item = build_canonical_ad_observation(
                canonical_campaign_id=req.canonical_campaign_id,
                provider_observation_id=req.provider_observation_id,
                canonical_creative_id=req.canonical_creative_id,
                row=req.row,
                evidence=req.evidence,
            )
            result = observation_repository.append(item)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        status = str(result.get("status") or "").strip()
        if status == "conflict":
            raise HTTPException(
                status_code=409,
                detail=str(
                    result.get("reason")
                    or "advertising_observation_conflict"
                ),
            )
        if status not in {"recorded", "existing"}:
            raise HTTPException(
                status_code=502,
                detail="advertising_ingest_invalid_repository_result",
            )

        return {
            "mode": "OBSERVE",
            "status": status,
            "observation_id": result.get("observation_id"),
            "canonical_campaign_id": item.canonical_campaign_id,
            "provider_observation_id": item.provider_observation_id,
            "execution_authority": "none",
            "campaign_creation": False,
            "budget_mutation": False,
            "pause_mutation": False,
            "retarget_execution": False,
        }

    return router
