"""OBSERVE-only Empire Digital Avatar domain foundation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class AvatarMeetingMode(str, Enum):
    SHADOW = "shadow"
    COPILOT = "copilot"
    REPRESENT = "represent"
    NEGOTIATE = "negotiate"
    CLOSE = "close"


class AvatarAction(str, Enum):
    PREPARE_RESPONSE = "prepare_response"
    SPEAK = "speak"
    QUOTE = "quote"
    NEGOTIATE = "negotiate"
    CLOSE = "close"
    ACCEPT_TERMS = "accept_terms"
    PAYMENT_REQUEST = "payment_request"
    SEND_FOLLOW_UP = "send_follow_up"
    MOVE_FUNDS = "move_funds"


@dataclass(frozen=True)
class DigitalAvatarIdentity:
    avatar_id: str
    owner_name: str
    display_name: str
    organisation_name: str
    disclosure_text: str
    owner_consent_evidence_ref: str
    voice_profile_ref: str | None = None
    visual_profile_ref: str | None = None

    def validate(self) -> None:
        required = (
            self.avatar_id,
            self.owner_name,
            self.display_name,
            self.organisation_name,
            self.disclosure_text,
            self.owner_consent_evidence_ref,
        )
        if not all(str(value).strip() for value in required):
            raise ValueError("avatar identity and owner consent evidence required")
        if "ai" not in self.disclosure_text.lower():
            raise ValueError("avatar disclosure must explicitly identify AI")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AvatarAuthorityEnvelope:
    can_answer_business_questions: bool = True
    can_quote_verified_price: bool = False
    can_negotiate: bool = False
    can_close_within_terms: bool = False
    can_prepare_follow_up: bool = True
    max_discount_bps: int = 0

    def validate(self) -> None:
        if not 0 <= self.max_discount_bps <= 10_000:
            raise ValueError("max_discount_bps must be between 0 and 10000")
        if self.can_negotiate and not self.can_quote_verified_price:
            raise ValueError("negotiation requires verified-price authority")
        if self.can_close_within_terms and not self.can_negotiate:
            raise ValueError("close authority requires negotiation authority")


@dataclass(frozen=True)
class AvatarMeetingSession:
    meeting_id: str
    avatar_id: str
    provider: str
    mode: AvatarMeetingMode
    disclosure_announced: bool = False
    participant_refs: tuple[str, ...] = ()


    def validate(self) -> None:
        if not self.meeting_id.strip() or not self.avatar_id.strip():
            raise ValueError("meeting_id and avatar_id required")
        if not self.provider.strip():
            raise ValueError("meeting provider required")


@dataclass(frozen=True)
class AvatarCommercialContext:
    opportunity_id: str | None = None
    verified_price_cents: int | None = None
    proposed_discount_bps: int = 0
    commercial_terms_verified: bool = False
    evidence_refs: tuple[str, ...] = ()

    def validate(self) -> None:
        if self.verified_price_cents is not None and self.verified_price_cents <= 0:
            raise ValueError("verified_price_cents must be positive when present")
        if not 0 <= self.proposed_discount_bps <= 10_000:
            raise ValueError("proposed_discount_bps must be between 0 and 10000")


@dataclass(frozen=True)
class AvatarActionDecision:
    action: AvatarAction
    allowed: bool
    founder_gate_required: bool
    blockers: tuple[str, ...]
    execution_authority: str = "none"
    side_effects: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["action"] = self.action.value
        return data


_EXTERNAL_ACTIONS = {
    AvatarAction.SPEAK,
    AvatarAction.QUOTE,
    AvatarAction.NEGOTIATE,
    AvatarAction.CLOSE,
    AvatarAction.ACCEPT_TERMS,
    AvatarAction.PAYMENT_REQUEST,
    AvatarAction.SEND_FOLLOW_UP,
    AvatarAction.MOVE_FUNDS,
}


def evaluate_avatar_action(
    *,
    identity: DigitalAvatarIdentity,
    authority: AvatarAuthorityEnvelope,
    session: AvatarMeetingSession,
    action: AvatarAction,
    commercial: AvatarCommercialContext | None = None,
    runtime_authority: str = "observe",
) -> AvatarActionDecision:
    identity.validate()
    authority.validate()
    session.validate()
    commercial = commercial or AvatarCommercialContext()
    commercial.validate()
    if runtime_authority.strip().lower() != "observe":
        raise ValueError("Digital Avatar V1 runtime authority is OBSERVE only")

    blockers: list[str] = []
    founder_gate_required = action in {
        AvatarAction.ACCEPT_TERMS,
        AvatarAction.PAYMENT_REQUEST,
        AvatarAction.MOVE_FUNDS,
    }


    if session.avatar_id != identity.avatar_id:
        blockers.append("avatar_session_identity_mismatch")
    if action in _EXTERNAL_ACTIONS and not session.disclosure_announced:
        blockers.append("ai_disclosure_not_announced")

    if action == AvatarAction.SPEAK and session.mode == AvatarMeetingMode.SHADOW:
        blockers.append("shadow_mode_cannot_speak")
    if action == AvatarAction.QUOTE:
        if session.mode not in {
            AvatarMeetingMode.REPRESENT,
            AvatarMeetingMode.NEGOTIATE,
            AvatarMeetingMode.CLOSE,
        }:
            blockers.append("meeting_mode_cannot_quote")
        if not authority.can_quote_verified_price:
            blockers.append("verified_price_authority_missing")
        if commercial.verified_price_cents is None:
            blockers.append("verified_commercial_price_missing")
    if action == AvatarAction.NEGOTIATE:
        if session.mode not in {AvatarMeetingMode.NEGOTIATE, AvatarMeetingMode.CLOSE}:
            blockers.append("meeting_mode_cannot_negotiate")
        if not authority.can_negotiate:
            blockers.append("negotiation_authority_missing")
        if commercial.proposed_discount_bps > authority.max_discount_bps:
            blockers.append("discount_exceeds_delegated_limit")


    if action == AvatarAction.CLOSE:
        if session.mode != AvatarMeetingMode.CLOSE:
            blockers.append("meeting_mode_cannot_close")
        if not authority.can_close_within_terms:
            blockers.append("close_authority_missing")
        if not commercial.commercial_terms_verified:
            blockers.append("verified_commercial_terms_missing")
    if action == AvatarAction.SEND_FOLLOW_UP and not authority.can_prepare_follow_up:
        blockers.append("follow_up_authority_missing")

    if founder_gate_required:
        blockers.append("founder_gate_required_v1")
    if action in _EXTERNAL_ACTIONS:
        blockers.append("runtime_observe_only")

    ordered = tuple(sorted(set(blockers)))
    return AvatarActionDecision(
        action=action,
        allowed=not ordered,
        founder_gate_required=founder_gate_required,
        blockers=ordered,
    )
