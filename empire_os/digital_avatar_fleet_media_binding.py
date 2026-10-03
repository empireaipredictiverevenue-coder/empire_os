"""Tenant-scoped media identity binding for Digital Avatar clone fleets."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any, Iterable

from empire_os.digital_avatar import DigitalAvatarIdentity
from empire_os.digital_avatar_fleet import AvatarFleetRuntimeBinding
from empire_os.digital_avatar_visual_registry import AvatarVisualRegistration
from empire_os.digital_avatar_voice_registry import AvatarVoiceRegistration


def _media_binding_key(
    *,
    tenant_id: str,
    avatar_id: str,
    voice_profile_ref: str | None,
    voice_profile_sha256: str | None,
    visual_profile_ref: str | None,
    visual_profile_sha256: str | None,
) -> str:
    material = "|".join((
        str(tenant_id or "").strip(),
        str(avatar_id or "").strip(),
        str(voice_profile_ref or ""),
        str(voice_profile_sha256 or ""),
        str(visual_profile_ref or ""),
        str(visual_profile_sha256 or ""),
    ))
    return "avatar-media:" + sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AvatarFleetMediaBinding:
    tenant_id: str
    avatar_id: str
    owner_ref: str
    owner_name: str
    owner_consent_evidence_ref: str
    voice_profile_ref: str | None
    voice_profile_sha256: str | None
    voice_engine: str | None
    engine_voice_id: str | None
    voice_language: str | None
    voice_consent_verified: bool
    visual_profile_ref: str | None
    visual_profile_sha256: str | None
    visual_engine: str | None
    engine_avatar_id: str | None
    visual_target_fps: int | None
    visual_consent_verified: bool
    binding_key: str
    voice_ready: bool
    visual_ready: bool
    multimodal_ready: bool
    media_binding_only: bool = True
    raw_reference_media_included: bool = False
    render_execution: bool = False
    meeting_transmission_authority: bool = False
    speech_execution_allowed: bool = False
    visual_execution_allowed: bool = False
    commercial_execution_allowed: bool = False
    payment_execution_allowed: bool = False
    revenue_recognition_allowed: bool = False
    execution_authority: str = "none"

    def validate(self) -> None:
        if not self.tenant_id.strip() or not self.avatar_id.strip():
            raise ValueError("fleet media tenant/avatar required")
        if (
            not self.owner_ref.strip()
            or not self.owner_name.strip()
            or not self.owner_consent_evidence_ref.strip()
        ):
            raise ValueError("fleet media owner consent required")
        if not self.binding_key.strip():
            raise ValueError("fleet media binding key required")
        expected_key = _media_binding_key(
            tenant_id=self.tenant_id,
            avatar_id=self.avatar_id,
            voice_profile_ref=self.voice_profile_ref,
            voice_profile_sha256=self.voice_profile_sha256,
            visual_profile_ref=self.visual_profile_ref,
            visual_profile_sha256=self.visual_profile_sha256,
        )
        if self.binding_key != expected_key:
            raise ValueError("fleet media binding key mismatch")
        if self.voice_profile_ref and not str(self.engine_voice_id or "").strip():
            raise ValueError("fleet media voice engine identity required")
        if self.visual_profile_ref and not str(self.engine_avatar_id or "").strip():
            raise ValueError("fleet media visual engine identity required")
        if self.voice_ready != bool(self.voice_profile_ref):
            raise ValueError("fleet media voice readiness invariant violated")
        if self.visual_ready != bool(self.visual_profile_ref):
            raise ValueError("fleet media visual readiness invariant violated")
        if self.multimodal_ready != (self.voice_ready and self.visual_ready):
            raise ValueError("fleet media multimodal readiness invariant violated")
        if self.voice_profile_ref is None and self.visual_profile_ref is None:
            raise ValueError("fleet media requires voice or visual registration")
        if (
            self.media_binding_only is not True
            or self.raw_reference_media_included
            or self.render_execution
            or self.meeting_transmission_authority
            or self.speech_execution_allowed
            or self.visual_execution_allowed
            or self.commercial_execution_allowed
            or self.payment_execution_allowed
            or self.revenue_recognition_allowed
            or self.execution_authority != "none"
        ):
            raise ValueError("fleet media binding grants forbidden authority")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


def _validate_runtime_identity(
    *,
    runtime: AvatarFleetRuntimeBinding,
    identity: DigitalAvatarIdentity,
) -> None:
    identity.validate()
    if runtime.tenant_id.strip() == "":
        raise ValueError("fleet media runtime tenant required")
    if runtime.avatar_id != identity.avatar_id:
        raise PermissionError("fleet media runtime/identity avatar mismatch")
    if runtime.owner_name.strip() != identity.owner_name.strip():
        raise PermissionError("fleet media runtime/identity owner mismatch")
    if (
        runtime.owner_consent_evidence_ref.strip()
        != identity.owner_consent_evidence_ref.strip()
    ):
        raise PermissionError("fleet media runtime/identity consent mismatch")
    if runtime.runtime_authority != "observe" or runtime.execution_authority != "none":
        raise ValueError("fleet media runtime authority invalid")
    if (
        runtime.speech_execution_allowed
        or runtime.commercial_execution_allowed
        or runtime.payment_execution_allowed
        or runtime.revenue_recognition_allowed
    ):
        raise ValueError("fleet media runtime grants forbidden authority")


def _voice_fields(
    *,
    identity: DigitalAvatarIdentity,
    registration: AvatarVoiceRegistration | None,
) -> tuple[
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    bool,
]:
    declared = str(identity.voice_profile_ref or "").strip() or None
    if declared is None:
        if registration is not None:
            raise ValueError("voice registration supplied without identity profile ref")
        return None, None, None, None, None, False
    if registration is None:
        raise ValueError("declared voice profile registration missing")
    if registration.profile_ref != declared:
        raise ValueError("fleet media voice profile ref mismatch")
    if registration.avatar_id != identity.avatar_id:
        raise ValueError("fleet media voice avatar mismatch")
    if registration.owner_consent_evidence_ref != identity.owner_consent_evidence_ref:
        raise ValueError("fleet media voice owner consent mismatch")
    if not registration.voice_consent_evidence_ref.strip():
        raise ValueError("fleet media voice consent evidence missing")
    if not registration.profile_sha256.strip():
        raise ValueError("fleet media voice profile hash missing")
    if registration.raw_reference_media_stored is not False:
        raise ValueError("fleet media voice raw-media invariant violated")
    if registration.meeting_transmission_authority is not False:
        raise ValueError("fleet media voice transmission authority forbidden")
    if registration.execution_authority != "none":
        raise ValueError("fleet media voice execution authority forbidden")
    return (
        registration.profile_ref,
        registration.profile_sha256,
        registration.preferred_engine,
        registration.engine_voice_id,
        registration.language,
        True,
    )


def _visual_fields(
    *,
    identity: DigitalAvatarIdentity,
    registration: AvatarVisualRegistration | None,
) -> tuple[
    str | None,
    str | None,
    str | None,
    str | None,
    int | None,
    bool,
]:
    declared = str(identity.visual_profile_ref or "").strip() or None
    if declared is None:
        if registration is not None:
            raise ValueError("visual registration supplied without identity profile ref")
        return None, None, None, None, None, False
    if registration is None:
        raise ValueError("declared visual profile registration missing")
    if registration.profile_ref != declared:
        raise ValueError("fleet media visual profile ref mismatch")
    if registration.avatar_id != identity.avatar_id:
        raise ValueError("fleet media visual avatar mismatch")
    if registration.owner_consent_evidence_ref != identity.owner_consent_evidence_ref:
        raise ValueError("fleet media visual owner consent mismatch")
    if not registration.visual_consent_evidence_ref.strip():
        raise ValueError("fleet media visual consent evidence missing")
    if not registration.profile_sha256.strip():
        raise ValueError("fleet media visual profile hash missing")
    if registration.raw_reference_media_stored is not False:
        raise ValueError("fleet media visual raw-media invariant violated")
    if registration.meeting_transmission_authority is not False:
        raise ValueError("fleet media visual transmission authority forbidden")
    if registration.execution_authority != "none":
        raise ValueError("fleet media visual execution authority forbidden")
    return (
        registration.profile_ref,
        registration.profile_sha256,
        registration.preferred_engine,
        registration.engine_avatar_id,
        registration.target_fps,
        True,
    )


def bind_avatar_fleet_media(
    *,
    runtime: AvatarFleetRuntimeBinding,
    identity: DigitalAvatarIdentity,
    voice_registration: AvatarVoiceRegistration | None = None,
    visual_registration: AvatarVisualRegistration | None = None,
) -> AvatarFleetMediaBinding:
    _validate_runtime_identity(runtime=runtime, identity=identity)
    voice = _voice_fields(identity=identity, registration=voice_registration)
    visual = _visual_fields(identity=identity, registration=visual_registration)

    binding_key = _media_binding_key(
        tenant_id=runtime.tenant_id,
        avatar_id=runtime.avatar_id,
        voice_profile_ref=voice[0],
        voice_profile_sha256=voice[1],
        visual_profile_ref=visual[0],
        visual_profile_sha256=visual[1],
    )

    binding = AvatarFleetMediaBinding(
        tenant_id=runtime.tenant_id,
        avatar_id=runtime.avatar_id,
        owner_ref=runtime.owner_ref,
        owner_name=runtime.owner_name,
        owner_consent_evidence_ref=runtime.owner_consent_evidence_ref,
        voice_profile_ref=voice[0],
        voice_profile_sha256=voice[1],
        voice_engine=voice[2],
        engine_voice_id=voice[3],
        voice_language=voice[4],
        voice_consent_verified=voice[5],
        visual_profile_ref=visual[0],
        visual_profile_sha256=visual[1],
        visual_engine=visual[2],
        engine_avatar_id=visual[3],
        visual_target_fps=visual[4],
        visual_consent_verified=visual[5],
        binding_key=binding_key,
        voice_ready=voice[0] is not None,
        visual_ready=visual[0] is not None,
        multimodal_ready=voice[0] is not None and visual[0] is not None,
    )
    binding.validate()
    return binding


def normalize_avatar_fleet_media_bindings(
    bindings: Iterable[AvatarFleetMediaBinding],
) -> tuple[AvatarFleetMediaBinding, ...]:
    by_avatar: dict[tuple[str, str], AvatarFleetMediaBinding] = {}
    voice_owner: dict[str, tuple[str, str]] = {}
    visual_owner: dict[str, tuple[str, str]] = {}
    engine_voice_owner: dict[str, tuple[str, str]] = {}
    engine_avatar_owner: dict[str, tuple[str, str]] = {}

    for binding in bindings:
        binding.validate()
        key = (binding.tenant_id, binding.avatar_id)
        current = by_avatar.get(key)
        if current is not None and current != binding:
            raise ValueError("fleet_media_binding_conflict")
        by_avatar[key] = binding

        for profile_ref, owners, label in (
            (binding.voice_profile_ref, voice_owner, "voice"),
            (binding.visual_profile_ref, visual_owner, "visual"),
        ):
            if not profile_ref:
                continue
            owner = owners.get(profile_ref)
            if owner is not None and owner != key:
                raise ValueError(f"fleet_media_{label}_profile_reuse_conflict")
            owners[profile_ref] = key

        for engine_id, owners, label in (
            (binding.engine_voice_id, engine_voice_owner, "voice"),
            (binding.engine_avatar_id, engine_avatar_owner, "visual"),
        ):
            if not engine_id:
                continue
            owner = owners.get(engine_id)
            if owner is not None and owner != key:
                raise ValueError(f"fleet_media_{label}_engine_reuse_conflict")
            owners[engine_id] = key

    return tuple(by_avatar[key] for key in sorted(by_avatar))
