"""Read/preview API for Empire Digital Avatar V1."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from empire_os.digital_avatar import (
    AvatarAction,
    AvatarAuthorityEnvelope,
    AvatarCommercialContext,
    AvatarMeetingMode,
    AvatarMeetingSession,
    DigitalAvatarIdentity,
    evaluate_avatar_action,
)
from empire_os.digital_avatar_copilot import build_avatar_copilot_handoff
from empire_os.digital_avatar_authority import (
    AvatarCloseProposal,
    AvatarCommercialAuthorityPolicy,
)
from empire_os.digital_avatar_meeting_memory import build_avatar_meeting_memory
from empire_os.digital_avatar_mode_transition import (
    AvatarModeTransitionEvidence,
    assess_avatar_mode_transition,
)
from empire_os.digital_avatar_response_draft import validate_avatar_response_draft
from empire_os.digital_avatar_response_task import build_realtime_response_task
from empire_os.digital_avatar_shadow import build_shadow_guidance
from empire_os.digital_avatar_strategy import build_avatar_meeting_strategy
from empire_os.digital_avatar_turn import (
    AvatarClaimTruth,
    AvatarTurnClaim,
    AvatarTurnDraft,
    AvatarTurnPurpose,
    assess_avatar_turn_for_approval,
)
from empire_os.recall_meeting_adapter import normalize_verified_recall_event
from empire_os.recall_shadow_bot_plan import build_recall_shadow_bot_plan
from empire_os.recall_shadow_pipeline import (
    RecallVerifiedEvent,
    build_recall_shadow_pipeline_preview,
)
from empire_os.meeting_gateway import (
    MeetingObservation,
    MeetingObservationKind,
    MeetingPlatform,
    MeetingSpeakerRole,
    build_shadow_meeting_state,
)


class AvatarIdentityRequest(BaseModel):
    avatar_id: str
    owner_name: str
    display_name: str
    organisation_name: str
    disclosure_text: str
    owner_consent_evidence_ref: str
    voice_profile_ref: str | None = None
    visual_profile_ref: str | None = None


class AvatarAuthorityRequest(BaseModel):
    can_answer_business_questions: bool = True
    can_quote_verified_price: bool = False
    can_negotiate: bool = False
    can_close_within_terms: bool = False
    can_prepare_follow_up: bool = True
    max_discount_bps: int = Field(default=0, ge=0, le=10000)


class AvatarSessionRequest(BaseModel):
    meeting_id: str
    avatar_id: str
    provider: str
    mode: AvatarMeetingMode
    disclosure_announced: bool = False
    participant_refs: list[str] = Field(default_factory=list)


class AvatarCommercialRequest(BaseModel):
    opportunity_id: str | None = None
    verified_price_cents: int | None = Field(default=None, gt=0)
    proposed_discount_bps: int = Field(default=0, ge=0, le=10000)
    commercial_terms_verified: bool = False
    evidence_refs: list[str] = Field(default_factory=list)


class AvatarModeTransitionPreviewRequest(BaseModel):
    session: AvatarSessionRequest
    target_mode: AvatarMeetingMode
    owner_approval_evidence_ref: str | None = None
    delegated_authority_evidence_ref: str | None = None
    commercial_terms_evidence_ref: str | None = None


class AvatarActionPreviewRequest(BaseModel):
    identity: AvatarIdentityRequest
    authority: AvatarAuthorityRequest = Field(default_factory=AvatarAuthorityRequest)
    session: AvatarSessionRequest
    action: AvatarAction
    commercial: AvatarCommercialRequest = Field(default_factory=AvatarCommercialRequest)


class AvatarStrategyPreviewRequest(BaseModel):
    identity: AvatarIdentityRequest
    session: AvatarSessionRequest
    account_name: str
    objective: str
    buyer_signal_summary: str | None = None
    buyer_signal_evidence_refs: list[str] = Field(default_factory=list)
    proof_refs: list[str] = Field(default_factory=list)
    commercial_terms_ref: str | None = None
    predictive_inputs: dict = Field(default_factory=dict)
    action_candidates: list[dict] = Field(default_factory=list)


class MeetingObservationRequest(BaseModel):
    meeting_id: str
    external_meeting_id: str
    platform: MeetingPlatform
    provider_event_id: str
    kind: MeetingObservationKind
    occurred_at: str
    evidence_ref: str
    speaker_ref: str | None = None
    speaker_name: str | None = None
    speaker_role: MeetingSpeakerRole = MeetingSpeakerRole.UNKNOWN
    text: str | None = None
    is_final: bool = True


class RecallEventPreviewRequest(BaseModel):
    meeting_id: str
    platform: MeetingPlatform
    payload: dict
    received_at: str
    verified: bool = False
    participant_roles: dict[str, MeetingSpeakerRole | str] = Field(default_factory=dict)


class RecallVerifiedEventRequest(BaseModel):
    payload: dict
    received_at: str
    verified: bool = False


class RecallShadowPipelinePreviewRequest(BaseModel):
    identity: AvatarIdentityRequest
    session: AvatarSessionRequest
    platform: MeetingPlatform
    events: list[RecallVerifiedEventRequest]
    participant_roles: dict[str, MeetingSpeakerRole | str] = Field(default_factory=dict)
    account_name: str
    objective: str
    proof_refs: list[str] = Field(default_factory=list)
    commercial_terms_ref: str | None = None
    predictive_inputs: dict = Field(default_factory=dict)
    action_candidates: list[dict] = Field(default_factory=list)
    commercial_policy: AvatarCommercialPolicyRequest | None = None
    close_proposal: AvatarCloseProposalRequest | None = None


class RecallShadowBotPlanRequest(BaseModel):
    meeting_id: str
    avatar_id: str
    platform: MeetingPlatform
    bot_name: str
    meeting_url: str
    realtime_webhook_url: str
    recording_consent_evidence_ref: str
    webhook_verification_evidence_ref: str
    join_at: str | None = None


class AvatarTurnClaimRequest(BaseModel):
    text: str
    truth_class: AvatarClaimTruth
    evidence_refs: list[str] = Field(default_factory=list)


class AvatarTurnApprovalPreviewRequest(BaseModel):
    session: AvatarSessionRequest
    purpose: AvatarTurnPurpose
    text: str
    claims: list[AvatarTurnClaimRequest] = Field(default_factory=list)
    strategy_evidence_refs: list[str] = Field(default_factory=list)
    commercial_authority: dict | None = None


class AvatarCopilotHandoffPreviewRequest(AvatarTurnApprovalPreviewRequest):
    identity: AvatarIdentityRequest


class AvatarCommercialPolicyRequest(BaseModel):
    allowed_product_codes: list[str]
    approved_terms_refs: list[str]
    allowed_currencies: list[str] = Field(default_factory=lambda: ["USD"])
    max_discount_bps: int = Field(default=0, ge=0, le=10000)
    max_contract_months: int = Field(default=1, gt=0)


class AvatarCloseProposalRequest(BaseModel):
    product_code: str
    list_price_cents: int = Field(gt=0)
    proposed_price_cents: int = Field(gt=0)
    currency: str
    contract_months: int = Field(gt=0)
    terms_ref: str
    evidence_refs: list[str] = Field(default_factory=list)


class AvatarMeetingMemoryPreviewRequest(BaseModel):
    session: AvatarSessionRequest
    observations: list[MeetingObservationRequest] = Field(default_factory=list)


class AvatarResponseTaskPreviewRequest(BaseModel):
    identity: AvatarIdentityRequest
    session: AvatarSessionRequest
    observations: list[MeetingObservationRequest] = Field(default_factory=list)
    account_name: str
    objective: str
    proof_refs: list[str] = Field(default_factory=list)
    commercial_terms_ref: str | None = None
    predictive_inputs: dict = Field(default_factory=dict)
    action_candidates: list[dict] = Field(default_factory=list)
    additional_evidence_refs: list[str] = Field(default_factory=list)


class AvatarResponseDraftValidationRequest(AvatarResponseTaskPreviewRequest):
    draft_payload: dict
    provider_key: str
    source_ref: str


class AvatarShadowPreviewRequest(BaseModel):
    identity: AvatarIdentityRequest
    session: AvatarSessionRequest
    observations: list[MeetingObservationRequest] = Field(default_factory=list)
    account_name: str
    objective: str
    proof_refs: list[str] = Field(default_factory=list)
    commercial_terms_ref: str | None = None
    predictive_inputs: dict = Field(default_factory=dict)
    action_candidates: list[dict] = Field(default_factory=list)
    commercial_policy: AvatarCommercialPolicyRequest | None = None
    close_proposal: AvatarCloseProposalRequest | None = None


def _identity(req: AvatarIdentityRequest) -> DigitalAvatarIdentity:
    return DigitalAvatarIdentity(**req.model_dump())


def _session(req: AvatarSessionRequest) -> AvatarMeetingSession:
    data = req.model_dump()
    data["participant_refs"] = tuple(data["participant_refs"])
    return AvatarMeetingSession(**data)


def _authority(req: AvatarAuthorityRequest) -> AvatarAuthorityEnvelope:
    return AvatarAuthorityEnvelope(**req.model_dump())


def _commercial(req: AvatarCommercialRequest) -> AvatarCommercialContext:
    data = req.model_dump()
    data["evidence_refs"] = tuple(data["evidence_refs"])
    return AvatarCommercialContext(**data)


def _observation(req: MeetingObservationRequest) -> MeetingObservation:
    return MeetingObservation(**req.model_dump())


def _commercial_policy(
    req: AvatarCommercialPolicyRequest | None,
) -> AvatarCommercialAuthorityPolicy | None:
    if req is None:
        return None
    data = req.model_dump()
    data["allowed_product_codes"] = tuple(data["allowed_product_codes"])
    data["approved_terms_refs"] = tuple(data["approved_terms_refs"])
    data["allowed_currencies"] = tuple(data["allowed_currencies"])
    return AvatarCommercialAuthorityPolicy(**data)


def _close_proposal(
    req: AvatarCloseProposalRequest | None,
) -> AvatarCloseProposal | None:
    if req is None:
        return None
    data = req.model_dump()
    data["evidence_refs"] = tuple(data["evidence_refs"])
    return AvatarCloseProposal(**data)


def _turn_draft(req: AvatarTurnApprovalPreviewRequest) -> AvatarTurnDraft:
    session = _session(req.session)
    claims = tuple(
        AvatarTurnClaim(
            text=row.text,
            truth_class=row.truth_class,
            evidence_refs=tuple(row.evidence_refs),
        )
        for row in req.claims
    )
    return AvatarTurnDraft(
        meeting_id=session.meeting_id,
        avatar_id=session.avatar_id,
        purpose=req.purpose,
        text=req.text,
        claims=claims,
        strategy_evidence_refs=tuple(req.strategy_evidence_refs),
    )


def create_digital_avatar_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/digital-avatar",
        tags=["digital-avatar"],
    )

    @router.get("/health")
    def health():
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "meeting_transport_active": False,
            "speech_execution": False,
            "negotiation_execution": False,
            "close_execution": False,
            "payment_execution": False,
            "execution_authority": "none",
        }

    @router.post("/providers/recall/event/preview")
    def recall_event_preview(req: RecallEventPreviewRequest):
        try:
            observation = normalize_verified_recall_event(
                meeting_id=req.meeting_id,
                platform=req.platform,
                payload=req.payload,
                received_at=req.received_at,
                verified=req.verified,
                participant_roles=req.participant_roles,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "provider": "recall",
            "webhook_event_verified": req.verified is True,
            "persistence_performed": False,
            "meeting_action_execution": False,
            "execution_authority": "none",
            "observation": observation.as_dict(),
        }

    @router.post("/providers/recall/shadow-pipeline/preview")
    def recall_shadow_pipeline_preview(req: RecallShadowPipelinePreviewRequest):
        try:
            preview = build_recall_shadow_pipeline_preview(
                identity=_identity(req.identity),
                session=_session(req.session),
                platform=req.platform,
                events=[
                    RecallVerifiedEvent(
                        payload=row.payload,
                        received_at=row.received_at,
                        verified=row.verified,
                    )
                    for row in req.events
                ],
                participant_roles=req.participant_roles,
                account_name=req.account_name,
                objective=req.objective,
                proof_refs=req.proof_refs,
                commercial_terms_ref=req.commercial_terms_ref,
                predictive_inputs=req.predictive_inputs,
                action_candidates=req.action_candidates,
                commercial_policy=_commercial_policy(req.commercial_policy),
                close_proposal=_close_proposal(req.close_proposal),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return preview.as_dict()

    @router.post("/providers/recall/shadow-plan/preview")
    def recall_shadow_plan_preview(req: RecallShadowBotPlanRequest):
        try:
            plan = build_recall_shadow_bot_plan(**req.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "provider": "recall",
            "api_call_allowed": False,
            "live_join_execution": False,
            "execution_authority": "none",
            "plan": plan.as_dict(),
        }

    @router.post("/copilot/handoff/preview")
    def copilot_handoff_preview(req: AvatarCopilotHandoffPreviewRequest):
        try:
            handoff = build_avatar_copilot_handoff(
                identity=_identity(req.identity),
                session=_session(req.session),
                draft=_turn_draft(req),
                commercial_authority=req.commercial_authority,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "human_approval_required": True,
            "transmission_performed": False,
            "speech_execution_allowed": False,
            "execution_authority": "none",
            "handoff": handoff.as_dict(),
        }

    @router.post("/turns/approval/preview")
    def turn_approval_preview(req: AvatarTurnApprovalPreviewRequest):
        try:
            session = _session(req.session)
            decision = assess_avatar_turn_for_approval(
                session=session,
                draft=_turn_draft(req),
                commercial_authority=req.commercial_authority,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "requires_explicit_human_approval": True,
            "speech_execution_allowed": False,
            "execution_authority": "none",
            "decision": decision.as_dict(),
        }

    @router.post("/mode-transition/preview")
    def mode_transition_preview(req: AvatarModeTransitionPreviewRequest):
        try:
            decision = assess_avatar_mode_transition(
                session=_session(req.session),
                target_mode=req.target_mode,
                evidence=AvatarModeTransitionEvidence(
                    owner_approval_evidence_ref=req.owner_approval_evidence_ref,
                    delegated_authority_evidence_ref=(
                        req.delegated_authority_evidence_ref
                    ),
                    commercial_terms_evidence_ref=(
                        req.commercial_terms_evidence_ref
                    ),
                ),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "transition_execution_performed": False,
            "execution_authority": "none",
            "decision": decision.as_dict(),
        }

    @router.post("/actions/preview")
    def action_preview(req: AvatarActionPreviewRequest):
        try:
            decision = evaluate_avatar_action(
                identity=_identity(req.identity),
                authority=_authority(req.authority),
                session=_session(req.session),
                action=req.action,
                commercial=_commercial(req.commercial),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "execution_authority": "none",
            "decision": decision.as_dict(),
        }

    @router.post("/strategy/preview")
    def strategy_preview(req: AvatarStrategyPreviewRequest):
        try:
            packet = build_avatar_meeting_strategy(
                identity=_identity(req.identity),
                session=_session(req.session),
                account_name=req.account_name,
                objective=req.objective,
                buyer_signal_summary=req.buyer_signal_summary,
                buyer_signal_evidence_refs=req.buyer_signal_evidence_refs,

                proof_refs=req.proof_refs,
                commercial_terms_ref=req.commercial_terms_ref,
                predictive_inputs=req.predictive_inputs,
                action_candidates=req.action_candidates,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "execution_authority": "none",
            "strategy": packet.as_dict(),
        }

    @router.post("/meeting/memory/preview")
    def meeting_memory_preview(req: AvatarMeetingMemoryPreviewRequest):
        try:
            memory = build_avatar_meeting_memory(
                session=_session(req.session),
                observations=[_observation(row) for row in req.observations],
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "summary_generated": False,
            "inference_performed": False,
            "persistence_performed": False,
            "execution_authority": "none",
            "memory": memory.as_dict(),
        }

    @router.post("/meeting/response-task/preview")
    def meeting_response_task_preview(req: AvatarResponseTaskPreviewRequest):
        try:
            identity = _identity(req.identity)
            session = _session(req.session)
            memory = build_avatar_meeting_memory(
                session=session,
                observations=[_observation(row) for row in req.observations],
            )
            strategy = build_avatar_meeting_strategy(
                identity=identity,
                session=session,
                account_name=req.account_name,
                objective=req.objective,
                proof_refs=req.proof_refs,
                commercial_terms_ref=req.commercial_terms_ref,
                predictive_inputs=req.predictive_inputs,
                action_candidates=req.action_candidates,
            )
            task = build_realtime_response_task(
                memory=memory,
                strategy=strategy,
                additional_evidence_refs=req.additional_evidence_refs,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "COPILOT_PREVIEW",
            "read_only": True,
            "requires_human_approval": True,
            "speech_execution_allowed": False,
            "execution_authority": "none",
            "response_task": task.as_dict(),
        }

    @router.post("/meeting/response-draft/validate")
    def meeting_response_draft_validate(req: AvatarResponseDraftValidationRequest):
        try:
            identity = _identity(req.identity)
            session = _session(req.session)
            memory = build_avatar_meeting_memory(
                session=session,
                observations=[_observation(row) for row in req.observations],
            )
            strategy = build_avatar_meeting_strategy(
                identity=identity,
                session=session,
                account_name=req.account_name,
                objective=req.objective,
                proof_refs=req.proof_refs,
                commercial_terms_ref=req.commercial_terms_ref,
                predictive_inputs=req.predictive_inputs,
                action_candidates=req.action_candidates,
            )
            task = build_realtime_response_task(
                memory=memory,
                strategy=strategy,
                additional_evidence_refs=req.additional_evidence_refs,
            )
            draft = validate_avatar_response_draft(
                task=task,
                payload=req.draft_payload,
                provider_key=req.provider_key,
                source_ref=req.source_ref,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "COPILOT_PREVIEW",
            "read_only": True,
            "draft_generated_here": False,
            "transmission_performed": False,
            "speech_execution_allowed": False,
            "execution_authority": "none",
            "draft": draft.as_dict(),
        }

    @router.post("/meeting/shadow/preview")
    def meeting_shadow_preview(req: AvatarShadowPreviewRequest):
        try:
            identity = _identity(req.identity)
            session = _session(req.session)
            state = build_shadow_meeting_state(
                session=session,
                observations=[_observation(row) for row in req.observations],
            )
            guidance = build_shadow_guidance(
                identity=identity,
                session=session,
                state=state,
                account_name=req.account_name,
                objective=req.objective,
                proof_refs=req.proof_refs,
                commercial_terms_ref=req.commercial_terms_ref,
                predictive_inputs=req.predictive_inputs,
                action_candidates=req.action_candidates,
                commercial_policy=_commercial_policy(req.commercial_policy),
                close_proposal=_close_proposal(req.close_proposal),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "private_guidance_only": True,
            "meeting_transport_active": False,
            "speech_execution": False,
            "execution_authority": "none",
            "state": state.as_dict(),
            "guidance": guidance.as_dict(),
        }

    return router
