"""Tenant/avatar-scoped continuity projection for Digital Avatar clone fleets."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from empire_os.digital_avatar_fleet import AvatarFleetRuntimeBinding
from empire_os.digital_avatar_meeting_outcome import AvatarMeetingOutcomePacket
from empire_os.saas_scale import TenantMembership


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("continuity source observed_at must include timezone")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class AvatarFleetContinuitySource:
    tenant_id: str
    avatar_id: str
    observed_at: datetime
    source_ref: str
    outcome: AvatarMeetingOutcomePacket

    def validate(self) -> None:
        if not self.tenant_id.strip() or not self.avatar_id.strip():
            raise ValueError("continuity source tenant/avatar required")
        if not self.source_ref.strip():
            raise ValueError("continuity source_ref required")
        _utc(self.observed_at)
        if self.outcome.avatar_id != self.avatar_id:
            raise ValueError("continuity source/outcome avatar mismatch")
        if self.outcome.private_to_owner is not True:
            raise ValueError("continuity outcome must remain private")
        if (
            self.outcome.speech_execution
            or self.outcome.commercial_execution
            or self.outcome.payment_execution
        ):
            raise ValueError("continuity outcome contains forbidden execution authority")
        if self.outcome.execution_authority != "none":
            raise ValueError("continuity outcome grants forbidden authority")


@dataclass(frozen=True)
class AvatarFleetContinuityEntry:
    meeting_id: str
    account_name: str
    observed_at: str
    conversation_id: str | None
    opportunity_id: str | None
    lifecycle_status: str | None
    buyer_utterance_count: int
    close_ready_at_end: bool
    human_takeover_required: bool
    follow_up_review_recommended: bool
    predictive_revenue_refresh_recommended: bool
    buyer_evidence_refs: tuple[str, ...]
    verification_refs: tuple[str, ...]
    commercial_proof_eligible: bool
    truth_class: str = "OBSERVED"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
@dataclass(frozen=True)
class AvatarFleetContinuityMemory:
    tenant_id: str
    avatar_id: str
    owner_name: str
    entries: tuple[AvatarFleetContinuityEntry, ...]
    conversation_ids: tuple[str, ...]
    opportunity_ids: tuple[str, ...]
    follow_up_review_count: int
    human_takeover_count: int
    commercial_proof_eligible_count: int
    source_count: int
    mode: str = "OBSERVE"
    truth_class: str = "OBSERVED_CONTINUITY"
    private_to_owner: bool = True
    raw_transcript_included: bool = False
    raw_audio_included: bool = False
    model_inference_performed: bool = False
    canonical_write_performed: bool = False
    speech_execution_allowed: bool = False
    commercial_execution_allowed: bool = False
    payment_execution_allowed: bool = False
    revenue_recognition_allowed: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _validate_runtime(
    *,
    membership: TenantMembership,
    runtime: AvatarFleetRuntimeBinding,
) -> None:
    membership.validate()
    if not membership.can("operate"):
        raise PermissionError("membership_operate_permission_denied")
    if membership.tenant_id != runtime.tenant_id:
        raise PermissionError("continuity_membership_runtime_tenant_mismatch")
    if membership.user_id != runtime.membership_user_id:
        raise PermissionError("continuity_membership_runtime_user_mismatch")
    if runtime.runtime_authority != "observe":
        raise ValueError("continuity runtime authority must remain observe")
    if runtime.execution_authority != "none":
        raise ValueError("continuity runtime execution authority must remain none")
    if (
        runtime.speech_execution_allowed
        or runtime.commercial_execution_allowed
        or runtime.payment_execution_allowed
        or runtime.revenue_recognition_allowed
    ):
        raise ValueError("continuity runtime contains forbidden authority")
def build_avatar_fleet_continuity_memory(
    *,
    membership: TenantMembership,
    runtime: AvatarFleetRuntimeBinding,
    sources: Iterable[AvatarFleetContinuitySource],
    max_entries: int = 20,
) -> AvatarFleetContinuityMemory:
    _validate_runtime(membership=membership, runtime=runtime)
    if max_entries < 1 or max_entries > 100:
        raise ValueError("max_entries must be between 1 and 100")

    rows = tuple(sources)
    for source in rows:
        source.validate()
        if (
            source.avatar_id == runtime.avatar_id
            and source.tenant_id != runtime.tenant_id
        ):
            raise ValueError("avatar_memory_cross_tenant_conflict")

    own = tuple(
        source
        for source in rows
        if source.tenant_id == runtime.tenant_id
        and source.avatar_id == runtime.avatar_id
    )
    ordered = sorted(
        own,
        key=lambda source: (
            -_utc(source.observed_at).timestamp(),
            source.outcome.meeting_id,
            source.source_ref,
        ),
    )[:max_entries]

    entries: list[AvatarFleetContinuityEntry] = []
    for source in ordered:
        outcome = source.outcome
        proof_eligible = bool(
            outcome.verified_commercial_outcome
            and outcome.cortex_customer_label_eligible
        )
        entries.append(
            AvatarFleetContinuityEntry(
                meeting_id=outcome.meeting_id,
                account_name=outcome.account_name,
                observed_at=_utc(source.observed_at).isoformat(),
                conversation_id=outcome.conversation_id,
                opportunity_id=outcome.opportunity_id,
                lifecycle_status=outcome.lifecycle_status,
                buyer_utterance_count=outcome.buyer_utterance_count,
                close_ready_at_end=outcome.close_ready_at_end,
                human_takeover_required=outcome.human_takeover_required,
                follow_up_review_recommended=(
                    outcome.follow_up_review_recommended
                ),
                predictive_revenue_refresh_recommended=(
                    outcome.predictive_revenue_refresh_recommended
                ),
                buyer_evidence_refs=outcome.buyer_evidence_refs,
                verification_refs=outcome.verification_refs,
                commercial_proof_eligible=proof_eligible,
            )
        )

    conversation_ids = tuple(dict.fromkeys(
        entry.conversation_id
        for entry in entries
        if entry.conversation_id
    ))
    opportunity_ids = tuple(dict.fromkeys(
        entry.opportunity_id
        for entry in entries
        if entry.opportunity_id
    ))

    return AvatarFleetContinuityMemory(
        tenant_id=runtime.tenant_id,
        avatar_id=runtime.avatar_id,
        owner_name=runtime.owner_name,
        entries=tuple(entries),
        conversation_ids=conversation_ids,
        opportunity_ids=opportunity_ids,
        follow_up_review_count=sum(
            entry.follow_up_review_recommended
            for entry in entries
        ),
        human_takeover_count=sum(
            entry.human_takeover_required
            for entry in entries
        ),
        commercial_proof_eligible_count=sum(
            entry.commercial_proof_eligible
            for entry in entries
        ),
        source_count=len(entries),
    )
