"""Visual clone profile and renderer policy for Empire Digital Avatar."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from empire_os.digital_avatar_voice_sidecar import AvatarVoiceRenderArtifact


@dataclass(frozen=True)
class AvatarVisualEngineCapability:
    engine: str
    audio_driven: bool
    realtime: bool
    expressive_head_motion: bool
    local_self_hosted: bool
    code_license_id: str
    model_commercial_use: bool
    commercial_ready_by_default: bool
    model_ref: str
    notes: tuple[str, ...] = ()


DEFAULT_VISUAL_ENGINES: dict[str, AvatarVisualEngineCapability] = {
    "ditto": AvatarVisualEngineCapability(
        engine="ditto",
        audio_driven=True,
        realtime=True,
        expressive_head_motion=True,
        local_self_hosted=True,
        code_license_id="Apache-2.0",
        model_commercial_use=True,
        commercial_ready_by_default=True,
        model_ref="antgroup/ditto-talkinghead",
        notes=(
            "primary_realtime_visual_engine",
            "online_streaming_configuration_available",
        ),
    ),
    "musetalk15": AvatarVisualEngineCapability(
        engine="musetalk15",
        audio_driven=True,
        realtime=True,
        expressive_head_motion=False,
        local_self_hosted=True,
        code_license_id="MIT",
        model_commercial_use=True,
        commercial_ready_by_default=True,
        model_ref="TMElyralab/MuseTalk:1.5",
        notes=("realtime_lip_sync_fallback",),
    ),
    "liveportrait": AvatarVisualEngineCapability(
        engine="liveportrait",
        audio_driven=False,
        realtime=True,
        expressive_head_motion=True,
        local_self_hosted=True,
        code_license_id="MIT",
        model_commercial_use=True,
        commercial_ready_by_default=False,
        model_ref="KlingAIResearch/LivePortrait",
        notes=(
            "motion_layer_only",
            "replace_noncommercial_insightface_detection_models_for_commercial_use",
        ),
    ),
}


@dataclass(frozen=True)
class AvatarVisualProfile:
    profile_ref: str
    owner_consent_evidence_ref: str
    source_image_ref: str
    engine_avatar_id: str
    preferred_engine: str = "ditto"
    fallback_engines: tuple[str, ...] = ("musetalk15",)
    likeness_required: bool = True
    expressive_motion_required: bool = True
    commercial_use_required: bool = True
    target_fps: int = 30

    def validate(self) -> None:
        if not self.profile_ref.strip():
            raise ValueError("visual profile ref required")
        if not self.owner_consent_evidence_ref.strip():
            raise ValueError("visual owner consent evidence required")
        if not self.source_image_ref.strip():
            raise ValueError("visual source image ref required")
        if not self.engine_avatar_id.strip():
            raise ValueError("registered visual avatar id required")
        if self.target_fps < 20 or self.target_fps > 60:
            raise ValueError("visual target fps must be between 20 and 60")


@dataclass(frozen=True)
class AvatarVisualRenderPlan:
    meeting_id: str
    avatar_id: str
    visual_profile_ref: str
    engine: str
    model_ref: str
    engine_avatar_id: str
    source_image_ref: str
    audio_sha256: str
    target_fps: int
    expressive_head_motion: bool
    commercial_ready: bool
    local_render_allowed: bool = True
    meeting_transmission_allowed: bool = False
    visual_execution_allowed: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_avatar_visual_render_plan(
    *,
    meeting_id: str,
    avatar_id: str,
    audio: AvatarVoiceRenderArtifact,
    profile: AvatarVisualProfile,
    engine_capabilities: Mapping[str, AvatarVisualEngineCapability] | None = None,
    available_engines: Mapping[str, bool] | None = None,
    commercial_overrides: Mapping[str, bool] | None = None,
) -> AvatarVisualRenderPlan:
    profile.validate()
    clean_meeting = str(meeting_id or "").strip()
    clean_avatar = str(avatar_id or "").strip()
    if not clean_meeting or not clean_avatar:
        raise ValueError("meeting and avatar identity required")
    if audio.pcm_bytes <= 0 or not audio.audio_sha256:
        raise ValueError("visual render requires rendered speech audio evidence")
    if audio.meeting_transmission_performed or audio.speech_execution_performed:
        raise ValueError("visual plan requires pre-transmission audio artifact")

    capabilities = dict(engine_capabilities or DEFAULT_VISUAL_ENGINES)
    availability = dict(available_engines or {})
    overrides = dict(commercial_overrides or {})
    candidates = (profile.preferred_engine, *profile.fallback_engines)
    chosen: AvatarVisualEngineCapability | None = None

    for engine_name in candidates:
        capability = capabilities.get(str(engine_name).strip().lower())
        if capability is None:
            continue
        if availability and availability.get(capability.engine) is not True:
            continue
        if not capability.local_self_hosted or not capability.realtime:
            continue
        commercial_ready = (
            capability.commercial_ready_by_default
            or overrides.get(capability.engine) is True
        )
        if profile.commercial_use_required and not (
            capability.model_commercial_use and commercial_ready
        ):
            continue
        if profile.expressive_motion_required and not capability.expressive_head_motion:
            continue
        if not capability.audio_driven:
            continue
        chosen = capability
        break

    if chosen is None:
        raise ValueError("no compliant realtime visual engine available")

    return AvatarVisualRenderPlan(
        meeting_id=clean_meeting,
        avatar_id=clean_avatar,
        visual_profile_ref=profile.profile_ref,
        engine=chosen.engine,
        model_ref=chosen.model_ref,
        engine_avatar_id=profile.engine_avatar_id,
        source_image_ref=profile.source_image_ref,
        audio_sha256=audio.audio_sha256,
        target_fps=profile.target_fps,
        expressive_head_motion=chosen.expressive_head_motion,
        commercial_ready=True,
    )
