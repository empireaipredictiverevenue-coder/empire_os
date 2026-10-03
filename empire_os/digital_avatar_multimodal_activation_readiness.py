"""Authority-free multimodal activation readiness for Clone Fleet."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from empire_os.digital_avatar_fleet_media_binding import AvatarFleetMediaBinding
from empire_os.digital_avatar_visual_profile import (
    AvatarVisualEngineCapability,
    DEFAULT_VISUAL_ENGINES,
)
from empire_os.digital_avatar_voice_profile import (
    AvatarVoiceEngineCapability,
    DEFAULT_VOICE_ENGINES,
)


_REQUIRED_MEDIA = frozenset({"voice", "visual", "multimodal"})


@dataclass(frozen=True)
class AvatarMultimodalActivationReadiness:
    tenant_id: str
    avatar_id: str
    meeting_id: str
    required_media: str
    voice_ready: bool
    visual_ready: bool
    activation_ready: bool
    blockers: tuple[str, ...]
    voice_engine: str | None
    visual_engine: str | None
    media_binding_key: str
    media_identity_verified: bool = True
    recommendation_only: bool = True
    render_execution: bool = False
    provider_call_performed: bool = False
    meeting_join_performed: bool = False
    output_media_start_performed: bool = False
    speech_execution_allowed: bool = False
    visual_execution_allowed: bool = False
    commercial_execution_allowed: bool = False
    payment_execution_allowed: bool = False
    revenue_recognition_allowed: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _voice_readiness(
    *,
    binding: AvatarFleetMediaBinding,
    capabilities: Mapping[str, AvatarVoiceEngineCapability],
    availability: Mapping[str, bool],
) -> tuple[bool, tuple[str, ...]]:
    blockers: list[str] = []
    if not binding.voice_ready:
        blockers.append("voice_media_binding_missing")
        return False, tuple(blockers)

    if not str(binding.voice_profile_sha256 or "").strip():
        blockers.append("voice_profile_hash_missing")
    if not str(binding.engine_voice_id or "").strip():
        blockers.append("voice_engine_identity_missing")

    engine = str(binding.voice_engine or "").strip().lower()
    capability = capabilities.get(engine)
    if not engine or capability is None:
        blockers.append("voice_engine_unsupported")
    else:
        if not capability.local_self_hosted:
            blockers.append("voice_engine_not_self_hosted")
        if not capability.streaming:
            blockers.append("voice_engine_not_streaming")
        if not capability.zero_shot_clone:
            blockers.append("voice_engine_not_clone_capable")
        if availability.get(engine) is not True:
            blockers.append("voice_engine_unavailable")

    return not blockers, tuple(blockers)


def _visual_readiness(
    *,
    binding: AvatarFleetMediaBinding,
    capabilities: Mapping[str, AvatarVisualEngineCapability],
    availability: Mapping[str, bool],
    commercial_overrides: Mapping[str, bool],
) -> tuple[bool, tuple[str, ...]]:
    blockers: list[str] = []
    if not binding.visual_ready:
        blockers.append("visual_media_binding_missing")
        return False, tuple(blockers)

    if not str(binding.visual_profile_sha256 or "").strip():
        blockers.append("visual_profile_hash_missing")
    if not str(binding.engine_avatar_id or "").strip():
        blockers.append("visual_engine_identity_missing")

    engine = str(binding.visual_engine or "").strip().lower()
    capability = capabilities.get(engine)
    if not engine or capability is None:
        blockers.append("visual_engine_unsupported")
    else:
        if not capability.local_self_hosted:
            blockers.append("visual_engine_not_self_hosted")
        if not capability.realtime:
            blockers.append("visual_engine_not_realtime")
        if not capability.audio_driven:
            blockers.append("visual_engine_not_audio_driven")
        commercial_ready = (
            capability.model_commercial_use
            and (
                capability.commercial_ready_by_default
                or commercial_overrides.get(engine) is True
            )
        )
        if not commercial_ready:
            blockers.append("visual_engine_not_commercial_ready")
        if availability.get(engine) is not True:
            blockers.append("visual_engine_unavailable")

    return not blockers, tuple(blockers)


def assess_multimodal_activation_readiness(
    *,
    binding: AvatarFleetMediaBinding,
    meeting_id: str,
    required_media: str,
    available_voice_engines: Mapping[str, bool],
    available_visual_engines: Mapping[str, bool],
    voice_capabilities: Mapping[str, AvatarVoiceEngineCapability] | None = None,
    visual_capabilities: Mapping[str, AvatarVisualEngineCapability] | None = None,
    visual_commercial_overrides: Mapping[str, bool] | None = None,
) -> AvatarMultimodalActivationReadiness:
    binding.validate()
    meeting = str(meeting_id or "").strip()
    if not meeting:
        raise ValueError("multimodal readiness meeting_id required")
    requirement = str(required_media or "").strip().lower()
    if requirement not in _REQUIRED_MEDIA:
        raise ValueError("unsupported multimodal readiness media requirement")

    voice_ready, voice_blockers = _voice_readiness(
        binding=binding,
        capabilities=dict(voice_capabilities or DEFAULT_VOICE_ENGINES),
        availability={
            str(key).strip().lower(): bool(value)
            for key, value in available_voice_engines.items()
        },
    )
    visual_ready, visual_blockers = _visual_readiness(
        binding=binding,
        capabilities=dict(visual_capabilities or DEFAULT_VISUAL_ENGINES),
        availability={
            str(key).strip().lower(): bool(value)
            for key, value in available_visual_engines.items()
        },
        commercial_overrides={
            str(key).strip().lower(): bool(value)
            for key, value in (
                visual_commercial_overrides or {}
            ).items()
        },
    )

    blockers: list[str] = []
    if requirement in {"voice", "multimodal"}:
        blockers.extend(voice_blockers)
    if requirement in {"visual", "multimodal"}:
        blockers.extend(visual_blockers)

    ordered = tuple(dict.fromkeys(blockers))
    return AvatarMultimodalActivationReadiness(
        tenant_id=binding.tenant_id,
        avatar_id=binding.avatar_id,
        meeting_id=meeting,
        required_media=requirement,
        voice_ready=voice_ready,
        visual_ready=visual_ready,
        activation_ready=not ordered,
        blockers=ordered,
        voice_engine=binding.voice_engine,
        visual_engine=binding.visual_engine,
        media_binding_key=binding.binding_key,
    )
