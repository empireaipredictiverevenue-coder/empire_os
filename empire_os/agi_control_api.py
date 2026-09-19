"""OBSERVE-only API for Empire's agentic intelligence control plane."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from empire_os.agi_control_plane import (
    assess_agi_layer_readiness,
    build_cognitive_packet,
    review_learning_candidate,
)
from empire_os.agi_memory import build_memory_query, review_memory_item
from empire_os.agi_capabilities import (
    capability_registry,
    review_capability_request,
)


class AgiReadinessRequest(BaseModel):
    evidence: dict[str, Any] = Field(default_factory=dict)


class CognitivePacketRequest(BaseModel):
    task_id: str
    goal: str
    evidence_refs: list[str]
    world_state_ref: str
    memory_refs: list[dict[str, Any]] = Field(default_factory=list)
    options: list[dict[str, Any]] = Field(default_factory=list)
    selected_option_id: str | None = None
    constraints: list[str] = Field(default_factory=list)
    verifier: dict[str, Any] = Field(default_factory=dict)
    policy: dict[str, Any] = Field(default_factory=dict)
    authority_mode: str = "OBSERVE"
    side_effect_class: str = "none"


class LearningCandidateRequest(BaseModel):
    candidate: dict[str, Any] = Field(default_factory=dict)


class MemoryQueryRequest(BaseModel):
    task_type: str
    task_id: str
    entity_refs: list[str] = Field(default_factory=list)
    topic_keys: list[str] = Field(default_factory=list)
    max_items_per_type: int = 20


class MemoryItemReviewRequest(BaseModel):
    item: dict[str, Any] = Field(default_factory=dict)


class CapabilityReviewRequest(BaseModel):
    request: dict[str, Any] = Field(default_factory=dict)


def create_agi_control_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/agi-control",
        tags=["agentic-intelligence-control"],
    )

    @router.get("/health")
    def health():
        return {
            "architecture": "agentic_general_intelligence_control_plane",
            "human_level_agi_claimed": False,
            "asi_claimed": False,
            "mode": "OBSERVE",
            "execution_authority": "none",
            "consequential_autonomy": False,
            "private_chain_of_thought_persisted": False,
        }

    @router.post("/readiness/preview")
    def readiness(req: AgiReadinessRequest):
        return assess_agi_layer_readiness(req.evidence)

    @router.post("/cognitive-packet/preview")
    def cognitive_packet(req: CognitivePacketRequest):
        try:
            return build_cognitive_packet(
                task_id=req.task_id,
                goal=req.goal,
                evidence_refs=req.evidence_refs,
                world_state_ref=req.world_state_ref,
                memory_refs=req.memory_refs,
                options=req.options,
                selected_option_id=req.selected_option_id,
                constraints=req.constraints,
                verifier=req.verifier,
                policy=req.policy,
                authority_mode=req.authority_mode,
                side_effect_class=req.side_effect_class,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/learning/preview")
    def learning_preview(req: LearningCandidateRequest):
        return review_learning_candidate(req.candidate)

    @router.post("/memory/query/preview")
    def memory_query(req: MemoryQueryRequest):
        try:
            return build_memory_query(
                task_type=req.task_type,
                task_id=req.task_id,
                entity_refs=req.entity_refs,
                topic_keys=req.topic_keys,
                max_items_per_type=req.max_items_per_type,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/memory/item/review")
    def memory_item_review(req: MemoryItemReviewRequest):
        return review_memory_item(req.item)

    @router.get("/capabilities")
    def capabilities():
        return capability_registry()

    @router.post("/capabilities/review")
    def capability_review(req: CapabilityReviewRequest):
        return review_capability_request(req.request)

    return router
