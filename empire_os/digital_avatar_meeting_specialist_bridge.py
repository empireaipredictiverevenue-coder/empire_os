"""Internal specialist advisory bridge for one visible Digital Avatar voice."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from empire_os.digital_avatar_turn import AvatarClaimTruth


@dataclass(frozen=True)
class AvatarSpecialistAdvisory:
    domain: str
    source_component: str
    summary: str
    truth_class: AvatarClaimTruth
    evidence_refs: tuple[str, ...]
    available: bool = True
    blockers: tuple[str, ...] = ()
    execution_authority: str = "none"
    external_action_performed: bool = False
    commercial_authority: str = "none"
    financial_authority: str = "none"
    private_chain_of_thought_persisted: bool = False

    def validate(self) -> None:
        if not self.domain.strip() or not self.source_component.strip():
            raise ValueError("specialist domain and source_component required")
        if self.available:
            if not self.summary.strip():
                raise ValueError("available specialist summary required")
            if not tuple(ref for ref in self.evidence_refs if str(ref).strip()):
                raise ValueError("available specialist evidence refs required")
        elif not self.blockers:
            raise ValueError("unavailable specialist requires blockers")
        if self.execution_authority != "none":
            raise ValueError("specialist execution authority forbidden")
        if self.external_action_performed:
            raise ValueError("specialist external action forbidden")
        if self.commercial_authority != "none":
            raise ValueError("specialist commercial authority forbidden")
        if self.financial_authority != "none":
            raise ValueError("specialist financial authority forbidden")
        if self.private_chain_of_thought_persisted:
            raise ValueError("specialist private chain-of-thought forbidden")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        value = asdict(self)
        value["truth_class"] = self.truth_class.value
        return value
@dataclass(frozen=True)
class AvatarMeetingAdvisoryPacket:
    meeting_id: str
    avatar_id: str
    required_domains: tuple[str, ...]
    advisories: tuple[AvatarSpecialistAdvisory, ...]
    unresolved_domains: tuple[str, ...]
    response_context_ready: bool
    single_visible_avatar: bool = True
    specialist_speech_execution_allowed: bool = False
    meeting_provider_call_performed: bool = False
    inference_performed: bool = False
    inference_provider_key: str | None = None
    external_action_performed: bool = False
    commercial_authority: str = "none"
    financial_authority: str = "none"
    execution_authority: str = "none"

    @property
    def provider_call_performed(self) -> bool:
        """Backward-compatible alias for meeting-provider activity."""
        return self.meeting_provider_call_performed

    def as_dict(self) -> dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "avatar_id": self.avatar_id,
            "required_domains": list(self.required_domains),
            "advisories": [
                advisory.as_dict()
                for advisory in self.advisories
            ],
            "unresolved_domains": list(self.unresolved_domains),
            "response_context_ready": self.response_context_ready,
            "single_visible_avatar": self.single_visible_avatar,
            "specialist_speech_execution_allowed": (
                self.specialist_speech_execution_allowed
            ),
            "provider_call_performed": self.provider_call_performed,
            "meeting_provider_call_performed": (
                self.meeting_provider_call_performed
            ),
            "inference_performed": self.inference_performed,
            "inference_provider_key": self.inference_provider_key,
            "external_action_performed": self.external_action_performed,
            "commercial_authority": self.commercial_authority,
            "financial_authority": self.financial_authority,
            "execution_authority": self.execution_authority,
        }
def _domain(value: str) -> str:
    return str(value or "").strip().lower()


def build_avatar_meeting_advisory_packet(
    *,
    meeting_id: str,
    avatar_id: str,
    required_domains: Iterable[str],
    advisories: Iterable[AvatarSpecialistAdvisory],
    inference_performed: bool = False,
    inference_provider_key: str | None = None,
) -> AvatarMeetingAdvisoryPacket:
    clean_meeting = str(meeting_id or "").strip()
    clean_avatar = str(avatar_id or "").strip()
    if not clean_meeting or not clean_avatar:
        raise ValueError("meeting_id and avatar_id required")

    requested = tuple(_domain(value) for value in required_domains)
    if not requested or any(not value for value in requested):
        raise ValueError("required specialist domains required")
    if len(requested) != len(set(requested)):
        raise ValueError("required specialist domains must be unique")
    requested_set = frozenset(requested)
    provider_key = str(inference_provider_key or "").strip() or None
    if inference_performed and provider_key is None:
        raise ValueError("specialist inference provider key required")
    if not inference_performed and provider_key is not None:
        raise ValueError("specialist inference provider without inference")

    by_domain: dict[str, AvatarSpecialistAdvisory] = {}
    for advisory in advisories:
        advisory.validate()
        domain = _domain(advisory.domain)
        if domain not in requested_set:
            raise ValueError("unrequested specialist domain")
        if domain in by_domain:
            raise ValueError("specialist_owner_ambiguous")
        by_domain[domain] = advisory
    unresolved = tuple(
        sorted(
            domain
            for domain in requested_set
            if domain not in by_domain
            or by_domain[domain].available is not True
        )
    )
    ordered = tuple(
        by_domain[domain]
        for domain in sorted(by_domain)
    )

    return AvatarMeetingAdvisoryPacket(
        meeting_id=clean_meeting,
        avatar_id=clean_avatar,
        required_domains=tuple(sorted(requested_set)),
        advisories=ordered,
        unresolved_domains=unresolved,
        response_context_ready=not unresolved,
        inference_performed=bool(inference_performed),
        inference_provider_key=provider_key,
    )
