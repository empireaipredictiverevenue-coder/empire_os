"""OBSERVE-only Outreach Intelligence API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from empire_os.outreach_intelligence import (
    build_outreach_packet,
    reply_next_action,
)


class OutreachPacketRequest(BaseModel):
    account: dict[str, Any]
    contact_plan: dict[str, Any]
    context: dict[str, Any]
    signals: list[dict[str, Any]] = Field(default_factory=list)
    channel_evidence: list[dict[str, Any]] = Field(default_factory=list)
    proof_refs: list[str] = Field(default_factory=list)
    predicted_economics: dict[str, Any] = Field(default_factory=dict)


class ReplyActionRequest(BaseModel):
    classification: str


def create_outreach_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/outreach",
        tags=["outreach-intelligence"],
    )

    @router.get("/health")
    def health():
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "send_enabled": False,
            "sms_enabled": False,
            "voice_dial_enabled": False,
            "booking_execution": False,
            "crm_mutation": False,
            "buyer_activation": False,
        }

    @router.post("/packet/preview")
    def packet_preview(req: OutreachPacketRequest):
        try:
            packet = build_outreach_packet(
                account=req.account,
                contact_plan=req.contact_plan,
                context=req.context,
                signals=req.signals,
                channel_evidence=req.channel_evidence,
                proof_refs=req.proof_refs,
                predicted_economics=req.predicted_economics,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return packet

    @router.post("/reply-next-action/preview")
    def reply_action_preview(req: ReplyActionRequest):
        return reply_next_action(req.classification)

    return router
