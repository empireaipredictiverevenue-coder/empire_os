"""Evidence-only Predictive Cloud V3 forecast preview and registry API."""
from __future__ import annotations

from datetime import date
from typing import Any, Protocol

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from empire_os.predictive_calibration import (
    ForecastActualEvidence,
    review_forecast_calibration,
)
from empire_os.predictive_materializer import materialize_daily_actuals
from empire_os.predictive_registry import ForecastRegistryRecord


class ObservedActualRequest(BaseModel):
    observed_date: str
    value: float = Field(ge=0)
    source: str


class ForecastPreviewRequest(BaseModel):
    metric: str
    horizon_days: int = Field(ge=1, le=365)
    points: list[ObservedActualRequest]


class ForecastCalibrationRequest(BaseModel):
    preview: ForecastPreviewRequest
    actual_observed_date: str
    actual_value: float = Field(ge=0)
    actual_source: str


class ForecastRegisterRequest(BaseModel):
    forecast_key: str
    model_name: str
    model_version: str
    dimension_key: str = "global"
    preview: ForecastPreviewRequest
    evidence: dict[str, Any] = Field(default_factory=dict)


class PredictiveRegistryRepository(Protocol):
    def record(self, item: ForecastRegistryRecord):
        ...

    def list_forecasts(self, *, limit: int):
        ...


def create_predictive_router(
    repository: PredictiveRegistryRepository | None = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/predictive",
        tags=["predictive-cloud"],
    )

    def materialize(req: ForecastPreviewRequest):
        rows = [
            {
                "snapshot_date": point.observed_date,
                "actual_value": point.value,
                "source": point.source,
            }
            for point in req.points
        ]
        try:
            return materialize_daily_actuals(
                metric=req.metric,
                rows=rows,
                value_field="actual_value",
                date_field="snapshot_date",
                horizon_days=req.horizon_days,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get("/health")
    def health():
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "write_authority": (
                "forecast_registry_only"
                if repository is not None
                else "none"
            ),
            "synthetic_data_allowed": False,
            "registry_available": repository is not None,
            "commercial_execution": False,
        }

    @router.post("/forecast/preview")
    def forecast_preview(req: ForecastPreviewRequest):
        result = materialize(req)
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "write_authority": "none",
            "synthetic_data_allowed": False,
            "materialization": result.as_dict(),
        }

    @router.post("/forecast/calibration/preview")
    def forecast_calibration_preview(req: ForecastCalibrationRequest):
        result = materialize(req.preview)
        try:
            actual = ForecastActualEvidence(
                metric=req.preview.metric,
                observed_date=date.fromisoformat(req.actual_observed_date),
                actual_value=req.actual_value,
                source=req.actual_source,
            )
            review = review_forecast_calibration(
                materialization=result,
                actual=actual,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "write_authority": "none",
            "synthetic_data_allowed": False,
            "forecast_mutation": False,
            "model_weight_mutation": False,
            "commercial_execution": False,
            "accounting_mutation": False,
            "creates_actual_revenue": False,
            "calibration": review.as_dict(),
        }

    @router.post("/forecast/register")
    def forecast_register(req: ForecastRegisterRequest):
        if repository is None:
            raise HTTPException(
                status_code=503,
                detail="predictive_registry_not_activated",
            )
        result = materialize(req.preview)
        item = ForecastRegistryRecord(
            forecast_key=req.forecast_key,
            model_name=req.model_name,
            model_version=req.model_version,
            dimension_key=req.dimension_key,
            forecast=result.forecast,
            evidence=dict(req.evidence),
        )
        try:
            item.validate()
            stored = repository.record(item)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        status = str(stored.get("status") or "").strip()
        if status not in {"recorded", "existing"}:
            raise HTTPException(
                status_code=502,
                detail="predictive_registry_invalid_repository_result",
            )
        return {
            "mode": "OBSERVE",
            "status": status,
            "forecast_id": stored.get("forecast_id"),
            "execution_authority": "none",
            "commercial_execution": False,
            "forecast": result.forecast.as_dict(),
        }

    @router.get("/forecasts")
    def forecasts(limit: int = Query(default=100, ge=1, le=500)):
        if repository is None:
            raise HTTPException(
                status_code=503,
                detail="predictive_registry_not_activated",
            )
        rows = list(repository.list_forecasts(limit=limit))
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "execution_authority": "none",
            "count": len(rows),
            "items": [dict(row) for row in rows],
        }

    return router
