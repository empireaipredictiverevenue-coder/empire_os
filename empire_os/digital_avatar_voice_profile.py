"""Voice-profile and render-engine policy for Empire Digital Avatar."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from empire_os.digital_avatar_speech import AvatarSpeechRenderTask


@dataclass(frozen=True)
class AvatarVoiceProfile:
    profile_ref: str
    owner_consent_evidence_ref: str
    reference_audio_ref: str | None = None
    reference_transcript_ref: str | None = None
    engine_voice_id: str | None = None
    clone_required: bool = True
    preferred_engine: str = "cosyvoice3"
    language: str = "en"

    def validate(self) -> None:
        if not self.profile_ref.strip():
            raise ValueError("voice profile ref required")
        if not self.owner_consent_evidence_ref.strip():
            raise ValueError("voice owner consent evidence required")
        if self.clone_required:
            if not str(self.reference_audio_ref or "").strip():
                raise ValueError("clone voice reference audio required")
            if not str(self.reference_transcript_ref or "").strip():
                raise ValueError("clone voice reference transcript required")
            if not str(self.engine_voice_id or "").strip():
                raise ValueError("registered clone voice id required")


@dataclass(frozen=True)
class AvatarVoiceEngineCapability:
    engine: str
    zero_shot_clone: bool
    streaming: bool
    local_self_hosted: bool
    license_id: str
    model_ref: str | None = None


@dataclass(frozen=True)
class AvatarVoiceRenderPlan:
    meeting_id: str
    avatar_id: str
    voice_profile_ref: str
    engine: str
    model_ref: str | None
    language: str
    reference_audio_ref: str | None
    reference_transcript_ref: str | None
    engine_voice_id: str
    clone_required: bool
    streaming_required: bool
    local_audio_render_allowed: bool
    meeting_transmission_allowed: bool = False
    speech_execution_allowed: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_VOICE_ENGINES: dict[str, AvatarVoiceEngineCapability] = {
    "cosyvoice3": AvatarVoiceEngineCapability(
        engine="cosyvoice3",
        zero_shot_clone=True,
        streaming=True,
        local_self_hosted=True,
        license_id="Apache-2.0",
        model_ref="FunAudioLLM/Fun-CosyVoice3-0.5B-2512",
    ),
    "kokoro": AvatarVoiceEngineCapability(
        engine="kokoro",
        zero_shot_clone=False,
        streaming=True,
        local_self_hosted=True,
        license_id="Apache-2.0",
        model_ref="empire_voice_lab:kokoro",
    ),
}


def build_avatar_voice_render_plan(
    *,
    task: AvatarSpeechRenderTask,
    profile: AvatarVoiceProfile,
    engine_capabilities: Mapping[str, AvatarVoiceEngineCapability] | None = None,
    available_engines: Mapping[str, bool] | None = None,
) -> AvatarVoiceRenderPlan:
    profile.validate()
    if profile.profile_ref != task.voice_profile_ref:
        raise ValueError("speech task/voice profile identity mismatch")
    if task.local_audio_render_allowed is not True:
        raise ValueError("speech task does not allow local audio rendering")
    if task.meeting_transmission_allowed:
        raise ValueError("voice render plan cannot inherit meeting transmission")

    engines = dict(engine_capabilities or DEFAULT_VOICE_ENGINES)
    availability = dict(available_engines or {})
    preferred = profile.preferred_engine.strip().lower()
    capability = engines.get(preferred)
    if capability is None:
        raise ValueError("preferred avatar voice engine unsupported")
    if not capability.local_self_hosted:
        raise ValueError("avatar voice engine must be self-hosted")
    if availability and availability.get(preferred) is not True:
        raise ValueError("preferred avatar voice engine unavailable")
    if profile.clone_required and not capability.zero_shot_clone:
        raise ValueError("clone-required voice profile cannot use generic TTS")
    if profile.clone_required and not capability.streaming:
        raise ValueError("clone-required meeting voice engine must stream")

    return AvatarVoiceRenderPlan(
        meeting_id=task.meeting_id,
        avatar_id=task.avatar_id,
        voice_profile_ref=profile.profile_ref,
        engine=capability.engine,
        model_ref=capability.model_ref,
        language=profile.language,
        reference_audio_ref=profile.reference_audio_ref,
        reference_transcript_ref=profile.reference_transcript_ref,
        engine_voice_id=str(profile.engine_voice_id or "").strip(),
        clone_required=profile.clone_required,
        streaming_required=capability.streaming,
        local_audio_render_allowed=True,
    )
