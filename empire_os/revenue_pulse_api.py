"""Read-only Revenue Pulse V3 API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from empire_os.revenue_pulse import (
    RevenuePulseForecast,
    RevenuePulseWindow,
    StormPulse,
    build_revenue_pulse,
)


class PulseWindowRequest(BaseModel):
    label: str
    hours: int = Field(gt=0)
    acquisitions: int | None = Field(default=None, ge=0)
    qualified: int | None = Field(default=None, ge=0)
    buyer_reviews: int | None = Field(default=None, ge=0)
    delivered_outreach: int | None = Field(default=None, ge=0)
    commercial_replies: int | None = Field(default=None, ge=0)
    commercial_terms: int | None = Field(default=None, ge=0)
    verified_payments: int | None = Field(default=None, ge=0)
    fulfilments: int | None = Field(default=None, ge=0)
    recognized_revenue_cents: int | None = Field(default=None, ge=0)
    realized_gp_cents: int | None = Field(default=None, ge=0)
    evidence_refs: list[str] = Field(min_length=1)


class ForecastRequest(BaseModel):
    horizon: str
    forecast_revenue_cents: int | None = Field(default=None, ge=0)
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence_refs: list[str] = Field(min_length=1)
    model_key: str | None = None


class StormPulseRequest(BaseModel):
    opportunity_count: int = Field(ge=0)
    max_multiplier: float | None = Field(default=None, ge=1)
    priority_boost_max: float | None = Field(default=None, ge=0)
    evidence_refs: list[str] = Field(min_length=1)


class RevenuePulsePreviewRequest(BaseModel):
    current: PulseWindowRequest
    previous: PulseWindowRequest | None = None
    highest_priority_blocker: str | None = None
    blocker_state: str | None = None
    forecasts: list[ForecastRequest] = Field(default_factory=list)
    storm: StormPulseRequest | None = None
    node_pulses: dict[str, dict[str, Any]] = Field(default_factory=dict)


def _window(req: PulseWindowRequest) -> RevenuePulseWindow:
    return RevenuePulseWindow(
        label=req.label,
        hours=req.hours,
        acquisitions=req.acquisitions,
        qualified=req.qualified,
        buyer_reviews=req.buyer_reviews,
        delivered_outreach=req.delivered_outreach,
        commercial_replies=req.commercial_replies,
        commercial_terms=req.commercial_terms,
        verified_payments=req.verified_payments,
        fulfilments=req.fulfilments,
        recognized_revenue_cents=req.recognized_revenue_cents,
        realized_gp_cents=req.realized_gp_cents,
        evidence_refs=tuple(req.evidence_refs),
    )


def create_revenue_pulse_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/revenue-pulse",
        tags=["revenue-pulse"],
    )

    @router.get("/status")
    def status():
        return {
            "schema_version": "empire.revenue-pulse.v3",
            "mode": "OBSERVE",
            "execution_allowed": False,
            "canonical_truth_only": True,
            "forecast_separate_from_revenue": True,
            "storm_multiplier_modeled_only": True,
        }

    @router.post("/preview")
    def preview(req: RevenuePulsePreviewRequest):
        try:
            return build_revenue_pulse(
                current=_window(req.current),
                previous=(
                    _window(req.previous)
                    if req.previous is not None
                    else None
                ),
                highest_priority_blocker=req.highest_priority_blocker,
                blocker_state=req.blocker_state,
                forecasts=tuple(
                    RevenuePulseForecast(
                        horizon=item.horizon,
                        forecast_revenue_cents=(
                            item.forecast_revenue_cents
                        ),
                        confidence=item.confidence,
                        evidence_refs=tuple(item.evidence_refs),
                        model_key=item.model_key,
                    )
                    for item in req.forecasts
                ),
                storm=(
                    StormPulse(
                        opportunity_count=req.storm.opportunity_count,
                        max_multiplier=req.storm.max_multiplier,
                        priority_boost_max=req.storm.priority_boost_max,
                        evidence_refs=tuple(req.storm.evidence_refs),
                    )
                    if req.storm is not None
                    else None
                ),
                node_pulses=req.node_pulses,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return router
