"""Evidence-only Predictive Cloud V3 forecast preview API."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from empire_os.predictive_materializer import materialize_daily_actuals


class ObservedActualRequest(BaseModel):
    observed_date: str
    value: float = Field(ge=0)
    source: str


class ForecastPreviewRequest(BaseModel):
    metric: str
    horizon_days: int = Field(ge=1, le=365)
    points: list[ObservedActualRequest]


def create_predictive_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/predictive",
        tags=["predictive-cloud"],
    )

    @router.get("/health")
    def health():
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "write_authority": "none",
            "synthetic_data_allowed": False,
        }

    @router.post("/forecast/preview")
    def forecast_preview(req: ForecastPreviewRequest):
        rows = [
            {
                "snapshot_date": point.observed_date,
                "actual_value": point.value,
                "source": point.source,
            }
            for point in req.points
        ]
        try:
            result = materialize_daily_actuals(
                metric=req.metric,
                rows=rows,
                value_field="actual_value",
                date_field="snapshot_date",
                horizon_days=req.horizon_days,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "write_authority": "none",
            "synthetic_data_allowed": False,
            "materialization": result.as_dict(),
        }

    return router
