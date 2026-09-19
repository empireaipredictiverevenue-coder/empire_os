"""OBSERVE-only Astra operating board preview API."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from empire_os.astra import AstraSnapshot, build_operating_board


class AstraSnapshotRequest(BaseModel):
    execution_mode: str = "observe"
    actual_revenue_cents: int = Field(default=0, ge=0)
    premium_ai_budget_cents: int = Field(default=0, ge=0)
    replies_waiting: int = Field(default=0, ge=0)
    failed_jobs: int = Field(default=0, ge=0)
    owned_inventory_count: int = Field(default=0, ge=0)
    qualified_unallocated_count: int = Field(default=0, ge=0)
    active_buyer_capacity: int = Field(default=0, ge=0)
    buyer_candidates_due: int = Field(default=0, ge=0)
    outbound_domain_verified: bool = False
    source_health_ok: bool = True


class AstraBoardPreviewRequest(BaseModel):
    snapshot: AstraSnapshotRequest
    negative_margin_orders: int = Field(default=0, ge=0)
    calibration_ready: bool = False
    gross_margin_rate: float | None = None
    limit: int = Field(default=5, ge=1, le=20)


def create_astra_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/astra",
        tags=["astra"],
    )

    @router.get("/health")
    def health():
        return {
            "mode": "OBSERVE",
            "side_effects": "none",
            "execution_authority": "none",
            "commercial_mutation": False,
            "payment_execution": False,
            "outreach_execution": False,
            "allocation_execution": False,
        }

    @router.post("/board/preview")
    def board_preview(req: AstraBoardPreviewRequest):
        mode = req.snapshot.execution_mode.strip().lower()
        if mode != "observe":
            raise HTTPException(
                status_code=422,
                detail="astra preview supports OBSERVE only",
            )

        snapshot = AstraSnapshot(**req.snapshot.model_dump())
        board = build_operating_board(
            snapshot,
            negative_margin_orders=req.negative_margin_orders,
            calibration_ready=req.calibration_ready,
            gross_margin_rate=req.gross_margin_rate,
            limit=req.limit,
        )
        return {
            "mode": "OBSERVE",
            "side_effects": "none",
            "execution_authority": "none",
            "commercial_mutation": False,
            "board": board.as_dict(),
        }

    return router
